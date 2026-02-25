# Illuminate Assessment Data Extractor

Python-based extractor for pulling standards-based assessment data from Illuminate/Renaissance DnA API into SQL Server with school enrichment.

## Overview

This tool provides a **two-tier table architecture** for flexible assessment data management:

- **Illuminate_\* tables**: Landing zone for ALL assessment data from Illuminate
- **HMH_\* tables**: Automatically filtered subset containing only HMH program data (Into Literature, Into Math, Into Reading)

### Key Features

- ✅ OAuth 1.0 authentication with Illuminate API
- ✅ Standards-based assessment data extraction
- ✅ SQL Server integration with MERGE operations (no duplicates)
- ✅ Automatic HMH data filtering via stored procedure
- ✅ Support for pagination and large datasets
- ✅ Comprehensive logging and error handling
- ✅ API endpoint discovery tool
- ✅ Flexible field mapping for various API structures

## Architecture

```
┌─────────────────────┐
│  Illuminate API     │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Illuminate_Assessment_Results           │ ◄── ALL assessment data
│  Illuminate_Assessment_Summary           │
│  Illuminate_Standards                    │
│  Illuminate_Assignments                  │
└──────────┬───────────────────────────────┘
           │
           │ sp_Sync_HMH_Data (auto)
           ▼
┌──────────────────────────────────────────┐
│  HMH_Assessment_Results                  │ ◄── HMH data only
│  HMH_Assessment_Summary                  │
│  HMH_Standards                           │
│  HMH_Assignments                         │
└──────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Requirements:
- Python 3.8+
- SQL Server (any version)
- ODBC Driver 17 for SQL Server

### 2. Set Up Database

Run both schema files in SQL Server:

```sql
USE YourDatabase;
GO

-- 1. Create Illuminate tables (landing zone)
-- Execute: illuminate_schema.sql

-- 2. Create HMH tables (filtered subset)
-- Execute: hmh_schema.sql
```

### 3. Configure Credentials

```bash
cp config.ini.template config.ini
# Edit config.ini with your credentials
```

Example config.ini:
```ini
[api]
base_url = https://yourdistrict.illuminateed.com/live/api/v2

[oauth]
consumer_key = your_consumer_key
consumer_secret = your_consumer_secret
access_token = your_access_token
access_token_secret = your_access_token_secret

[database]
server = your_server
database = your_database
windows_auth = false
username = your_username
password = your_password
```

### 4. Test API Connection

```bash
python test_oauth.py
```

### 5. Run Extraction

```bash
python illuminate_extractor.py
```

## Usage

### Discovery Mode

Test API endpoints and view response structures:

```bash
python illuminate_extractor.py discover
```

This creates JSON files showing the actual API response structure.

### Standard Extraction

Edit `illuminate_extractor.py` to configure:

```python
school_ids = None  # or [123, 456, 789] for specific schools
start_date = '2024-01-01'
end_date = '2024-12-31'
academic_year = '2024-2025'
```

Then run:

```bash
python illuminate_extractor.py
```

### Programmatic Usage

```python
from illuminate_extractor import IlluminateAPIExtractor

extractor = IlluminateAPIExtractor('config.ini')

# Extract all data
total = extractor.extract_illuminate_assessment_data(
    school_ids=None,
    start_date='2024-01-01',
    end_date='2024-12-31',
    academic_year='2024-2025'
)

print(f"Extracted {total} records")
```

## Database Tables

### Illuminate Tables (All Data)

**Illuminate_Assessment_Results**
- All student assessment results with standards-level scoring
- Includes HMH, district assessments, NWEA, etc.

**Illuminate_Assessment_Summary**
- Overall scores for each student-assignment combination

**Illuminate_Standards**
- Lookup table for all academic standards

**Illuminate_Assignments**
- Lookup table for all assignments/assessments

### HMH Tables (Filtered Data)

**HMH_Assessment_Results**
- Standards-level data for HMH programs only
- Automatically filtered from Illuminate tables

**HMH_Assessment_Summary**
- Overall scores for HMH assessments only

**HMH_Standards** & **HMH_Assignments**
- Lookup tables for HMH-specific data

### Automatic Filtering

The stored procedure `sp_Sync_HMH_Data` automatically filters HMH data based on:

```sql
WHERE
    LOWER(ProgramName) LIKE '%hmh%'
    OR LOWER(ProgramName) LIKE '%into literature%'
    OR LOWER(ProgramName) LIKE '%into math%'
    OR LOWER(ProgramName) LIKE '%into reading%'
    OR LOWER(Publisher) LIKE '%houghton mifflin%'
    OR LOWER(Publisher) LIKE '%harcourt%'
```

To manually re-sync:
```sql
EXEC sp_Sync_HMH_Data
```

## Sample Queries

### View All Programs

```sql
SELECT ProgramName, Publisher, COUNT(*) as AssessmentCount
FROM Illuminate_Assessment_Results
GROUP BY ProgramName, Publisher
ORDER BY AssessmentCount DESC;
```

### HMH Student Performance

```sql
SELECT
    StandardCodingNumber,
    StandardDescription,
    AVG(CAST(PointsAchieved AS FLOAT) / NULLIF(PointsPossible, 0) * 100) as AvgPercent
FROM HMH_Assessment_Results
GROUP BY StandardCodingNumber, StandardDescription
ORDER BY AvgPercent DESC;
```

### Preview HMH Filter

```sql
SELECT * FROM vw_HMH_Assessments
WHERE DateCompleted >= '2024-01-01';
```

## Troubleshooting

### OAuth Issues

If you get HTML responses instead of JSON:

1. Verify credentials in Illuminate: **Settings → API Management**
2. Ensure OAuth 1.0 (not 2.0)
3. Run diagnostics:
   ```bash
   python test_oauth.py
   python test_all_urls.py
   ```
4. Contact Illuminate support to verify API access

### Database Connection

```bash
# Test SQL Server connection
sqlcmd -S your_server -U your_user -P your_password
```

For ODBC driver issues on macOS:
```bash
brew install msodbcsql17
```

### Data Quality

Check extraction logs:
```bash
tail -f illuminate_extraction.log
```

Verify data:
```sql
-- Check record counts
SELECT 'Illuminate' as Source, COUNT(*) FROM Illuminate_Assessment_Results
UNION ALL
SELECT 'HMH', COUNT(*) FROM HMH_Assessment_Results;

-- Check date range
SELECT MIN(DateCompleted), MAX(DateCompleted)
FROM Illuminate_Assessment_Results;
```

## Documentation

- **README_NEW.md** - Detailed architecture documentation
- **SETUP_CHECKLIST.md** - Step-by-step setup guide
- **HMH_EXTRACTION_GUIDE.md** - Comprehensive HMH-specific guide
- **QUICK_START.md** - Quick reference

## File Structure

```
.
├── illuminate_extractor.py      # Main extractor
├── illuminate_schema.sql         # Illuminate tables + sync procedure
├── hmh_schema.sql               # HMH tables
├── config.ini.template          # Configuration template
├── requirements.txt             # Python dependencies
├── test_oauth.py               # OAuth diagnostic tool
├── test_all_urls.py            # API URL discovery
└── README.md                   # This file
```

## Security

⚠️ **Important**: Never commit `config.ini` to version control!

- `config.ini` is in `.gitignore`
- Use strong passwords
- Rotate API keys periodically
- Restrict database permissions to minimum required
- Consider using Windows Authentication for SQL Server

## Getting Illuminate API Credentials

1. Log into your Illuminate instance as administrator
2. Navigate to **Settings (COG icon) → API Management**
3. Create new API access key (OAuth 1.0)
4. Copy all four credentials:
   - Consumer Key
   - Consumer Secret
   - Access Token
   - Access Token Secret

## Maintenance

### Daily Incremental Loads

Use the incremental script for nightly updates:

```bash
# Extract last 7 days (recommended for nightly runs)
python illuminate_extractor_incremental.py

# Extract last 1 day
python illuminate_extractor_incremental.py 1

# Extract last 3 days
python illuminate_extractor_incremental.py 3
```

**Schedule with cron (Linux/Mac):**
```bash
# Run every night at 2 AM
0 2 * * * cd /path/to/Illuminate-Data-Extract && python3 illuminate_extractor_incremental.py >> nightly.log 2>&1
```

**Schedule with Windows Task Scheduler:**
1. Open Task Scheduler
2. Create Basic Task → "Illuminate Nightly Update"
3. Trigger: Daily at 2:00 AM
4. Action: Start program
   - Program: `python.exe`
   - Arguments: `illuminate_extractor_incremental.py`
   - Start in: `C:\path\to\Illuminate-Data-Extract`

### Re-sync HMH Data

```sql
-- After modifying filter criteria
EXEC sp_Sync_HMH_Data
```

## Requirements

- Python 3.8 or higher
- SQL Server (any version)
- ODBC Driver 17+ for SQL Server
- Illuminate API access (OAuth 1.0)

## License

This project is provided as-is for educational and data integration purposes.

## Contributing

Issues and pull requests welcome! Please ensure:
- No credentials in commits
- Code follows existing style
- Documentation updated
- Tests pass

## Support

- **API Issues**: Contact Illuminate/Renaissance support
- **Database Issues**: Check SQL Server logs
- **Code Issues**: Open a GitHub issue

---

**Note**: This extractor uses a two-tier table approach. ALL Illuminate data goes to `Illuminate_*` tables, then HMH data is automatically filtered to `HMH_*` tables. This provides maximum flexibility for querying and reporting.
