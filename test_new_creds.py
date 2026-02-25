"""
Test new Illuminate credentials - trying different OAuth configurations
"""

import requests
from requests_oauthlib import OAuth1
import json

# Your new credentials
access_key = "6424AD83199F"
access_secret = "063ddbe8543ff0b993957bb1c36e61346550afcb"

base_url = "https://therominegroup.illuminateed.com/live/api/v2"

print("=" * 80)
print("Testing Illuminate API with New Credentials")
print("=" * 80)
print(f"Access Key: {access_key}")
print(f"Access Secret: {access_secret[:10]}...")
print()

# Test 1: Use as Access Token + Secret (with empty consumer key/secret)
print("\n[Test 1] Using as Access Token/Secret with empty consumer credentials")
print("-" * 80)
oauth1 = OAuth1(
    '',  # Empty consumer key
    client_secret='',  # Empty consumer secret
    resource_owner_key=access_key,
    resource_owner_secret=access_secret,
    signature_type='auth_header'
)

try:
    response = requests.get(f"{base_url}/sites", auth=oauth1, params={'per_page': 1}, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS! Got JSON response")
        print(json.dumps(response.json(), indent=2)[:300])
    else:
        print(f"❌ Got HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Use as Consumer Key + Secret (with empty access token/secret)
print("\n\n[Test 2] Using as Consumer Key/Secret with empty access credentials")
print("-" * 80)
oauth2 = OAuth1(
    access_key,
    client_secret=access_secret,
    resource_owner_key='',
    resource_owner_secret='',
    signature_type='auth_header'
)

try:
    response = requests.get(f"{base_url}/sites", auth=oauth2, params={'per_page': 1}, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS! Got JSON response")
        print(json.dumps(response.json(), indent=2)[:300])
    else:
        print(f"❌ Got HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Use same values for both consumer and access
print("\n\n[Test 3] Using same values for both consumer AND access credentials")
print("-" * 80)
oauth3 = OAuth1(
    access_key,
    client_secret=access_secret,
    resource_owner_key=access_key,
    resource_owner_secret=access_secret,
    signature_type='auth_header'
)

try:
    response = requests.get(f"{base_url}/sites", auth=oauth3, params={'per_page': 1}, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS! Got JSON response")
        print(json.dumps(response.json(), indent=2)[:300])
    else:
        print(f"❌ Got HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Try with just Bearer token (no OAuth 1.0)
print("\n\n[Test 4] Using as Bearer token (OAuth 2.0 style)")
print("-" * 80)
headers = {
    'Authorization': f'Bearer {access_key}',
}

try:
    response = requests.get(f"{base_url}/sites", headers=headers, params={'per_page': 1}, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS! Got JSON response")
        print(json.dumps(response.json(), indent=2)[:300])
    else:
        print(f"❌ Got HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Try Basic Auth
print("\n\n[Test 5] Using as Basic Auth (username:password)")
print("-" * 80)
try:
    response = requests.get(
        f"{base_url}/sites",
        auth=(access_key, access_secret),
        params={'per_page': 1},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    if 'application/json' in response.headers.get('Content-Type', ''):
        print("✅ SUCCESS! Got JSON response")
        print(json.dumps(response.json(), indent=2)[:300])
    else:
        print(f"❌ Got HTML: {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("Testing Complete")
print("=" * 80)
