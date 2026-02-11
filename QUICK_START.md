# Quick Start Guide - HMH Assessment Extraction

## 5-Minute Setup

### 1. Install Dependencies
```bash
cd /Users/tdownie/PycharmProjects/Illuminate-Data-Extract
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create Database
In SQL Server:
```sql
CREATE DATABASE HMH_AssessmentData;
GO
USE HMH_AssessmentData;
GO
-- Run the hmh_schema.sql script
```

### 3. Configure Credentials
```bash
cp config.ini.template config.ini
# Edit config.ini with your Illuminate API and SQL Server credentials
```

### 4. Discover API Endpoints (First Time)
```bash
python illuminate_extractor.py discover
```
Check the generated JSON files to verify HMH data is accessible.

### 5. Run Extraction
```bash
python illuminate_extractor.py
```

## What Gets Extracted

- **HMH_Assessment_Results**: Student scores on individual standards
- **HMH_Assessment_Summary**: Overall assignment scores
- **HMH_Standards**: Lookup table of all standards
- **HMH_Assignments**: Lookup table of all assignments

## Key Configuration Points

Edit `illuminate_extractor.py` main() function:

```python
school_ids = None  # [123, 456] for specific schools, None for all
start_date = '2024-01-01'  # Start of date range
end_date = '2024-12-31'     # End of date range
academic_year = '2024-2025' # Academic year
```

## Verify Data

```sql
-- Check total records
SELECT COUNT(*) FROM HMH_Assessment_Results;

-- Check date range
SELECT MIN(DateCompleted), MAX(DateCompleted) FROM HMH_Assessment_Results;

-- Check unique students
SELECT COUNT(DISTINCT StudentID_LASID) FROM HMH_Assessment_Results;

-- Check programs extracted
SELECT ProgramName, COUNT(*) FROM HMH_Assessment_Results GROUP BY ProgramName;
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check OAuth credentials in config.ini |
| Cannot connect to SQL Server | Verify server name and authentication settings |
| No HMH data found | Run discover mode and check field names |
| ODBC driver error | Install: `brew install msodbcsql17` (macOS) |

## Next Steps

See **HMH_EXTRACTION_GUIDE.md** for:
- Detailed configuration options
- Advanced usage examples
- Data quality checks
- Security best practices
- Maintenance procedures
