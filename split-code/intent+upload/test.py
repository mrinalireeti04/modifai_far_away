import json
from modifai_engine import run_ai_wrapper

# Objective 1: Test with RELEVANT data
def test_successful_validation():
    print("\n--- TEST 1: Relevant Data ---")
    bucket = "modifai-bucket"
    key = "data/financial_report.pdf" # Ensure this exists in S3
    intent = "I want to extract revenue growth and risk factors from earnings reports."
    
    result = run_ai_wrapper(bucket, key, intent)
    print(json.dumps(result, indent=2))
    
    # Check if all objectives are in the output
    if result["status"] == "success":
        print("✅ SUCCESS: Intent Refined, Data Validated, and Model Selected.")
    else:
        print("❌ FAILED: Engine rejected relevant data.")

# Objective 2: Test with IRRELEVANT data (Relevance Validator Check)
def test_failed_validation():
    print("\n--- TEST 2: Irrelevant Data ---")
    bucket = "modifai-bucket"
    key = "data/cooking_recipes.pdf" # A file totally unrelated to the intent
    intent = "Analyze quarterly stock market trends."
    
    result = run_ai_wrapper(bucket, key, intent)
    print(json.dumps(result, indent=2))
    
    if result["status"] == "rejected":
        print("✅ SUCCESS: Relevance Validator correctly identified mismatch.")
    else:
        print("❌ FAILED: Engine accepted irrelevant data.")

if __name__ == "__main__":
    test_successful_validation()
    test_failed_validation()