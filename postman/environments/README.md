# Postman Environments

This directory contains Postman environment files for different deployment environments.

## Available Environments

### 1. Development.postman_environment.json
**For local development with Docker Compose**

Variables:
- `baseUrl`: `http://localhost:8080`
- `lambdaPath`: `2015-03-31/functions/function/invocations`
- `tenant_id`: `test-tenant`
- `namespace`: `default`
- `minioConsole`: `http://localhost:9006`
- `minioApi`: `http://localhost:9005`

### 2. Staging.postman_environment.json
**For AWS staging environment**

Variables:
- `baseUrl`: Your staging API Gateway URL
- `lambdaPath`: `staging`
- `tenant_id`: `staging-tenant`
- `apiKey`: Your staging API key (secret)
- `awsRegion`: `us-east-1`
- `awsAccountId`: Your AWS account ID (secret)

### 3. Production.postman_environment.json
**For AWS production environment**

Variables:
- `baseUrl`: Your production API Gateway URL
- `lambdaPath`: `prod`
- `tenant_id`: `production-tenant`
- `apiKey`: Your production API key (secret)
- `awsRegion`: `us-east-1`
- `awsAccountId`: Your AWS account ID (secret)

## How to Import

1. Open Postman
2. Click **Environments** in the left sidebar
3. Click **Import** button
4. Select the environment file(s) you want to import
5. The environment will be added to your workspace

## How to Use

1. Select the environment from the dropdown in the top-right corner
2. Click the eye icon to view/edit environment variables
3. Update any placeholder values (e.g., API Gateway URLs, API keys)
4. Run your requests - they'll automatically use the selected environment's variables

## Switching Environments

Simply select a different environment from the dropdown:
- **Development** → Local testing with Docker
- **Staging** → AWS staging environment
- **Production** → AWS production environment

## Customizing for Your Setup

### For Staging/Production:

1. Open the environment in Postman
2. Update these values:
   - `baseUrl`: Replace with your actual API Gateway URL
   - `lambdaPath`: Update if using different stage names
   - `tenant_id`: Change to your actual tenant ID
   - `apiKey`: Add your API key (if using API Gateway authentication)
   - `awsAccountId`: Add your AWS account ID
   - `awsRegion`: Update if using different region

### Adding New Variables:

You can add custom variables to any environment:
1. Open environment in Postman
2. Click **Add** to add a new variable
3. Use the variable in requests with `{{variableName}}`

## Environment Variables Used in Collection

All requests in `S3_ACID_Database.postman_collection.json` use these variables:

| Variable | Description | Used In |
|----------|-------------|---------|
| `{{baseUrl}}` | Base API URL | All requests |
| `{{lambdaPath}}` | Lambda invocation path | All requests |
| `{{tenant_id}}` | Tenant identifier | All database operations |
| `{{namespace}}` | Table namespace | All database operations |
| `{{protocol}}` | http or https | URL construction |
| `{{host}}` | Hostname | URL construction |
| `{{port}}` | Port number | URL construction (dev only) |

## Security Best Practices

1. **Never commit sensitive values**: Keep API keys and account IDs in Postman only
2. **Use secret variables**: Mark sensitive values as "secret" type in Postman
3. **Separate environments**: Always use different tenant IDs and credentials per environment
4. **Rotate API keys**: Regularly update production API keys

## Adding a New Environment

To create a new environment (e.g., for QA):

1. Copy an existing environment file
2. Rename it: `QA.postman_environment.json`
3. Update the values:
   ```json
   {
     "id": "qa-env",
     "name": "S3 ACID Database - QA",
     "values": [
       {
         "key": "baseUrl",
         "value": "https://your-qa-api-gateway.execute-api.us-east-1.amazonaws.com",
         "type": "default",
         "enabled": true
       },
       ...
     ]
   }
   ```
4. Import into Postman

## Troubleshooting

### Requests fail with 404
- Check that `baseUrl` and `lambdaPath` are correct for your environment
- Verify the API Gateway stage name matches `lambdaPath`

### Authentication errors
- Ensure `apiKey` is set (for AWS API Gateway)
- Check that the API key is valid and not expired

### Wrong tenant data
- Verify `tenant_id` matches your intended tenant
- Check that `namespace` is correct

## Example: Complete Setup

```bash
# 1. Import collection
# In Postman: Import > S3_ACID_Database.postman_collection.json

# 2. Import all environments
# In Postman: Environments > Import > Select all 3 environment files

# 3. Select Development environment
# Dropdown menu (top-right) > "S3 ACID Database - Development"

# 4. Run requests
# Start with "Health Check" to verify connectivity
```

## Documentation

- See [../README.md](../README.md) for project overview
- See [../QUICKSTART.md](../QUICKSTART.md) for API examples
- See [../CONFIG.md](../CONFIG.md) for backend configuration
