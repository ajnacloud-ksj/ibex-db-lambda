# Local Testing Guide 🛠️

Here is how to verify the Docker image and `InvalidEntrypoint` fix locally using Docker Compose.

## 1. Start the Local Lambda
Run this command from the `ibex-db-lambda` directory (or `docker` subdirectory):

```bash
# If you are in the root directory:
cd docker
docker-compose up --build lambda-api
```

This will:
1.  Build the Docker image using the updated `Dockerfile`.
2.  Start the Lambda emulator (RIE) on port `8080`.
3.  Mount your local `src/` code into the container.

## 2. Verify Health Check
Once the container is running (look for "Listening on port 8080"), open a new terminal and run:

```bash
curl -XPOST "http://localhost:8080/2015-03-31/functions/function/invocations" \
  -d '{"httpMethod":"GET","path":"/health"}'
```

**Success Response:**
You should see a JSON response with `"statusCode": 200`.

**Failure Response:**
If you see `Runtime.InvalidEntrypoint` again, likely the `CMD` or `PYTHONPATH` is still mismatched.

## 3. Test Database Operations
You can essentially use `curl` to simulate any database request.

**Example: List Tables**
```bash
curl -XPOST "http://localhost:8080/2015-03-31/functions/function/invocations" \
  -d '{
    "httpMethod": "POST",
    "path": "/database",
    "body": "{\"operation\": \"LIST_TABLES\", \"tenant_id\": \"local\", \"namespace\": \"test\"}"
  }'
```

## 4. Cleaning Up
To stop the containers:
```bash
docker-compose down
```
