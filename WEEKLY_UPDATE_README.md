# Illuminate Weekly Update Guide

## Overview

The weekly update script automatically pulls new assessment data from Illuminate and updates all database tables. It runs much faster than a full extraction since it only pulls data from the last 7 days.

## What It Does

1. **Extracts** assessment data from the last 7 days (configurable)
2. **Updates** Illuminate_Assignments lookup table with any new assignments
3. **Updates** Illuminate_Standards lookup table with any new standards
4. **Rebuilds** Illuminate_Assessment_Summary table from all current results

## Files

- `weekly_update.py` - Main Python script that performs the update
- `run_weekly_update.sh` - Shell wrapper for easy scheduling with cron
- `weekly_update.log` - Log file (created automatically)

## Manual Execution

### Basic Usage (Last 7 Days)
```bash
cd /home/ubuntu/Illuminate-Data-Extract
python3 weekly_update.py
```

### Custom Date Range
```bash
# Pull last 14 days
python3 weekly_update.py --days 14

# Pull last 3 days
python3 weekly_update.py --days 3
```

### Using the Shell Script
```bash
./run_weekly_update.sh
```

## Automated Scheduling

### Schedule with Cron (Runs Every Monday at 6:00 AM)

1. SSH to the server:
   ```bash
   ssh ubuntu@10.10.10.196
   ```

2. Edit crontab:
   ```bash
   crontab -e
   ```

3. Add this line:
   ```
   0 6 * * 1 /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh >> /home/ubuntu/Illuminate-Data-Extract/weekly_update.log 2>&1
   ```

4. Save and exit

### Cron Schedule Explanation
- `0` - Minute (0)
- `6` - Hour (6 AM)
- `*` - Day of month (any)
- `*` - Month (any)
- `1` - Day of week (1 = Monday)

### Other Cron Schedule Examples
```bash
# Every day at 2 AM
0 2 * * * /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh >> /home/ubuntu/Illuminate-Data-Extract/weekly_update.log 2>&1

# Every Sunday at midnight
0 0 * * 0 /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh >> /home/ubuntu/Illuminate-Data-Extract/weekly_update.log 2>&1

# Every Monday and Friday at 7 AM
0 7 * * 1,5 /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh >> /home/ubuntu/Illuminate-Data-Extract/weekly_update.log 2>&1
```

## Checking Cron Status

### View current cron jobs:
```bash
crontab -l
```

### Check if cron is running:
```bash
systemctl status cron
```

### View the log file:
```bash
tail -50 /home/ubuntu/Illuminate-Data-Extract/weekly_update.log
```

### Monitor in real-time:
```bash
tail -f /home/ubuntu/Illuminate-Data-Extract/weekly_update.log
```

## Expected Output

```
================================================================================
Illuminate Assessment Data Weekly Update
================================================================================
Date Range: 2026-03-24 to 2026-03-31 (7 days)
Academic Year: 2025-2026
================================================================================

2026-03-31 17:00:00,123 - INFO - STEP 1/4: Extracting recent assessment data...
2026-03-31 17:00:05,456 - INFO - Extracted 1,234 assessment records

2026-03-31 17:00:05,789 - INFO - STEP 2/4: Updating lookup tables...
2026-03-31 17:00:06,012 - INFO - Updated 15 assignments
2026-03-31 17:00:06,345 - INFO - Updated 42 standards

2026-03-31 17:00:06,678 - INFO - STEP 3/4: Rebuilding summary table...
2026-03-31 17:00:07,901 - INFO - Created 22,011 summary records

2026-03-31 17:00:08,234 - INFO - STEP 4/4: Verification...

================================================================================
WEEKLY UPDATE COMPLETED SUCCESSFULLY
================================================================================
Illuminate_Assessment_Results:   172,903 records
Illuminate_Assignments:               665 records
Illuminate_Standards:               1,445 records
Illuminate_Assessment_Summary:     22,011 records
================================================================================

Next update: Run this script again next Monday
================================================================================
```

## Troubleshooting

### Check if script ran
```bash
# Check cron log
grep CRON /var/log/syslog | tail -20

# Check our log file
tail -100 /home/ubuntu/Illuminate-Data-Extract/weekly_update.log
```

### Run manually to test
```bash
cd /home/ubuntu/Illuminate-Data-Extract
python3 weekly_update.py
```

### Common Issues

1. **Script not running**: Check cron service is active
   ```bash
   systemctl status cron
   ```

2. **Permission denied**: Make script executable
   ```bash
   chmod +x /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh
   ```

3. **Database connection failed**: Verify network connectivity
   ```bash
   ping 10.10.10.200
   ```

## Performance

- **Full extraction**: ~10-15 minutes for entire school year (172,903 records)
- **Weekly update**: ~1-2 minutes for 7 days of data (~1,000-2,000 records)

## Notes

- The script automatically determines the current academic year
- Summary table is always rebuilt from scratch (not incremental)
- Lookup tables use MERGE statements to avoid duplicates
- All operations are logged with timestamps
