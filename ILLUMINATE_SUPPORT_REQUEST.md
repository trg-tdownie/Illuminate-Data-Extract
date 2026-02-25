# API Authentication Support Request for Illuminate/Renaissance DnA

**Date:** February 11, 2026
**Organization:** The Romine Group (therominegroup.illuminateed.com)
**Purpose:** Programmatic API access for assessment data extraction

---

## Issue Summary

We are attempting to integrate with the Illuminate DnA API v2 to extract assessment data programmatically, but we are unable to authenticate successfully. We have obtained Access Key/Secret credentials but are missing additional required credentials for OAuth 1.0 authentication.

## What We've Tried

### Credentials Obtained
From **Settings (COG) → API Management**, we were able to generate:
- **Access Key:** 6424AD83199F
- **Access Secret:** 063ddbe8543ff0b993957bb1c36e61346550afcb

We selected a "consumer" (application) but did not see additional OAuth credentials displayed.

### API Endpoints Tested
- `https://therominegroup.illuminateed.com/live/api/v2/sites`
- `https://therominegroup.illuminateed.com/live/api/v2/students/assessments`
- `https://therominegroup.illuminateed.com/dna/api/v2/sites`
- `https://therominegroup.illuminateed.com/api/v2/sites`

### Authentication Methods Attempted
1. **OAuth 1.0** with Access Token/Secret (missing Consumer Key/Secret)
2. **Bearer Token** authentication
3. **Basic Authentication** (username/password style)
4. **API Key in headers** (X-API-Key, Illuminate-Access-Key)
5. **API Key in query parameters**

**Result:** All attempts return HTTP 200 with HTML content (login page) instead of JSON API responses, indicating authentication failure.

## Questions for Illuminate Support

### 1. OAuth 1.0 Credentials
Does Illuminate API v2 use OAuth 1.0 authentication? If yes, we need all four credentials:
- ✅ Access Token (we have: 6424AD83199F)
- ✅ Access Token Secret (we have: 063ddbe8543...)
- ❓ **Consumer Key** - Where can we find this?
- ❓ **Consumer Secret** - Where can we find this?

**Question:** When we select a "consumer" in API Management, how do we view the Consumer Key and Consumer Secret?

### 2. Authentication Method
What is the correct authentication method for the v2 API?
- OAuth 1.0?
- OAuth 2.0?
- API Key authentication?
- Other?

### 3. API Documentation
Can you provide:
- Official API documentation for v2
- Code examples showing authentication (preferably Python, JavaScript, or cURL)
- List of available endpoints and their parameters
- Expected request/response formats

### 4. Base URL
What is the correct base URL for API v2?
- `https://therominegroup.illuminateed.com/live/api/v2`
- `https://therominegroup.illuminateed.com/dna/api/v2`
- `https://therominegroup.illuminateed.com/api/v2`
- Other?

### 5. Required Headers
Are there any required headers for API requests? For example:
- `Content-Type: application/json`
- `Accept: application/json`
- Custom headers?

## Our Use Case

We are building a data extraction tool to:
- Extract student assessment results with standards-based scoring
- Pull data from all assessment programs (HMH, district assessments, NWEA, etc.)
- Store data in our SQL Server database for reporting and analytics
- Run automated daily/weekly extractions

**Data Required:**
- Student assessment scores (overall and by standard)
- Assessment metadata (names, dates, subjects)
- Standards information
- Student demographics
- School/site information

## Example Code We're Using

```python
from requests_oauthlib import OAuth1
import requests

# OAuth 1.0 authentication (requires all 4 credentials)
oauth = OAuth1(
    consumer_key='MISSING',        # ← Need this
    client_secret='MISSING',       # ← Need this
    resource_owner_key='6424AD83199F',
    resource_owner_secret='063ddbe8543ff0b993957bb1c36e61346550afcb',
    signature_type='auth_header'
)

response = requests.get(
    'https://therominegroup.illuminateed.com/live/api/v2/sites',
    auth=oauth,
    params={'per_page': 1}
)

# Expected: JSON response with site data
# Actual: HTML response (login page)
```

## Requested Assistance

1. **Provide complete OAuth credentials** (including Consumer Key/Secret) or explain how to obtain them
2. **Share API v2 documentation** with authentication examples
3. **Confirm correct base URL** and endpoint paths
4. **Provide working code example** for authentication (any language)
5. If OAuth 1.0 is deprecated, **explain the current authentication method**

## Technical Environment

- **Programming Language:** Python 3.12
- **HTTP Library:** requests, requests-oauthlib
- **Target Database:** SQL Server
- **Server OS:** macOS (development), Windows Server (production)

## Timeline

We are ready to begin data extraction as soon as authentication is resolved. Our extraction tool is fully built and tested, waiting only for working API credentials.

## Contact Information

**Name:** Tyler Downie
**Email:** tdownie@therominegroup.com
**Phone:** 248-202-8733
**Organization:** The Romine Group
**Best time to reach:** M-F 9am - 5pm Eastern Time

---

## Additional Notes

We have successfully connected to the SQL Server database and built all necessary data transformation logic. The extraction tool includes:
- Two-tier database architecture (all Illuminate data + filtered HMH data)
- Automatic standards-based scoring extraction
- Data quality validation
- Error handling and logging
- Support for incremental loads

We are eager to begin extracting data and appreciate your assistance in resolving this authentication issue.

Thank you for your help!

---

**Attachments:**
- API test results (showing HTML responses instead of JSON)
- Database schema (Illuminate_* and HMH_* tables)
- Code samples demonstrating authentication attempts
