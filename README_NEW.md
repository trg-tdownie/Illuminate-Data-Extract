# Illuminate Assessment Data Extractor

Complete solution for extracting ALL assessment data from Illuminate/Renaissance DnA API into SQL Server with automatic HMH data filtering.

## Architecture Overview

This extractor uses a **two-tier table structure**:

1. **Illuminate_* tables** - Landing zone for ALL Illuminate assessment data
2. **HMH_* tables** - Filtered subset containing only HMH program data

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
           │ sp_Sync_HMH_Data (auto-filters)
           ▼
┌──────────────────────────────────────────┐
│  HMH_Assessment_Results                  │ ◄── HMH data only
│  HMH_Assessment_Summary                  │
│  HMH_Standards                           │
│  HMH_Assignments                         │
└──────────────────────────────────────────┘
```

## Why Two Table Sets?

### Benefits:
1. **Flexibility** - Query all Illuminate data OR just HMH data
2. **Data Integrity** - Original Illuminate data preserved
3. **Easy Updates** - Re-sync HMH data anytime with `EXEC sp_Sync_HMH_Data`
4. **Multiple Filters** - Can create additional filtered tables (e.g., NWEA_*, DistrictAssessment_*)
5. **Performance** - HMH tables are smaller and faster to query

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Both Table Sets in SQL Server
```sql
-- Run both schema files
USE TRG_Dashboard;
GO

-- First: Create Illuminate tables (landing zone)
-- Execute illuminate_schema.sql

-- Second: Create HMH tables (filtered subset)
-- Execute hmh_schema.sql
```

### 3. Configure Credentials
Edit `config.ini` with your Illuminate API and SQL Server credentials.

### 4. Test API Connection
```bash
python test_oauth.py
```

### 5. Run Extraction
```bash
python illuminate_extractor.py
```

This will:
- Extract ALL Illuminate assessment data → Illuminate_* tables
- Automatically filter HMH data → HMH_* tables (via sp_Sync_HMH_Data)

## Database Tables

### Illuminate Tables (All Data)

**Illuminate_Assessment_Results**
- All student assessment results with standards-level scoring
- Includes: HMH, district assessments, NWEA, etc.
- Key fields: ProgramName, Publisher, AssessmentID

**Illuminate_Assessment_Summary**
- Overall scores for each assessment
- Aggregated totals across all standards

**Illuminate_Standards**
- Lookup table for all academic standards

**Illuminate_Assignments**
- Lookup table for all assignments/assessments

### HMH Tables (Filtered Subset)

**HMH_Assessment_Results**
- Standards-level data for HMH programs ONLY
- Filtered from Illuminate_Assessment_Results

**HMH_Assessment_Summary**
- Overall scores for HMH assessments only

**HMH_Standards**
- Standards used in HMH assessments

**HMH_Assignments**
- HMH assignments only

## How HMH Filtering Works

The stored procedure `sp_Sync_HMH_Data` filters data based on these criteria:

```sql
WHERE
    LOWER(ProgramName) LIKE '%hmh%'
    OR LOWER(ProgramName) LIKE '%into literature%'
    OR LOWER(ProgramName) LIKE '%into math%'
    OR LOWER(ProgramName) LIKE '%into reading%'
    OR LOWER(Publisher) LIKE '%houghton mifflin%'
    OR LOWER(Publisher) LIKE '%harcourt%'
```

### Manual Re-sync
If you need to re-sync HMH data (after changing filter criteria, etc.):

```sql
EXEC sp_Sync_HMH_Data
```

## Usage Examples

### Extract All Data
```bash
python illuminate_extractor.py
```

### Extract Specific Date Range
Edit `illuminate_extractor.py`:
```python
start_date = '2025-01-01'
end_date = '2025-06-30'
academic_year = '2024-2025'
```

### Extract Specific Schools
Edit `illuminate_extractor.py`:
```python
school_ids = [123, 456, 789]  # Your school IDs
```

### API Discovery Mode
```bash
python illuminate_extractor.py discover
```

## Querying Data

### Query ALL Illuminate Data
```sql
-- All assessment programs
SELECT ProgramName, COUNT(*) as AssessmentCount
FROM Illuminate_Assessment_Results
GROUP BY ProgramName
ORDER BY AssessmentCount DESC;

-- All publishers
SELECT Publisher, COUNT(*) as AssessmentCount
FROM Illuminate_Assessment_Results
GROUP BY Publisher;
```

### Query HMH Data Only
```sql
-- HMH assessment summary
SELECT ProgramName, Component, COUNT(*) as StudentCount
FROM HMH_Assessment_Results
GROUP BY ProgramName, Component;

-- Student performance on HMH standards
SELECT StandardCodingNumber, StandardDescription,
       AVG(CAST(PointsAchieved AS FLOAT) / NULLIF(PointsPossible, 0) * 100) as AvgPercent
FROM HMH_Assessment_Results
GROUP BY StandardCodingNumber, StandardDescription
ORDER BY AvgPercent DESC;
```

### Use the View
```sql
-- Preview what will be synced to HMH tables
SELECT *
FROM vw_HMH_Assessments
WHERE DateCompleted >= '2025-01-01';
```

## Data Flow

### During Extraction:
1. `illuminate_extractor.py` connects to Illuminate API
2. Extracts assessment data (all programs)
3. Saves to `Illuminate_Assessment_Results` & `Illuminate_Assessment_Summary`
4. Populates `Illuminate_Standards` & `Illuminate_Assignments`
5. **Automatically** runs `sp_Sync_HMH_Data`
6. HMH data filtered to `HMH_Assessment_Results` & `HMH_Assessment_Summary`

### Key Methods:

**`extract_illuminate_assessment_data()`** - Main extraction method
- Extracts ALL assessment data (not filtered)
- Saves to Illuminate_* tables
- Auto-syncs HMH data at the end

**`_sync_hmh_data()`** - Sync HMH subset
- Calls sp_Sync_HMH_Data stored procedure
- Filters HMH data from Illuminate → HMH tables

## Configuration

### config.ini Structure
```ini
[api]
base_url = https://therominegroup.illuminateed.com/live/api/v2

[oauth]
consumer_key = your_key
consumer_secret = your_secret
access_token = your_token
access_token_secret = your_token_secret

[database]
server = 10.10.10.200
database = TRG_Dashboard
windows_auth = false
username = trg-dashboard
password = your_password
```

## OAuth Troubleshooting

If you're getting HTML responses instead of JSON:

1. **Verify credentials** in Illuminate: Settings → API Management
2. **Check OAuth version** - Must be OAuth 1.0 (not 2.0)
3. **Test with the diagnostic scripts**:
   ```bash
   python test_oauth.py
   python test_all_urls.py
   ```
4. **Contact Illuminate support** to verify API access is enabled

Common issues:
- Invalid/expired credentials → Regenerate in Illuminate
- Wrong base URL → Try different URL formats
- API access not enabled → Contact admin
- Missing permissions → Check API key permissions

## Maintenance

### Daily Incremental Load
```python
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
today = datetime.now().strftime('%Y-%m-%d')

extractor.extract_illuminate_assessment_data(
    start_date=yesterday,
    end_date=today,
    academic_year='2024-2025'
)
```

### Re-sync HMH Data Only
```sql
-- If you modify HMH filter criteria or find missing data
EXEC sp_Sync_HMH_Data
```

### Archive Old Data
```sql
-- Archive data older than 3 years
INSERT INTO Illuminate_Assessment_Results_Archive
SELECT * FROM Illuminate_Assessment_Results
WHERE AcademicYear < '2022-2023';

DELETE FROM Illuminate_Assessment_Results
WHERE AcademicYear < '2022-2023';
```

## File Structure

```
Illuminate-Data-Extract/
├── illuminate_extractor.py      # Main extractor (updated for 2-tier)
├── illuminate_schema.sql         # Illuminate_* tables + sp_Sync_HMH_Data
├── hmh_schema.sql               # HMH_* tables
├── config.ini                   # Your credentials (not in git)
├── config.ini.template          # Template for credentials
├── requirements.txt             # Python dependencies
├── test_oauth.py               # OAuth diagnostic tool
├── test_all_urls.py            # URL discovery tool
├── README_NEW.md               # This file (new architecture)
├── HMH_EXTRACTION_GUIDE.md     # Detailed HMH guide
└── QUICK_START.md              # Quick reference
```

## Advanced: Creating Additional Filtered Tables

You can create additional filtered table sets for other programs:

```sql
-- Example: NWEA tables
CREATE TABLE NWEA_Assessment_Results (
    -- Same structure as HMH_Assessment_Results
);

-- Sync procedure
CREATE PROCEDURE sp_Sync_NWEA_Data AS
BEGIN
    INSERT INTO NWEA_Assessment_Results
    SELECT * FROM Illuminate_Assessment_Results
    WHERE LOWER(ProgramName) LIKE '%nwea%'
    OR LOWER(Publisher) LIKE '%nwea%';
END;
```

## Performance Tips

1. **Index Usage** - Both schemas include indexes on commonly queried fields
2. **Partition by Academic Year** - For very large datasets
3. **Incremental Loads** - Use date ranges instead of full extracts
4. **Archive Strategy** - Move old data to archive tables

## Support

### OAuth/API Issues
- Test with: `python test_oauth.py`
- Contact: Illuminate/Renaissance support

### Database Issues
- Check connection: `config.ini` database section
- Verify tables exist: Run schema scripts
- Check permissions: User needs INSERT, SELECT, EXEC

### Data Issues
- Review logs: `illuminate_extraction.log`
- Check sync results: `EXEC sp_Sync_HMH_Data` returns counts
- Verify filters: Query `vw_HMH_Assessments` view

## Security

- `config.ini` is in `.gitignore` - never commit credentials
- Use strong SQL Server passwords
- Restrict database permissions to minimum needed
- Rotate API keys periodically
- Consider Windows Authentication if possible

## License

Provided as-is for educational and data integration purposes.
