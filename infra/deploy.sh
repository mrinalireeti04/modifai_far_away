#!/bin/bash
#
# deploy.sh — Deploys Modifai Lambda functions and Step Functions state machine
#
# Usage:
#   cd /Volumes/Data/Hacks/Modifai/infra
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - AWS CLI configured with valid credentials
#   - S3 bucket 'modifai-bucket' exists
#   - IAM role 'ModifaiBedrockFineTuneRole' exists with SageMaker trust policy
#

set -e

REGION="ap-south-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
LAMBDA_ROLE_NAME="ModifaiLambdaExecutionRole"
SF_ROLE_NAME="ModifaiStepFunctionsRole"
LAMBDA_RUNTIME="python3.12"
LAMBDA_TIMEOUT=900  # 15 minutes max for Textract async
S3_BUCKET="modifai-bucket"
LAMBDA_CODE_BUCKET="modifai-lambda-code"

echo "=========================================="
echo "Modifai Infrastructure Deployment"
echo "Account: $ACCOUNT_ID | Region: $REGION"
echo "=========================================="


# ----- Step 1: Create S3 bucket for Lambda code -----
echo ""
echo "📦 Step 1: Creating Lambda code bucket..."
aws s3 mb "s3://$LAMBDA_CODE_BUCKET" --region "$REGION" 2>/dev/null || echo "   Bucket already exists"


# ----- Step 2: Create Lambda Execution Role -----
echo ""
echo "🔐 Step 2: Creating Lambda execution role..."

LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

aws iam create-role \
  --role-name "$LAMBDA_ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "   Role already exists"

# Attach policies
for POLICY in \
  "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
  "arn:aws:iam::aws:policy/AmazonS3FullAccess" \
  "arn:aws:iam::aws:policy/AmazonTextractFullAccess" \
  "arn:aws:iam::aws:policy/AmazonBedrockFullAccess" \
  "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"; do
  aws iam attach-role-policy --role-name "$LAMBDA_ROLE_NAME" --policy-arn "$POLICY" 2>/dev/null || true
done

echo "   ✅ Role: $LAMBDA_ROLE_ARN"

# Wait for role propagation
echo "   ⏳ Waiting 10s for IAM propagation..."
sleep 10


# ----- Step 3: Package and deploy Lambda functions -----
echo ""
echo "🚀 Step 3: Deploying Lambda functions..."

LAMBDAS_DIR="../lambdas"

# For macOS bash compatibility, avoiding associative arrays
FUNCS=(
  "ocr:handler.handler"
  "chunking:handler.handler"
  "dataset_generation:handler.handler"
  "dataset_generation_prepare:prepare_map.handler"
  "dataset_generation_collector:collector.handler"
  "quality_control:handler.handler"
  "fine_tune:handler.handler"
  "status_checker:handler.handler"
  "deploy:handler.handler"
)

# Store ARNs in standard variables
for ITEM in "${FUNCS[@]}"; do
  FUNC_KEY="${ITEM%%:*}"
  HANDLER="${ITEM##*:}"
  FUNC_NAME="modifai-${FUNC_KEY//_/-}"

  if [[ "$FUNC_KEY" == "dataset_generation_prepare" ]] || [[ "$FUNC_KEY" == "dataset_generation_collector" ]]; then
    SRC_DIR="$LAMBDAS_DIR/dataset_generation"
  else
    SRC_DIR="$LAMBDAS_DIR/$FUNC_KEY"
  fi

  echo "   📦 Packaging $FUNC_NAME..."
  TEMP_DIR=$(mktemp -d)
  cp "$SRC_DIR"/*.py "$TEMP_DIR/" 2>/dev/null || true
  (cd "$TEMP_DIR" && zip -q -r "/tmp/${FUNC_NAME}.zip" .)
  rm -rf "$TEMP_DIR"

  aws s3 cp "/tmp/${FUNC_NAME}.zip" "s3://${LAMBDA_CODE_BUCKET}/${FUNC_NAME}.zip" --quiet

  if aws lambda get-function --function-name "$FUNC_NAME" --region "$REGION" >/dev/null 2>&1; then
    aws lambda update-function-code \
      --function-name "$FUNC_NAME" \
      --s3-bucket "$LAMBDA_CODE_BUCKET" \
      --s3-key "${FUNC_NAME}.zip" \
      --region "$REGION" \
      --output text --query 'FunctionArn' >/dev/null
    echo "   ✅ Updated $FUNC_NAME"
  else
    FUNC_ARN=$(aws lambda create-function \
      --function-name "$FUNC_NAME" \
      --runtime "$LAMBDA_RUNTIME" \
      --handler "$HANDLER" \
      --role "$LAMBDA_ROLE_ARN" \
      --code "S3Bucket=${LAMBDA_CODE_BUCKET},S3Key=${FUNC_NAME}.zip" \
      --timeout "$LAMBDA_TIMEOUT" \
      --memory-size 512 \
      --environment "Variables={S3_BUCKET_NAME=${S3_BUCKET},AWS_REGION_OVERRIDE=${REGION},SAGEMAKER_ROLE_ARN=arn:aws:iam::${ACCOUNT_ID}:role/ModifaiBedrockFineTuneRole}" \
      --region "$REGION" \
      --output text --query 'FunctionArn')
    echo "   ✅ Created $FUNC_NAME → $FUNC_ARN"
  fi
  
  UPPER_KEY=$(echo "$FUNC_KEY" | tr '[:lower:]' '[:upper:]')
  eval "export ARN_${UPPER_KEY}=\"arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNC_NAME}\""
  rm -f "/tmp/${FUNC_NAME}.zip"
done


# ----- Step 4: Create Step Functions execution role -----
echo ""
echo "🔐 Step 4: Creating Step Functions role..."

SF_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${SF_ROLE_NAME}"

aws iam create-role \
  --role-name "$SF_ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "states.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "   Role already exists"

# Allow Step Functions to invoke Lambda
aws iam put-role-policy \
  --role-name "$SF_ROLE_NAME" \
  --policy-name "InvokeLambdaPolicy" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["lambda:InvokeFunction"],
      "Resource": "arn:aws:lambda:'"$REGION"':'"$ACCOUNT_ID"':function:modifai-*"
    }]
  }'

echo "   ✅ Role: $SF_ROLE_ARN"


# ----- Step 5: Deploy Step Functions state machine -----
echo ""
echo "🔧 Step 5: Deploying state machine..."

# Replace placeholders in state machine definition
STATE_MACHINE_DEF=$(cat state_machine.json)
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{OcrLambdaArn\}/${ARN_OCR}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{ChunkingLambdaArn\}/${ARN_CHUNKING}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{PrepareMapLambdaArn\}/${ARN_DATASET_GENERATION_PREPARE}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{DatasetGenerationLambdaArn\}/${ARN_DATASET_GENERATION}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{CollectorLambdaArn\}/${ARN_DATASET_GENERATION_COLLECTOR}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{QualityControlLambdaArn\}/${ARN_QUALITY_CONTROL}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{FineTuneLambdaArn\}/${ARN_FINE_TUNE}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{StatusCheckerLambdaArn\}/${ARN_STATUS_CHECKER}}"
STATE_MACHINE_DEF="${STATE_MACHINE_DEF//\$\{DeployLambdaArn\}/${ARN_DEPLOY}}"

SM_NAME="ModifaiPipeline"
SM_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${SM_NAME}"

if aws stepfunctions describe-state-machine --state-machine-arn "$SM_ARN" --region "$REGION" >/dev/null 2>&1; then
  aws stepfunctions update-state-machine \
    --state-machine-arn "$SM_ARN" \
    --definition "$STATE_MACHINE_DEF" \
    --role-arn "$SF_ROLE_ARN" \
    --region "$REGION" >/dev/null
  echo "   ✅ Updated state machine: $SM_ARN"
else
  SM_ARN=$(aws stepfunctions create-state-machine \
    --name "$SM_NAME" \
    --definition "$STATE_MACHINE_DEF" \
    --role-arn "$SF_ROLE_ARN" \
    --region "$REGION" \
    --output text --query 'stateMachineArn')
  echo "   ✅ Created state machine: $SM_ARN"
fi


# ----- Done -----
echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo ""
echo "State Machine ARN: $SM_ARN"
echo ""
echo "Lambda Functions:"
for ITEM in "${FUNCS[@]}"; do
  FUNC_KEY="${ITEM%%:*}"
  UPPER_KEY=$(echo "$FUNC_KEY" | tr '[:lower:]' '[:upper:]')
  var_name="ARN_${UPPER_KEY}"
  echo "   $FUNC_KEY → ${!var_name}"
done
echo ""
echo "To test (dataset_only mode):"
echo "  aws stepfunctions start-execution \\"
echo "    --state-machine-arn $SM_ARN \\"
echo "    --input '{\"project_id\":\"test\",\"s3_prefix\":\"test-user/test-project/\",\"mode\":\"dataset_only\",\"config\":{\"intent\":\"question-answering\",\"samples_per_chunk\":3,\"quality_threshold\":0.5},\"step_results\":{\"upload\":{\"raw_file_keys\":[\"data/test.pdf\"]}}}'"
echo "=========================================="
