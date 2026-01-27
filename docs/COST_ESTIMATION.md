# AWS Cost Estimation 💰

**Revised Workload**: 1,000 requests / day (**~30,000 requests / month**)
**Configuration**: 2048 MB Memory, x86_64 or ARM64.

---

## 1. Lambda Costs (Compute)

At this low volume (30k requests/month), you are well within the **AWS Free Tier** (400,000 GB-seconds/month).

- **Requests**: 30,000
- **Duration**: ~200ms
- **Compute**: 30,000 * 0.2 * 2GB = 12,000 GB-seconds
- **Cost**: **$0.00** (Free Tier)
- **Without Free Tier**: ~$0.20 / month

---

## 2. Storage Costs (S3 Standard vs S3 Express)

**Scenario**: 30,000 DB transactions/month.
**S3 Requests**: 30k * 5 = **150,000 S3 Requests / month**.

| Feature | S3 Standard | S3 Express One Zone | Difference |
| :--- | :--- | :--- | :--- |
| **Request Cost** | $0.0004 / 1k | $0.0025 / 1k | 6x multiplier |
| **Monthly Cost** | **$0.06** | **$0.38** | **Negligible** |

> **Verdict**: At 1000 requests/day, **S3 Express basically costs nothing ($0.40/month)**. 
> There is NO reason to use Standard S3 and suffer 100ms latency to save 30 cents.

---

## 3. Total Estimated Bill

**Configuration**: On-Demand Lambda + S3 Express

| Service | Configuration | Monthly Cost (Approx) |
| :--- | :--- | :--- |
| **Lambda** | 2GB Memory, On-Demand | **$0.00 - $0.20** |
| **S3 Express** | 100MB Data, 150k Requests | **~$0.50** |
| **Total** | | **< $1.00 / month** |

*This architecture is extremely cost-effective for your workload.*

## 4. Recommendation

1.  **Use S3 Express**: It's fast and cheap at this scale.
2.  **Monitor Cold Starts**: With only ~1 request every ~1.5 minutes, your Lambda *will* go cold often.
    - If user experience suffers (2-3s load times), enable **Provisioned Concurrency (1 instance)**.
    - Cost for 1 Provisioned Instance: **~$20/month**. This is optional but recommended if you hate the lag.

1.  **Deploy & Monitor**: Deploy the updated code. Enable AWS Cost Explorer tags for 'Project: IbexDB'.
2.  **Load Test**: Run a script simulating 2-5 requests/second to validate latency and see if 2 provisioned instances are enough.
3.  **Alarm Setup**: Set up CloudWatch Alarms for:
    - `ProvisionedConcurrencySpilloverInvocations` (Means you need more than 2 instances).
    - `Duration` (If queries get slow, cost goes up).
