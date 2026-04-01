#!/usr/bin/env python3
"""Check what fields Illuminate API actually returns"""
import requests
from requests_oauthlib import OAuth1
import json
import configparser

# Load config
config = configparser.ConfigParser()
config.read('/home/ubuntu/Illuminate-Data-Extract/config.ini')

consumer_key = config.get('oauth', 'consumer_key')
consumer_secret = config.get('oauth', 'consumer_secret')
access_token = config.get('oauth', 'access_token')
access_token_secret = config.get('oauth', 'access_token_secret')
base_url = config.get('api', 'base_url')

oauth = OAuth1(
    consumer_key,
    client_secret=consumer_secret,
    resource_owner_key=access_token,
    resource_owner_secret=access_token_secret,
    signature_type='auth_header'
)

print("="*80)
print("CHECKING ILLUMINATE API FIELDS")
print("="*80)

# Check Enrollment API
print("\n1. ENROLLMENT API (/Api/Enrollment/)")
print("-"*80)
url = f"{base_url}/Api/Enrollment/"
params = {'page': 1, 'limit': 1}
response = requests.get(url, auth=oauth, params=params)

if response.status_code == 200:
    data = response.json()
    if 'results' in data and len(data['results']) > 0:
        student = data['results'][0]
        print("\nAvailable fields in Enrollment API:")
        for key in sorted(student.keys()):
            value = student[key]
            if 'grade' in key.lower():
                print(f"  *** {key}: {value}")
            else:
                print(f"      {key}: {value}")
else:
    print(f"Error: {response.status_code}")

# Check Roster API
print("\n2. ROSTER API (/Api/Roster/)")
print("-"*80)
url = f"{base_url}/Api/Roster/"
params = {'page': 1, 'limit': 1}
response = requests.get(url, auth=oauth, params=params)

if response.status_code == 200:
    data = response.json()
    if 'results' in data and len(data['results']) > 0:
        roster = data['results'][0]
        print("\nAvailable fields in Roster API:")
        for key in sorted(roster.keys()):
            value = roster[key]
            if 'grade' in key.lower():
                print(f"  *** {key}: {value}")
            else:
                print(f"      {key}: {value}")
else:
    print(f"Error: {response.status_code}")

# Check Assessment Results API
print("\n3. ASSESSMENT RESULTS API (/Api/AssessmentAggregateStudentResponsesStandard/)")
print("-"*80)
url = f"{base_url}/Api/AssessmentAggregateStudentResponsesStandard/"
params = {'page': 1, 'limit': 1, 'start_date': '2025-08-01'}
response = requests.get(url, auth=oauth, params=params)

if response.status_code == 200:
    data = response.json()
    if 'results' in data and len(data['results']) > 0:
        result = data['results'][0]
        print("\nAvailable fields in Assessment Results API:")
        for key in sorted(result.keys()):
            value = result[key]
            if 'grade' in key.lower():
                print(f"  *** {key}: {value}")
            else:
                print(f"      {key}: {value}")
else:
    print(f"Error: {response.status_code}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("\nIf only 'grade_level_id' is available (no 'grade_level' or 'grade' field),")
print("then we must convert grade_level_id to actual grade by subtracting 1.")
print("="*80)
