#!/usr/bin/env python3
"""
Test script to demonstrate Microsoft Learn integration.
Shows how Azure Policy IDs are now populated in mappings.
"""

import requests
import json

# Backend URL
BASE_URL = "http://localhost:8000/api/v1"

# Test control from SAMA
test_control = {
    "control": {
        "control_id": "SAMA-IAM-01",
        "control_name": "Strong Authentication",
        "description": "Enforce multi-factor authentication (MFA) for all user access to systems and applications. Disable legacy authentication protocols that do not support MFA.",
        "domain": "Identity & Access Management"
    }
}

print("=" * 80)
print("Testing AI Control Mapping with Microsoft Learn Integration")
print("=" * 80)
print()

print("📋 Test Control:")
print(f"  ID: {test_control['control']['control_id']}")
print(f"  Name: {test_control['control']['control_name']}")
print(f"  Domain: {test_control['control']['domain']}")
print()

print("🔍 Searching Microsoft Learn for relevant Azure Policies...")
print("🤖 Mapping to MCSB using GPT-4o with policy context...")
print()

try:
    # Call the mapping endpoint
    response = requests.post(
        f"{BASE_URL}/mapping/map-single",
        json=test_control,
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        mapping = result['mapping']
        
        print("✅ Mapping Complete!")
        print("=" * 80)
        print()
        
        print("🎯 MCSB Mapping:")
        print(f"  Control ID: {mapping['mcsb_control_id']}")
        print(f"  Control Name: {mapping['mcsb_control_name']}")
        print(f"  Domain: {mapping['mcsb_domain']}")
        print()
        
        print("📊 Confidence & Type:")
        print(f"  Confidence Score: {mapping['confidence_score']:.0%}")
        print(f"  Mapping Type: {mapping['mapping_type']}")
        print()
        
        print("💡 AI Reasoning:")
        print(f"  {mapping['reasoning']}")
        print()
        
        print("🔧 Azure Policy IDs (from Microsoft Learn):")
        if mapping['azure_policy_ids']:
            for policy_id in mapping['azure_policy_ids']:
                print(f"  • {policy_id}")
            print()
            print(f"✨ Found {len(mapping['azure_policy_ids'])} policies!")
        else:
            print("  (No policies found - this may indicate search issues)")
        print()
        
        # Show the full JSON
        print("📄 Full Mapping JSON:")
        print(json.dumps(mapping, indent=2))
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to backend.")
    print("   Make sure the backend is running: uvicorn app.main:app --port 8000")
    
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("=" * 80)
print("Test Complete!")
print("=" * 80)
