"""
Test if Illuminate API has a Standards endpoint
"""
from illuminate_extractor import IlluminateAPIExtractor
import json

print("=" * 80)
print("Testing Illuminate API for Standards Endpoints")
print("=" * 80)

extractor = IlluminateAPIExtractor()

# Test possible standards endpoints
endpoints_to_test = [
    '/Api/Standards',
    '/Api/Standards/',
    '/Api/StandardSets',
    '/Api/StandardSets/',
    '/Api/AssessmentStandards',
    '/Api/AssessmentStandards/',
    '/Api/Standard',
    '/Api/Standard/',
]

print("\nTesting possible endpoints...\n")

for endpoint in endpoints_to_test:
    print(f"Testing: {endpoint}")
    try:
        params = {'page': 1, 'limit': 5}
        data = extractor._make_api_request(endpoint, params)

        if data:
            print(f"  ✓ SUCCESS! Endpoint exists and returned data")
            print(f"  Response type: {type(data)}")

            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())}")
                if 'results' in data:
                    print(f"  Results count: {len(data.get('results', []))}")
                    if len(data.get('results', [])) > 0:
                        print(f"  First result keys: {list(data['results'][0].keys())}")
                        print(f"  Sample record:")
                        print(f"    {json.dumps(data['results'][0], indent=4)[:500]}")
            elif isinstance(data, list):
                print(f"  List length: {len(data)}")
                if len(data) > 0:
                    print(f"  First item keys: {list(data[0].keys())}")
                    print(f"  Sample record:")
                    print(f"    {json.dumps(data[0], indent=4)[:500]}")

            print(f"\n  🎉 FOUND WORKING ENDPOINT: {endpoint}")
            break
        else:
            print(f"  ❌ No data returned (likely doesn't exist)")

    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")

    print()

print("\n" + "=" * 80)
print("\nAlternative: Check Standards in Assessment Details")
print("=" * 80)

# Try to get an assessment and see if it includes standards
print("\nGetting a sample assessment to check for standards metadata...")
try:
    # Get recent assessments
    params = {'page': 1, 'limit': 1}
    data = extractor._make_api_request('/Api/AssessmentAggregateStudentResponsesStandard/', params)

    if data and 'results' in data and len(data['results']) > 0:
        assessment_id = data['results'][0].get('assessment_id')
        print(f"\nFound assessment ID: {assessment_id}")

        # Try to get assessment details
        print(f"Testing /Api/Assessments/{assessment_id}")
        assessment_detail = extractor._make_api_request(f'/Api/Assessments/{assessment_id}')

        if assessment_detail:
            print(f"  ✓ Got assessment details")
            print(f"  Keys: {list(assessment_detail.keys()) if isinstance(assessment_detail, dict) else 'Not a dict'}")

            # Look for standards
            if isinstance(assessment_detail, dict):
                if 'standards' in assessment_detail:
                    print(f"\n  🎉 Assessment details include standards!")
                    standards = assessment_detail['standards']
                    print(f"  Standards count: {len(standards)}")
                    if len(standards) > 0:
                        print(f"  Sample standard:")
                        print(f"    {json.dumps(standards[0], indent=4)}")
                else:
                    print(f"  ❌ No 'standards' field in assessment details")
                    print(f"\n  Available fields:")
                    for key in assessment_detail.keys():
                        print(f"    - {key}")
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 80)
