# Setup Checklist - Illuminate Data Extractor

Use this checklist to set up the extractor once OAuth is resolved.

## ✅ Setup Steps

### 1. Database Setup

- [ ] Connect to SQL Server (10.10.10.200, TRG_Dashboard)
- [ ] Run `illuminate_schema.sql` to create:
  - Illuminate_Assessment_Results
  - Illuminate_Assessment_Summary
  - Illuminate_Standards
  - Illuminate_Assignments
  - vw_HMH_Assessments (view)
  - sp_Sync_HMH_Data (stored procedure)
- [ ] Run `hmh_schema.sql` to create:
  - HMH_Assessment_Results
  - HMH_Assessment_Summary
  - HMH_Standards
  - HMH_Assignments
- [ ] Verify tables exist:
  ```sql
  SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_NAME LIKE 'Illuminate_%' OR TABLE_NAME LIKE 'HMH_%';
  ```

### 2. Python Environment

- [x] Dependencies installed (`pip install -r requirements.txt`)
- [x] Config file created (`config.ini`)
- [x] SQL Server credentials configured
- [ ] OAuth credentials configured (waiting for Illuminate)

### 3. OAuth Resolution (IN PROGRESS)

Contact Illuminate support to verify:
- [ ] API access is enabled for your account
- [ ] OAuth 1.0 credentials are correct
- [ ] Credentials have proper permissions
- [ ] Correct base URL format

Test with:
```bash
python test_oauth.py
python test_all_urls.py
```

### 4. Test Run

Once OAuth is working:
- [ ] Run discovery mode:
  ```bash
  python illuminate_extractor.py discover
  ```
- [ ] Review generated JSON files to verify data structure
- [ ] Update field mappings if needed (in `_extract_common_illuminate_fields()`)
- [ ] Run small test extraction (1-2 days of data):
  ```python
  # Edit illuminate_extractor.py
  start_date = '2025-02-01'
  end_date = '2025-02-02'
  ```
- [ ] Verify data in database:
  ```sql
  SELECT COUNT(*) FROM Illuminate_Assessment_Results;
  SELECT COUNT(*) FROM HMH_Assessment_Results;
  SELECT ProgramName, COUNT(*) FROM Illuminate_Assessment_Results GROUP BY ProgramName;
  ```

### 5. Full Production Run

- [ ] Set date range for full extraction
- [ ] Set school_ids if needed (or None for all schools)
- [ ] Run extractor:
  ```bash
  python illuminate_extractor.py
  ```
- [ ] Monitor log file: `illuminate_extraction.log`
- [ ] Verify data quality:
  ```sql
  -- Check date range
  SELECT MIN(DateCompleted), MAX(DateCompleted) FROM Illuminate_Assessment_Results;

  -- Check student counts
  SELECT COUNT(DISTINCT StudentID_LASID) FROM Illuminate_Assessment_Results;

  -- Check HMH sync
  SELECT 'Illuminate' as Source, COUNT(*) as Records FROM Illuminate_Assessment_Results
  UNION ALL
  SELECT 'HMH', COUNT(*) FROM HMH_Assessment_Results;

  -- Check programs
  SELECT ProgramName, COUNT(*) as AssessmentCount
  FROM Illuminate_Assessment_Results
  GROUP BY ProgramName
  ORDER BY AssessmentCount DESC;
  ```

## 🔧 Current Status

### ✅ Completed
- Python dependencies installed
- SQL Server connection configured
- Illuminate schema created (illuminate_schema.sql)
- HMH schema created (hmh_schema.sql)
- Extractor updated for two-table architecture
- Auto-sync stored procedure (sp_Sync_HMH_Data)
- Documentation created
- Test scripts created (test_oauth.py, test_all_urls.py)

### ⏳ Waiting
- Illuminate support response for OAuth credentials

### 📋 Once OAuth Works
1. Run test extraction (1-2 days)
2. Verify data structure matches
3. Adjust field mappings if needed
4. Run full production extraction
5. Set up scheduled incremental loads

## 📊 What You'll Get

### Illuminate_* Tables (All Data)
All assessment data from Illuminate including:
- HMH assessments
- District-created assessments
- NWEA assessments
- Any other assessments in Illuminate

### HMH_* Tables (Filtered Data)
Only HMH program data:
- Into Literature
- Into Math
- Into Reading

Automatically filtered via `sp_Sync_HMH_Data`

## 🔍 Troubleshooting

### If OAuth still not working:
1. Ask Illuminate for API documentation specific to your instance
2. Request example API call with curl or Postman
3. Verify the exact base URL format they use
4. Check if there's a different authentication method available

### If data looks wrong:
1. Check discovery JSON files to see actual API structure
2. Update field mappings in `_extract_common_illuminate_fields()` (line 772)
3. Modify HMH filter in `sp_Sync_HMH_Data` if needed

### If sync not working:
```sql
-- Manually check what would be synced
SELECT * FROM vw_HMH_Assessments;

-- Manually run sync
EXEC sp_Sync_HMH_Data;

-- Check results
SELECT 'HMH Results' as TableName, COUNT(*) as Records FROM HMH_Assessment_Results
UNION ALL
SELECT 'HMH Summary', COUNT(*) FROM HMH_Assessment_Summary;
```

## 📞 Support Contacts

- **Illuminate API Issues**: Illuminate/Renaissance support
- **SQL Server Issues**: Your DBA / IT department
- **Python/Code Issues**: Check logs in `illuminate_extraction.log`

## 🗓️ Next Steps After Setup

1. **Schedule Daily Incremental Loads**
   - Extract previous day's data each morning
   - Keeps database current

2. **Create Reports/Views**
   - Build reporting views on top of HMH tables
   - Create dashboards for teachers/admins

3. **Archive Strategy**
   - Archive data older than 3 years
   - Keep Illuminate tables as historical record

4. **Monitor Data Quality**
   - Check for missing students
   - Verify all schools represented
   - Compare counts with Illuminate UI

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `illuminate_extractor.py` | Main extraction script |
| `illuminate_schema.sql` | Illuminate_* tables + sync procedure |
| `hmh_schema.sql` | HMH_* tables |
| `config.ini` | Your credentials (not in git) |
| `test_oauth.py` | OAuth diagnostic tool |
| `README_NEW.md` | Complete documentation |
| `QUICK_START.md` | Quick reference |
| `illuminate_extraction.log` | Runtime logs |

---

**Status**: Ready to run once OAuth is resolved with Illuminate support.
