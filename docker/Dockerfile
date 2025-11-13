# AWS Lambda Python runtime with uv for dependency management
FROM public.ecr.aws/lambda/python:3.11

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml requirements.txt* ./

# Install dependencies with uv (using requirements.txt if it exists, else pyproject.toml)
RUN if [ -f requirements.txt ]; then \
        uv pip install --system -r requirements.txt; \
    else \
        uv pip install --system -r pyproject.toml; \
    fi

# Install DuckDB Iceberg extensions
# Pre-install all necessary extensions at build time
RUN python3 -c "import duckdb; import platform; \
    print(f'Platform: {platform.machine()}'); \
    conn = duckdb.connect(':memory:'); \
    conn.execute('INSTALL iceberg'); \
    conn.execute('INSTALL httpfs'); \
    print('✓ DuckDB extensions installed')"

# Ensure extensions persist and create test database
RUN python3 -c "import duckdb; \
    conn = duckdb.connect('/tmp/test.db'); \
    conn.execute('FORCE INSTALL iceberg'); \
    conn.execute('FORCE INSTALL httpfs'); \
    conn.execute('LOAD iceberg'); \
    conn.execute('LOAD httpfs'); \
    print('✓ Extensions verified and loaded')"

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Set environment variables (can be overridden)
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src:${PYTHONPATH}"

# Lambda handler location
CMD ["src.lambda_handler.lambda_handler"]
