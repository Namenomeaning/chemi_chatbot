# Deployment Guide - CHEMI Chemistry Chatbot

Hướng dẫn triển khai CHEMI lên AWS App Runner.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub Repo   │────▶│   Amazon ECR    │────▶│  AWS App Runner │
│   (Source)      │     │ (Docker Images) │     │   (Hosting)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   Amazon S3     │
                                               │ (Static Assets) │
                                               └─────────────────┘
```

## Prerequisites

1. **AWS CLI** configured với credentials
2. **Docker** installed
3. **uv** (Python package manager)

## AWS Resources Cần Thiết

### 1. ECR Repository

```bash
aws ecr create-repository \
  --repository-name chemistry-chatbot \
  --region ap-southeast-1
```

### 2. S3 Bucket (Static Assets)

```bash
aws s3 mb s3://chemistry-chatbot-assets --region ap-southeast-1

# Enable public access
aws s3api put-public-access-block \
  --bucket chemistry-chatbot-assets \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Set bucket policy for public read
aws s3api put-bucket-policy --bucket chemistry-chatbot-assets --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::chemistry-chatbot-assets/*"
  }]
}'
```

### 3. IAM Roles

#### ECR Access Role (for App Runner to pull images)

```bash
# Create trust policy
cat > /tmp/ecr-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "build.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerECRAccessRole \
  --assume-role-policy-document file:///tmp/ecr-trust.json

aws iam attach-role-policy \
  --role-name AppRunnerECRAccessRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

#### Instance Role (for App Runner to access S3)

```bash
# Create trust policy
cat > /tmp/instance-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "tasks.apprunner.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name AppRunnerInstanceRole \
  --assume-role-policy-document file:///tmp/instance-trust.json

# S3 access policy
cat > /tmp/s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:HeadObject"],
    "Resource": "arn:aws:s3:::chemistry-chatbot-assets/*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name AppRunnerInstanceRole \
  --policy-name S3Access \
  --policy-document file:///tmp/s3-policy.json
```

## Manual Deployment

### Step 1: Build Docker Image

```bash
cd /path/to/chemistry_chatbot

# Build
docker build -f Dockerfile.apprunner -t chemistry-chatbot:latest .
```

### Step 2: Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin \
  <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com

# Tag
docker tag chemistry-chatbot:latest \
  <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest

# Push
docker push <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest
```

### Step 3: Create App Runner Service (First Time)

```bash
aws apprunner create-service \
  --service-name chemistry-chatbot \
  --region ap-southeast-1 \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "7860",
        "RuntimeEnvironmentVariables": {
          "OPENAI_API_KEY": "<YOUR_API_KEY>",
          "OPENAI_BASE_URL": "https://gpt3.shupremium.com/v1",
          "OPENAI_MODEL": "gpt-4o-mini",
          "S3_BUCKET": "chemistry-chatbot-assets",
          "S3_REGION": "ap-southeast-1",
          "S3_BASE_URL": "https://chemistry-chatbot-assets.s3.ap-southeast-1.amazonaws.com"
        }
      }
    },
    "AutoDeploymentsEnabled": true,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/AppRunnerECRAccessRole"
    }
  }' \
  --instance-configuration '{
    "InstanceRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/AppRunnerInstanceRole"
  }'
```

### Step 4: Deploy Updates

```bash
# Get service ARN
SERVICE_ARN=$(aws apprunner list-services --region ap-southeast-1 \
  --query "ServiceSummaryList[?ServiceName=='chemistry-chatbot'].ServiceArn" --output text)

# Start deployment
aws apprunner start-deployment --service-arn $SERVICE_ARN --region ap-southeast-1
```

## CI/CD với GitHub Actions

### Setup GitHub Secrets

Trong repo GitHub, vào **Settings > Secrets and variables > Actions** và thêm:

| Secret Name | Value |
|-------------|-------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |

### Workflow File

File `.github/workflows/deploy.yml` sẽ tự động:
1. Build Docker image khi push to `main`
2. Push image to ECR
3. Trigger App Runner deployment

```yaml
name: Deploy to AWS App Runner

on:
  push:
    branches:
      - main

env:
  AWS_REGION: ap-southeast-1
  ECR_REPOSITORY: chemistry-chatbot
  APP_RUNNER_SERVICE: chemistry-chatbot

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push
        run: |
          docker build -f Dockerfile.apprunner -t ${{ steps.login-ecr.outputs.registry }}/$ECR_REPOSITORY:latest .
          docker push ${{ steps.login-ecr.outputs.registry }}/$ECR_REPOSITORY:latest

      - name: Deploy
        run: |
          SERVICE_ARN=$(aws apprunner list-services \
            --query "ServiceSummaryList[?ServiceName=='$APP_RUNNER_SERVICE'].ServiceArn" --output text)
          aws apprunner start-deployment --service-arn $SERVICE_ARN
```

## Update Environment Variables

```bash
SERVICE_ARN=$(aws apprunner list-services --region ap-southeast-1 \
  --query "ServiceSummaryList[?ServiceName=='chemistry-chatbot'].ServiceArn" --output text)

aws apprunner update-service \
  --service-arn "$SERVICE_ARN" \
  --region ap-southeast-1 \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "7860",
        "RuntimeEnvironmentVariables": {
          "OPENAI_API_KEY": "<NEW_KEY>",
          "OPENAI_BASE_URL": "https://gpt3.shupremium.com/v1",
          "OPENAI_MODEL": "gpt-4o-mini",
          "S3_BUCKET": "chemistry-chatbot-assets",
          "S3_REGION": "ap-southeast-1",
          "S3_BASE_URL": "https://chemistry-chatbot-assets.s3.ap-southeast-1.amazonaws.com"
        }
      }
    },
    "AutoDeploymentsEnabled": true,
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/AppRunnerECRAccessRole"
    }
  }'
```

## Monitor & Debug

### Check Service Status

```bash
aws apprunner describe-service \
  --service-arn $SERVICE_ARN \
  --region ap-southeast-1 \
  --query "Service.[Status,ServiceUrl]"
```

### View Logs

```bash
# Logs available in CloudWatch
# Log group: /aws/apprunner/chemistry-chatbot/<service-id>/application
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `InvalidAccessRole` | Check IAM role trust policy includes `build.apprunner.amazonaws.com` |
| `libXrender.so.1 not found` | Add `libxrender1 libxext6` to Dockerfile |
| `libexpat.so.1 not found` | Add `libexpat1` to Dockerfile |
| `Unable to locate credentials` | Add Instance Role with S3 permissions |
| Service stuck in `OPERATION_IN_PROGRESS` | Wait 3-5 minutes, then check logs |

## Costs

- **App Runner**: ~$5-25/month (auto-scales based on traffic)
- **ECR**: ~$0.10/GB/month for storage
- **S3**: ~$0.023/GB/month + request costs

## Quick Deploy Commands

```bash
# One-liner: Build, push, deploy
cd /path/to/chemistry_chatbot && \
docker build -f Dockerfile.apprunner -t chemistry-chatbot:latest . && \
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com && \
docker tag chemistry-chatbot:latest <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest && \
docker push <ACCOUNT_ID>.dkr.ecr.ap-southeast-1.amazonaws.com/chemistry-chatbot:latest && \
aws apprunner start-deployment --service-arn $(aws apprunner list-services --region ap-southeast-1 --query "ServiceSummaryList[?ServiceName=='chemistry-chatbot'].ServiceArn" --output text) --region ap-southeast-1
```

## URLs

- **App**: https://fbhd6ucgpf.ap-southeast-1.awsapprunner.com
- **S3 Assets**: https://chemistry-chatbot-assets.s3.ap-southeast-1.amazonaws.com/
