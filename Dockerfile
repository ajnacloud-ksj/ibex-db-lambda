# AWS Lambda Python runtime with uv for dependency management
# Using Python 3.12+ for Amazon Linux 2023 with GLIBC 2.34 (required by DuckDB iceberg extension)
FROM public.ecr.aws/lambda/python:3.12

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies with uv using pyproject.toml
RUN uv pip install --system --no-cache -e .

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

# Ensure correct permissions for Lambda execution
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Remove custom PYTHONPATH - we want to import 'src' package from root
# ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src:${PYTHONPATH}"

# Lambda handler location (Module path)
CMD ["src.lambda_handler.lambda_handler"]
