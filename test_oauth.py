"""
Simple OAuth test script to debug Illuminate API authentication
"""

import requests
from requests_oauthlib import OAuth1
import json
import configparser

def test_oauth():
    # Load config
    config = configparser.ConfigParser()
    config.read('config.ini')

    base_url = config.get('api', 'base_url')
    consumer_key = config.get('oauth', 'consumer_key')
    consumer_secret = config.get('oauth', 'consumer_secret')
    access_token = config.get('oauth', 'access_token')
    access_token_secret = config.get('oauth', 'access_token_secret')

    print("=" * 80)
    print("Illuminate OAuth Authentication Test")
    print("=" * 80)
    print(f"Base URL: {base_url}")
    print(f"Consumer Key: {consumer_key[:10]}...")
    print(f"Access Token: {access_token[:10]}...")
    print()

    # Create OAuth1 auth
    oauth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
        signature_type='auth_header'
    )

    # Test different possible endpoints
    test_endpoints = [
        'assessments',  # List of assessments
        'students',     # List of students
        'sites',        # List of schools
    ]

    for endpoint in test_endpoints:
        url = f"{base_url}/{endpoint}"
        print(f"\nTesting: {url}")
        print("-" * 80)

        try:
            response = requests.get(url, auth=oauth, params={'per_page': 1}, timeout=30)

            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print(f"Response Length: {len(response.text)} chars")

            # Check if it's HTML (login page) or JSON (API response)
            if 'text/html' in response.headers.get('Content-Type', ''):
                print("❌ FAILED: Received HTML instead of JSON (likely auth issue)")
                print(f"First 200 chars: {response.text[:200]}")
            elif response.status_code == 401:
                print("❌ FAILED: 401 Unauthorized")
                print(f"Response: {response.text}")
            elif response.status_code == 403:
                print("❌ FAILED: 403 Forbidden (check API permissions)")
                print(f"Response: {response.text}")
            elif response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ SUCCESS: Valid JSON response received!")
                    print(f"Response structure: {json.dumps(data, indent=2)[:500]}...")

                    # Save successful response
                    with open(f'test_response_{endpoint}.json', 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"Saved to: test_response_{endpoint}.json")

                except json.JSONDecodeError:
                    print("❌ FAILED: 200 OK but not valid JSON")
                    print(f"Response: {response.text[:500]}")
            else:
                print(f"❌ FAILED: Unexpected status code {response.status_code}")
                print(f"Response: {response.text[:500]}")

        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR: {e}")

    print("\n" + "=" * 80)
    print("Authentication Test Complete")
    print("=" * 80)

    # Provide troubleshooting tips
    print("\nTroubleshooting:")
    print("1. If all responses are HTML:")
    print("   - OAuth credentials may be invalid or expired")
    print("   - Check credentials in Illuminate: Settings (COG) > API Management")
    print("   - Make sure you're using OAuth 1.0 credentials (not OAuth 2.0)")
    print()
    print("2. If you get 401/403 errors:")
    print("   - API access may not be enabled for your account")
    print("   - Contact your Illuminate administrator")
    print()
    print("3. Alternative API URLs to try:")
    print("   - https://therominegroup.illuminateed.com/api/v2")
    print("   - https://therominegroup.illuminateed.com/dna/api/v2")
    print("   - https://api.illuminateed.com/v2")
    print()

if __name__ == "__main__":
    test_oauth()
