#!/usr/bin/env python3
"""Quick API test script for the AI Mapping Agent backend."""

import httpx
import json
import sys

def test_endpoints():
    """Test the main API endpoints."""
    base_url = "http://localhost:8000"
    
    try:
        # Test root endpoint
        print("=" * 60)
        print("Testing Root Endpoint")
        print("=" * 60)
        r = httpx.get(f'{base_url}/')
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))
        
        # Test health endpoint  
        print("\n" + "=" * 60)
        print("Testing Health Endpoint")
        print("=" * 60)
        r = httpx.get(f'{base_url}/api/v1/health')
        print(f"Status: {r.status_code}")
        health = r.json()
        print(json.dumps(health, indent=2))
        
        # Test MCSB domains
        print("\n" + "=" * 60)
        print("Testing MCSB Domains Endpoint")
        print("=" * 60)
        r = httpx.get(f'{base_url}/api/v1/mapping/mcsb/domains')
        print(f"Status: {r.status_code}")
        domains = r.json()
        print(f"Found {len(domains)} MCSB domains:")
        for domain in domains[:10]:  # Show first 10
            print(f"  - {domain}")
        
        # Test MCSB controls endpoint
        print("\n" + "=" * 60)
        print("Testing MCSB Controls Endpoint")
        print("=" * 60)
        r = httpx.get(f'{base_url}/api/v1/mapping/mcsb/controls')
        print(f"Status: {r.status_code}")
        controls = r.json()
        print(f"Found {len(controls)} MCSB controls")
        if controls:
            print(f"\nFirst control example:")
            print(json.dumps(controls[0], indent=2))
            
        print("\n" + "=" * 60)
        print("✅ All endpoints responding!")
        print("=" * 60)
        print(f"\nAPI Documentation: {base_url}/docs")
        print(f"ReDoc: {base_url}/redoc")
        
        return 0
        
    except httpx.ConnectError as e:
        print(f"❌ Error: Could not connect to backend at {base_url}")
        print(f"Make sure the server is running with: uvicorn app.main:app --reload")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_endpoints())
