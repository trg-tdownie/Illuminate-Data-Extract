"""
Test multiple possible Illuminate API URL formats
"""

import requests
from requests_oauthlib import OAuth1
import json
import configparser

def test_all_urls():
    # Load config
    config = configparser.ConfigParser()
    config.read('config.ini')

    consumer_key = config.get('oauth', 'consumer_key')
    consumer_secret = config.get('oauth', 'consumer_secret')
    access_token = config.get('oauth', 'access_token')
    access_token_secret = config.get('oauth', 'access_token_secret')

    # Create OAuth1 auth
    oauth = OAuth1(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
        signature_type='auth_header'
    )

    # Test different base URLs
    base_urls = [
        'https://therominegroup.illuminateed.com/api/v2',
        'https://therominegroup.illuminateed.com/live/api/v2',
        'https://therominegroup.illuminateed.com/dna/api/v2',
        'https://api.illuminateed.com/v2',
        'https://therominegroup.illuminateed.com/api',
        'https://therominegroup.illuminateed.com/live/api',
    ]

    print("=" * 80)
    print("Testing All Possible Illuminate API URLs")
    print("=" * 80)

    for base_url in base_urls:
        url = f"{base_url}/sites"  # sites is usually a simple endpoint
        print(f"\nTesting: {url}")
        print("-" * 80)

        try:
            response = requests.get(url, auth=oauth, params={'per_page': 1}, timeout=10)

            content_type = response.headers.get('Content-Type', '')
            is_json = 'application/json' in content_type

            print(f"Status: {response.status_code} | Content-Type: {content_type}")

            if is_json and response.status_code == 200:
                print("✅ SUCCESS! This URL works!")
                try:
                    data = response.json()
                    print(f"Response preview: {json.dumps(data, indent=2)[:300]}...")
                    print(f"\n💡 Use this base URL: {base_url}")
                    return base_url
                except:
                    pass
            elif 'text/html' in content_type:
                print("❌ HTML response (auth issue)")
            else:
                print(f"❌ Failed: {response.text[:100]}")

        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n" + "=" * 80)
    print("No working URL found!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Log into Illuminate and verify the OAuth credentials")
    print("2. Go to: Settings (COG icon) > API Management")
    print("3. Check if the OAuth keys are for 'API v2' access")
    print("4. Try regenerating new OAuth 1.0 credentials")
    print("5. Check with Illuminate support if API access is enabled")
    return None

if __name__ == "__main__":
    working_url = test_all_urls()
