#!/usr/bin/env python3
"""
Test Azure OpenAI connection with DefaultAzureCredential
"""
import os
import sys
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

def test_connection():
    print("🔧 Testing Azure OpenAI Connection")
    print("=" * 80)
    
    # Get configuration
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    
    print(f"📍 Endpoint: {endpoint}")
    print(f"🚀 Deployment: {deployment}")
    print(f"📋 API Version: {api_version}")
    print()
    
    try:
        print("🔐 Authenticating with DefaultAzureCredential...")
        credential = DefaultAzureCredential()
        
        # Get token provider for Azure OpenAI scope
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default"
        )
        
        print("✅ Credential obtained successfully")
        print()
        
        print("🤖 Creating Azure OpenAI client...")
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version
        )
        print("✅ Client created successfully")
        print()
        
        print("💬 Testing chat completion...")
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Connection successful!' if you can read this."}
            ],
            max_completion_tokens=50
        )
        
        message = response.choices[0].message.content
        print(f"✅ Response received: {message}")
        print()
        
        print("=" * 80)
        print("🎉 SUCCESS! Azure OpenAI is configured correctly")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}")
        print(f"   {str(e)}")
        print()
        
        if "403" in str(e) or "Forbidden" in str(e):
            print("💡 Permission Issue:")
            print("   You may need 'Cognitive Services OpenAI User' role")
            print()
            print("   Grant yourself the role:")
            print(f"   az role assignment create \\")
            print(f"     --role 'Cognitive Services OpenAI User' \\")
            print(f"     --assignee $(az ad signed-in-user show --query id -o tsv) \\")
            print(f"     --scope /subscriptions/<subscription-id>/resourceGroups/wadutoit-ai-rg/providers/Microsoft.CognitiveServices/accounts/wadutoit-oai-san-01")
        
        elif "DeploymentNotFound" in str(e):
            print("💡 Deployment Issue:")
            print(f"   Deployment '{deployment}' not found")
            print("   Check available deployments:")
            print("   az cognitiveservices account deployment list --name wadutoit-oai-san-01 --resource-group wadutoit-ai-rg")
        
        print()
        print("=" * 80)
        print("❌ FAILED - Please fix the issue above and try again")
        print("=" * 80)
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
