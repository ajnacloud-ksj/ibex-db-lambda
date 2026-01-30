#!/usr/bin/env python3
"""
Performance Benchmark for IbexDB Lambda
Measures improvement from optimizations
"""

import boto3
import json
import time
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

# Lambda client
lambda_client = boto3.client('lambda')

class IbexDBBenchmark:
    def __init__(self, function_name='ibex-db-lambda', alias=None):
        self.function_name = function_name
        self.alias = alias
        self.results = {}

    def invoke_lambda(self, payload):
        """Invoke Lambda and measure latency"""
        start_time = time.perf_counter()

        response = lambda_client.invoke(
            FunctionName=f"{self.function_name}:{self.alias}" if self.alias else self.function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        # Parse response
        result = json.loads(response['Payload'].read())
        if 'body' in result:
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        else:
            body = result

        return {
            'latency_ms': latency_ms,
            'status_code': response.get('StatusCode', result.get('statusCode')),
            'cache_hit': result.get('headers', {}).get('X-Cache-Hit', 'false') == 'true',
            'execution_time': body.get('execution_time_ms'),
            'success': body.get('success', False)
        }

    def benchmark_cold_start(self, iterations=5):
        """Measure cold start performance"""
        print("\n📊 Benchmarking Cold Start Performance...")

        latencies = []
        for i in range(iterations):
            # Force cold start by waiting
            if i > 0:
                print("  Waiting 15 minutes for container to go cold...")
                time.sleep(900)  # 15 minutes

            payload = {
                'body': json.dumps({
                    'operation': 'LIST_TABLES',
                    'tenant_id': 'benchmark-test'
                })
            }

            result = self.invoke_lambda(payload)
            latencies.append(result['latency_ms'])
            print(f"  Run {i+1}: {result['latency_ms']:.2f}ms")

        self.results['cold_start'] = {
            'latencies': latencies,
            'avg': statistics.mean(latencies),
            'min': min(latencies),
            'max': max(latencies)
        }

    def benchmark_warm_performance(self, iterations=20):
        """Measure warm Lambda performance"""
        print("\n📊 Benchmarking Warm Performance...")

        # Warmup
        print("  Warming up Lambda...")
        for _ in range(3):
            payload = {
                'body': json.dumps({
                    'operation': 'LIST_TABLES',
                    'tenant_id': 'benchmark-test'
                })
            }
            self.invoke_lambda(payload)

        # Measure warm performance
        latencies = []
        cache_hits = 0

        for i in range(iterations):
            payload = {
                'body': json.dumps({
                    'operation': 'QUERY',
                    'tenant_id': 'benchmark-test',
                    'table': 'food_entries',
                    'filters': [{'field': 'user_id', 'operator': 'eq', 'value': 'test-user'}],
                    'limit': 10
                })
            }

            result = self.invoke_lambda(payload)
            latencies.append(result['latency_ms'])
            if result['cache_hit']:
                cache_hits += 1

            if (i + 1) % 5 == 0:
                print(f"  Progress: {i+1}/{iterations} (Cache hits: {cache_hits})")

        self.results['warm_performance'] = {
            'latencies': latencies,
            'avg': statistics.mean(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'p50': statistics.median(latencies),
            'p95': sorted(latencies)[int(len(latencies) * 0.95)],
            'p99': sorted(latencies)[int(len(latencies) * 0.99)],
            'cache_hit_rate': cache_hits / iterations
        }

    def benchmark_cache_effectiveness(self):
        """Measure cache effectiveness"""
        print("\n📊 Benchmarking Cache Effectiveness...")

        # Test 1: First query (cache miss)
        print("  Testing cache miss...")
        payload_miss = {
            'body': json.dumps({
                'operation': 'QUERY',
                'tenant_id': f'cache-test-{time.time()}',
                'table': 'food_entries',
                'limit': 50
            })
        }
        miss_result = self.invoke_lambda(payload_miss)

        # Test 2: Repeated query (cache hit)
        print("  Testing cache hit...")
        hit_results = []
        for _ in range(5):
            hit_result = self.invoke_lambda(payload_miss)
            hit_results.append(hit_result)

        self.results['cache_effectiveness'] = {
            'cache_miss_latency': miss_result['latency_ms'],
            'cache_hit_latency': statistics.mean([r['latency_ms'] for r in hit_results]),
            'improvement': ((miss_result['latency_ms'] - statistics.mean([r['latency_ms'] for r in hit_results])) /
                           miss_result['latency_ms']) * 100,
            'cache_hits': sum(1 for r in hit_results if r['cache_hit'])
        }

    def benchmark_batch_operations(self):
        """Measure batch operation performance"""
        print("\n📊 Benchmarking Batch Operations...")

        # Test individual operations
        print("  Testing individual operations...")
        individual_start = time.perf_counter()

        for i in range(10):
            payload = {
                'body': json.dumps({
                    'operation': 'WRITE',
                    'tenant_id': 'batch-test',
                    'table': 'food_entries',
                    'records': [{
                        'id': f'batch-test-{i}',
                        'description': f'Test item {i}',
                        'calories': 100 + i
                    }]
                })
            }
            self.invoke_lambda(payload)

        individual_time = (time.perf_counter() - individual_start) * 1000

        # Test batch operation
        print("  Testing batch operation...")
        batch_payload = {
            'body': json.dumps({
                'operation': 'BATCH',
                'tenant_id': 'batch-test',
                'operations': [
                    {
                        'operation': 'WRITE',
                        'table': 'food_entries',
                        'records': [{
                            'id': f'batch-test-bulk-{i}',
                            'description': f'Bulk test item {i}',
                            'calories': 200 + i
                        }]
                    }
                    for i in range(10)
                ]
            })
        }

        batch_result = self.invoke_lambda(batch_payload)

        self.results['batch_operations'] = {
            'individual_time_ms': individual_time,
            'batch_time_ms': batch_result['latency_ms'],
            'improvement': ((individual_time - batch_result['latency_ms']) / individual_time) * 100
        }

    def benchmark_concurrent_requests(self, concurrent_users=10):
        """Measure performance under concurrent load"""
        print(f"\n📊 Benchmarking Concurrent Requests ({concurrent_users} users)...")

        def make_request(user_id):
            payload = {
                'body': json.dumps({
                    'operation': 'QUERY',
                    'tenant_id': f'concurrent-test-{user_id}',
                    'table': 'food_entries',
                    'filters': [{'field': 'user_id', 'operator': 'eq', 'value': f'user-{user_id}'}],
                    'limit': 20
                })
            }
            return self.invoke_lambda(payload)

        latencies = []
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request, i) for i in range(concurrent_users * 5)]

            for future in as_completed(futures):
                result = future.result()
                latencies.append(result['latency_ms'])

        total_time = (time.perf_counter() - start_time) * 1000
        throughput = len(latencies) / (total_time / 1000)

        self.results['concurrent_requests'] = {
            'concurrent_users': concurrent_users,
            'total_requests': len(latencies),
            'total_time_ms': total_time,
            'throughput_rps': throughput,
            'avg_latency': statistics.mean(latencies),
            'p95_latency': sorted(latencies)[int(len(latencies) * 0.95)],
            'p99_latency': sorted(latencies)[int(len(latencies) * 0.99)]
        }

    def print_results(self):
        """Print benchmark results"""
        print("\n" + "="*60)
        print("IBEXDB LAMBDA OPTIMIZATION BENCHMARK RESULTS")
        print("="*60)

        # Cold Start
        if 'cold_start' in self.results:
            r = self.results['cold_start']
            print("\n🧊 Cold Start Performance:")
            print(f"  Average: {r['avg']:.2f}ms")
            print(f"  Min: {r['min']:.2f}ms")
            print(f"  Max: {r['max']:.2f}ms")

        # Warm Performance
        if 'warm_performance' in self.results:
            r = self.results['warm_performance']
            print("\n🔥 Warm Performance:")
            print(f"  Average: {r['avg']:.2f}ms")
            print(f"  P50: {r['p50']:.2f}ms")
            print(f"  P95: {r['p95']:.2f}ms")
            print(f"  P99: {r['p99']:.2f}ms")
            print(f"  Cache Hit Rate: {r['cache_hit_rate']*100:.1f}%")

        # Cache Effectiveness
        if 'cache_effectiveness' in self.results:
            r = self.results['cache_effectiveness']
            print("\n💾 Cache Effectiveness:")
            print(f"  Cache Miss: {r['cache_miss_latency']:.2f}ms")
            print(f"  Cache Hit: {r['cache_hit_latency']:.2f}ms")
            print(f"  Improvement: {r['improvement']:.1f}%")

        # Batch Operations
        if 'batch_operations' in self.results:
            r = self.results['batch_operations']
            print("\n📦 Batch Operations:")
            print(f"  Individual (10 ops): {r['individual_time_ms']:.2f}ms")
            print(f"  Batch (10 ops): {r['batch_time_ms']:.2f}ms")
            print(f"  Improvement: {r['improvement']:.1f}%")

        # Concurrent Requests
        if 'concurrent_requests' in self.results:
            r = self.results['concurrent_requests']
            print(f"\n👥 Concurrent Requests ({r['concurrent_users']} users):")
            print(f"  Throughput: {r['throughput_rps']:.2f} req/s")
            print(f"  Avg Latency: {r['avg_latency']:.2f}ms")
            print(f"  P95 Latency: {r['p95_latency']:.2f}ms")
            print(f"  P99 Latency: {r['p99_latency']:.2f}ms")

        # Overall Assessment
        print("\n" + "="*60)
        print("OPTIMIZATION IMPACT SUMMARY")
        print("="*60)

        if 'warm_performance' in self.results and 'cache_effectiveness' in self.results:
            # Calculate overall improvement
            baseline_latency = 2000  # Original average latency
            optimized_latency = self.results['warm_performance']['avg']
            overall_improvement = ((baseline_latency - optimized_latency) / baseline_latency) * 100

            print(f"\n🎯 Overall Performance:")
            print(f"  Baseline Latency: ~2000ms")
            print(f"  Optimized Latency: {optimized_latency:.2f}ms")
            print(f"  Overall Improvement: {overall_improvement:.1f}%")

            # Cost impact
            invocations_per_month = 1000000  # Example
            original_duration = 2000  # ms
            optimized_duration = optimized_latency
            original_cost = (invocations_per_month * original_duration / 1000) * 0.0000166667 * 0.5  # 512MB
            optimized_cost = (invocations_per_month * optimized_duration / 1000) * 0.0000166667 * 3  # 3GB
            cost_difference = optimized_cost - original_cost

            print(f"\n💰 Cost Analysis (1M invocations/month):")
            print(f"  Original Cost: ${original_cost:.2f}")
            print(f"  Optimized Cost: ${optimized_cost:.2f}")
            if cost_difference < 0:
                print(f"  Savings: ${abs(cost_difference):.2f} ({abs(cost_difference/original_cost)*100:.1f}%)")
            else:
                print(f"  Additional Cost: ${cost_difference:.2f} ({cost_difference/original_cost*100:.1f}%)")

            print("\n✅ Optimizations are highly effective!" if overall_improvement > 50 else
                  "\n⚠️ Optimizations show moderate improvement" if overall_improvement > 20 else
                  "\n❌ Limited improvement detected")

    def save_results(self, filename=None):
        """Save results to JSON file"""
        if not filename:
            filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📁 Results saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(description='Benchmark IbexDB Lambda Performance')
    parser.add_argument('--function', default='ibex-db-lambda', help='Lambda function name')
    parser.add_argument('--alias', help='Lambda alias to test')
    parser.add_argument('--skip-cold-start', action='store_true', help='Skip cold start tests')
    parser.add_argument('--quick', action='store_true', help='Run quick benchmark only')

    args = parser.parse_args()

    print("\n🚀 Starting IbexDB Lambda Benchmark...")
    print(f"Function: {args.function}")
    if args.alias:
        print(f"Alias: {args.alias}")

    benchmark = IbexDBBenchmark(args.function, args.alias)

    try:
        if not args.skip_cold_start and not args.quick:
            benchmark.benchmark_cold_start(iterations=1)

        benchmark.benchmark_warm_performance(iterations=10 if args.quick else 20)
        benchmark.benchmark_cache_effectiveness()

        if not args.quick:
            benchmark.benchmark_batch_operations()
            benchmark.benchmark_concurrent_requests(concurrent_users=5)

        benchmark.print_results()
        benchmark.save_results()

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())