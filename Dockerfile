# AWS Lambda Python runtime with uv for dependency management
# Using Python 3.12+ for Amazon Linux 2023 with GLIBC 2.34 (required by DuckDB iceberg extension)
FROM public.ecr.aws/lambda/python:3.12

# Install uv for fast Python package management (via pip to avoid ghcr 403 errors)
RUN pip install uv

# Copy dependency files
COPY requirements.txt ./

# Install dependencies (without installing the package itself to avoid namespace conflicts)
RUN uv pip install --system --no-cache -r requirements.txt

# Install DuckDB Iceberg extensions
# Pre-install all necessary extensions at build time
# Set home directory to a persistent location that Lambda can access
RUN mkdir -p /opt/duckdb_extensions && \
    python3 -c "import duckdb; import platform; \
    print(f'Platform: {platform.machine()}'); \
    conn = duckdb.connect(':memory:'); \
    conn.execute('SET home_directory=\\\"/opt/duckdb_extensions\\\"'); \
    conn.execute('INSTALL avro'); \
    conn.execute('INSTALL iceberg'); \
    conn.execute('INSTALL httpfs'); \
    print('✓ DuckDB extensions installed')"

# Verify extensions can be loaded
RUN python3 -c "import duckdb; \
    conn = duckdb.connect(':memory:'); \
    conn.execute('SET home_directory=\\\"/opt/duckdb_extensions\\\"'); \
    conn.execute('LOAD avro'); \
    conn.execute('LOAD iceberg'); \
    conn.execute('LOAD httpfs'); \
    print('✓ Extensions verified and loaded')"

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# Ensure correct permissions for Lambda execution
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Lambda handler location - src.lambda_handler.lambda_handler
# /var/task is in PYTHONPATH by default, and we have /var/task/src/lambda_handler.py
CMD ["src.lambda_handler.lambda_handler"]
