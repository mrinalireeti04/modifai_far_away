import boto3
import json

# We need both clients to be 100% sure
bedrock_admin = boto3.client('bedrock', region_name='us-east-1')
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

def test_bedrock_intelligence():
    print("🔍 Testing Modifai's AI Brain...")
    
    # 1. Test Admin Access (List Models)
    try:
        models = bedrock_admin.list_foundation_models()
        print("✅ Bedrock Admin: SUCCESS (Can see model list)")
    except Exception as e:
        print(f"❌ Bedrock Admin: FAILED. {e}")

    # 2. Test Runtime Access (Actual AI Response)
    # We use Claude 3 Haiku as it's the fastest for testing
    prompt_data = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Say 'System Online'"}]
    }
    
    try:
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps(prompt_data)
        )
        result = json.loads(response.get('body').read())
        print(f"✅ Bedrock Runtime: SUCCESS. AI says: {result['content'][0]['text']}")
    except Exception as e:
        print(f"❌ Bedrock Runtime: FAILED. {e}")
        print("💡 TIP: Ensure you have requested 'Claude 3 Haiku' access in the Bedrock Console.")

test_bedrock_intelligence()