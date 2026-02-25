"""
Test Illuminate API with simplified authentication (API Key style)
"""

import requests
import json

access_key = "6424AD83199F"
access_secret = "063ddbe8543ff0b993957bb1c36e61346550afcb"

base_url = "https://therominegroup.illuminateed.com/live/api/v2"

print("=" * 80)
print("Testing Illuminate API - API Key Authentication Methods")
print("=" * 80)

# Test 1: Query parameters
print("\n[Test 1] API Key in query parameters")
print("-" * 80)
try:
    response = requests.get(
        f"{base_url}/sites",
        params={
            'api_key': access_key,
            'api_secret': access_secret,
            'per_page': 1
        },
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Custom headers
print("\n[Test 2] API Key in custom headers")
print("-" * 80)
try:
    response = requests.get(
        f"{base_url}/sites",
        headers={
            'X-API-Key': access_key,
            'X-API-Secret': access_secret
        },
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Try different header names
print("\n[Test 3] Illuminate-specific headers")
print("-" * 80)
try:
    response = requests.get(
        f"{base_url}/sites",
        headers={
            'Illuminate-Access-Key': access_key,
            'Illuminate-Access-Secret': access_secret
        },
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Combined Authorization header
print("\n[Test 4] Combined in Authorization header")
print("-" * 80)
try:
    response = requests.get(
        f"{base_url}/sites",
        headers={
            'Authorization': f'Key {access_key}:{access_secret}'
        },
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Try /dna/api instead of /live/api
print("\n[Test 5] Try different base URL (/dna/api/v2)")
print("-" * 80)
alt_url = "https://therominegroup.illuminateed.com/dna/api/v2"
try:
    response = requests.get(
        f"{alt_url}/sites",
        auth=(access_key, access_secret),
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 6: Try without /v2
print("\n[Test 6] Try without version number (/live/api)")
print("-" * 80)
simple_url = "https://therominegroup.illuminateed.com/live/api"
try:
    response = requests.get(
        f"{simple_url}/sites",
        auth=(access_key, access_secret),
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS!")
        print(json.dumps(response.json(), indent=2)[:500])
    else:
        print(f"❌ HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("Testing Complete")
print("=" * 80)
print("\nIf all tests failed, you may need to:")
print("1. Check if there's API documentation in Illuminate")
print("2. Contact Illuminate support for authentication details")
print("3. Look for a 'Help' or 'Documentation' link in API Management")
