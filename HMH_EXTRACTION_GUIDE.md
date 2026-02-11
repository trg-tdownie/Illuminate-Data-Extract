# HMH Assessment Data Extraction from Illuminate API

Complete guide for extracting HMH (Houghton Mifflin Harcourt) assessment data from Illuminate/Renaissance DnA API into SQL Server database with standards-based scoring.

## Overview

This tool extracts detailed HMH assessment data including:
- **Into Literature** assessments
- **Into Math** assessments
- **Into Reading** assessments

Data includes student-level performance on individual standards with points achieved, points possible, and percentage scores.

## Features

- Standards-based assessment results (HMH_Assessment_Results table)
- Overall assignment summaries (HMH_Assessment_Summary table)
- Standards lookup table (HMH_Standards)
- Assignments lookup table (HMH_Assignments)
- Automatic academic year calculation
- SQL Server database integration with MERGE operations (no duplicates)
- API endpoint discovery tool
- OAuth 1.0 authentication
- Pagination support for large datasets
- Comprehensive logging

## Prerequisites

### Software Requirements

1. **Python 3.8 or higher**
2. **SQL Server** (any version)
3. **ODBC Driver 17 for SQL Server** (or higher)
   - Windows: Usually pre-installed
   - macOS: `brew install msodbcsql17`
   - Linux: Follow [Microsoft's guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)

### Access Requirements

1. **Illuminate API credentials** (OAuth 1.0)
2. **SQL Server database** with appropriate permissions
3. **Network access** to both Illuminate API and SQL Server

## Installation

### 1. Navigate to Project Directory

```bash
cd /Users/tdownie/PycharmProjects/Illuminate-Data-Extract
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up SQL Server Database

#### Create the Database

Connect to SQL Server using your preferred tool (SSMS, Azure Data Studio, sqlcmd):

```sql
CREATE DATABASE HMH_AssessmentData;
GO
```

#### Run the Schema Script

Execute the `hmh_schema.sql` file to create all tables:

```sql
USE HMH_AssessmentData;
GO

-- Then run the contents of hmh_schema.sql
```

Or use sqlcmd:

```bash
sqlcmd -S your_server -d HMH_AssessmentData -i hmh_schema.sql
```

### 5. Configure API and Database Credentials

Copy the template and edit with your credentials:

```bash
cp config.ini.template config.ini
nano config.ini  # or use your preferred editor
```

Fill in your actual values:

```ini
[api]
base_url = https://yourdistrict.illuminateed.com/api/v2

[oauth]
consumer_key = your_actual_consumer_key
consumer_secret = your_actual_consumer_secret
access_token = your_actual_access_token
access_token_secret = your_actual_access_token_secret

[database]
server = localhost\SQLEXPRESS  # or your server address
database = HMH_AssessmentData
windows_auth = false  # Set to true for Windows Authentication
username = your_sql_username  # Only if windows_auth = false
password = your_sql_password  # Only if windows_auth = false
```

## Getting Illuminate API Credentials

1. Log in to your Illuminate instance as an administrator
2. Click the **COG (Settings)** icon
3. Navigate to **API Management**
4. Create a new API access key or use existing one
5. Copy the **OAuth 1.0** credentials:
   - Consumer Key
   - Consumer Secret
   - Access Token
   - Access Token Secret

## Usage

### Step 1: Discover API Endpoints (First Time Setup)

Before running the full extraction, discover which endpoints are available:

```bash
python illuminate_extractor.py discover
```

This will:
- Test multiple potential endpoints
- Save response structures to JSON files
- Help you verify that HMH data is accessible
- Create files like `api_discovery_students_assessments.json`

Review these files to understand the data structure from your Illuminate instance.

### Step 2: Configure Extraction Parameters

Edit `illuminate_extractor.py` and update the `main()` function:

```python
def main():
    # ...

    # Configuration for HMH extraction
    school_ids = None  # Set to [123, 456] for specific schools, or None for all
    start_date = '2024-01-01'  # Your date range
    end_date = '2024-12-31'
    academic_year = '2024-2025'  # Your academic year

    # ...
```

### Step 3: Run the Extraction

```bash
python illuminate_extractor.py
```

You should see output like:

```
================================================================================
HMH Assessment Data Extractor for Illuminate API
================================================================================
School IDs: All schools
Date Range: 2024-01-01 to 2024-12-31
Academic Year: 2024-2025
================================================================================
============================================================
Starting HMH assessment data extraction
============================================================
Attempting to extract from students/assessment_standards endpoint...
Processed page 1, total HMH records: 243
Processed page 2, total HMH records: 512
...
```

### Advanced Usage Examples

#### Extract for Specific Schools Only

```python
extractor = IlluminateAPIExtractor('config.ini')
extractor.extract_hmh_assessment_data(
    school_ids=[123, 456, 789],
    start_date='2024-09-01',
    end_date='2024-12-31',
    academic_year='2024-2025'
)
```

#### Extract Without Connecting to Database (Test API Only)

```python
extractor = IlluminateAPIExtractor('config.ini')
extractor.discover_api_endpoints()  # No DB connection required
```

## Database Schema

### HMH_Assessment_Results

Stores individual student performance on each standard:

- Student identifiers (SASID, LASID)
- Assignment details (ProgramName, Component, AssignmentName)
- Standard information (StandardSet, StandardCodingNumber, StandardDescription)
- Performance data (PointsAchieved, PointsPossible, PercentCorrect)
- School and teacher information
- Timestamps

### HMH_Assessment_Summary

Stores overall assignment scores (aggregated):

- Same student/assignment fields as Results
- Total points across all standards
- Overall percentage
- Used for summary reports

### HMH_Standards

Lookup table for all standards:

- StandardSet (e.g., "Common Core State Standards")
- StandardCodingNumber (e.g., "RL.9-10.1")
- StandardDescription
- Subject

### HMH_Assignments

Lookup table for all assignments:

- ProgramName (e.g., "HMH Into Literature")
- Component (e.g., "Unit 1 Assessment")
- AssignmentName
- Subject

## Data Flow

```
Illuminate API
    ↓
illuminate_extractor.py
    ↓
Data Transformation & Mapping
    ↓
SQL Server Tables:
    ├── HMH_Assessment_Results (standards-level)
    ├── HMH_Assessment_Summary (overall scores)
    ├── HMH_Standards (lookup)
    └── HMH_Assignments (lookup)
```

## How the Extractor Works

### 1. HMH Assessment Detection

The extractor identifies HMH assessments by checking for these keywords in the API response:
- "hmh"
- "into literature"
- "into math"
- "into reading"
- "houghton mifflin"
- "harcourt"

### 2. Data Extraction Endpoints

The extractor tries these endpoints in order:

1. **students/assessment_standards** - Primary endpoint for standards-based data
2. **students/assessments** - Fallback for standard assessment results

### 3. Field Mapping

The extractor intelligently maps various API field names to your schema:

| Schema Field | Possible API Fields |
|--------------|-------------------|
| StudentID_SASID | state_student_id, sasid |
| StudentID_LASID | local_student_id, lasid, student_id |
| SchoolName | school_name, site_name |
| AssignmentName | assessment_name, assessment_title, assignment_name |

### 4. Academic Year Calculation

Academic years are automatically calculated from test dates:
- July 1, 2024 → June 30, 2025 = "2024-2025"
- Dates from July-December use current year as start
- Dates from January-June use previous year as start

## Logging

All operations are logged to `illuminate_extraction.log`:

```
2024-02-06 10:15:23 - INFO - OAuth 1.0 authentication configured
2024-02-06 10:15:24 - INFO - Successfully connected to SQL Server database
2024-02-06 10:15:25 - INFO - Starting HMH assessment data extraction
2024-02-06 10:15:26 - INFO - Processed page 1, total HMH records: 243
```

Check this file for detailed debugging information.

## Troubleshooting

### Authentication Errors

**401 Unauthorized:**
- Verify OAuth credentials in `config.ini`
- Check that API access is still active in Illuminate
- Ensure you're using OAuth 1.0 credentials (not OAuth 2.0)

### Database Connection Errors

**Cannot connect to SQL Server:**
- Verify SQL Server is running
- Check server name format (include instance name if needed: `localhost\SQLEXPRESS`)
- For Windows Auth: Ensure `windows_auth = true`
- For SQL Auth: Verify username/password
- Check firewall rules (port 1433)

**ODBC Driver not found:**
- Install ODBC Driver 17 for SQL Server
- macOS: `brew install msodbcsql17`
- Verify installation: `odbcinst -j`

### No Data Found

**HMH assessments not detected:**

1. Run discovery to see what data is available:
   ```bash
   python illuminate_extractor.py discover
   ```

2. Review the generated JSON files to verify:
   - HMH data exists in your Illuminate instance
   - Field names match what the extractor is looking for

3. Modify the `_is_hmh_assessment()` function if needed to match your data:
   ```python
   def _is_hmh_assessment(self, result: Dict) -> bool:
       # Add your custom identifiers here
       hmh_identifiers = [
           'hmh', 'your_custom_identifier'
       ]
       # ...
   ```

### Rate Limiting

If you experience rate limiting:
- The script includes 0.5 second delays between requests
- Increase delay: Change `time.sleep(0.5)` to `time.sleep(1.0)` in the code
- Extract smaller date ranges
- Contact Illuminate support for rate limit information

### Missing Fields

If certain fields are NULL:
- Check the discovery JSON files to see field names in your API
- Update `_extract_common_hmh_fields()` to match your field names
- The extractor handles missing fields gracefully (NULL values)

## Data Quality Checks

After extraction, run these queries to verify data quality:

```sql
-- Check total records
SELECT COUNT(*) as TotalRecords FROM HMH_Assessment_Results;

-- Check date range
SELECT MIN(DateCompleted) as EarliestDate,
       MAX(DateCompleted) as LatestDate
FROM HMH_Assessment_Results;

-- Check for students with results
SELECT COUNT(DISTINCT StudentID_LASID) as UniqueStudents
FROM HMH_Assessment_Results;

-- Check standards distribution
SELECT StandardCodingNumber, COUNT(*) as AssessmentCount
FROM HMH_Assessment_Results
GROUP BY StandardCodingNumber
ORDER BY AssessmentCount DESC;

-- Check programs
SELECT ProgramName, COUNT(*) as AssessmentCount
FROM HMH_Assessment_Results
GROUP BY ProgramName;

-- Verify summary vs detail counts
SELECT
    (SELECT COUNT(*) FROM HMH_Assessment_Summary) as SummaryCount,
    (SELECT COUNT(DISTINCT AssignmentName + CAST(StudentID_LASID AS VARCHAR))
     FROM HMH_Assessment_Results) as UniqueAssignmentStudents;
```

## Security Best Practices

- Never commit `config.ini` with real credentials to version control
- Add `config.ini` to `.gitignore`
- Use strong SQL Server passwords
- Restrict database user permissions to minimum required:
  ```sql
  GRANT INSERT, SELECT ON HMH_Assessment_Results TO your_user;
  GRANT INSERT, SELECT ON HMH_Assessment_Summary TO your_user;
  GRANT INSERT, SELECT ON HMH_Standards TO your_user;
  GRANT INSERT, SELECT ON HMH_Assignments TO your_user;
  ```
- Store API credentials securely (consider Azure Key Vault, AWS Secrets Manager, etc.)
- Use Windows Authentication when possible
- Enable SQL Server encryption

## Performance Optimization

For large extractions:

1. **Index Optimization**: The schema includes indexes on commonly queried fields
2. **Batch Size**: Default is 1000 records per page (maximum allowed by Illuminate)
3. **Incremental Loads**: Use date range parameters to load only recent data
4. **Parallel Processing**: Not currently implemented, but could be added for multiple school IDs

## Maintenance

### Regular Tasks

1. **Monitor log file size**: Rotate `illuminate_extraction.log` periodically
2. **Update dependencies**: Run `pip install --upgrade -r requirements.txt` quarterly
3. **Database maintenance**: Rebuild indexes monthly for large tables
4. **Archive old data**: Move historical data to archive tables if needed

### Incremental Updates

To load only new/updated data daily:

```python
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
today = datetime.now().strftime('%Y-%m-%d')

extractor.extract_hmh_assessment_data(
    start_date=yesterday,
    end_date=today,
    academic_year='2024-2025'
)
```

## Support

For issues related to:
- **This script**: Check `illuminate_extraction.log` and verify configuration
- **Illuminate API**: Contact Renaissance/Illuminate support
- **SQL Server**: Refer to Microsoft documentation
- **HMH programs**: Contact HMH support

## License

This project is provided as-is for educational and data integration purposes.

## Changelog

### Version 2.0 (Current)
- Added HMH-specific extraction
- Migrated from MySQL to SQL Server
- Added standards-based assessment support
- Added API endpoint discovery
- Improved field mapping flexibility
- Added academic year auto-calculation

### Version 1.0
- Initial release with general Illuminate extraction
- MySQL support
- Basic assessment and student score extraction
