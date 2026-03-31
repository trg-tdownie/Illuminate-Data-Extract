#!/bin/bash
#
# Illuminate Weekly Update Script
# Run this every Monday to update assessment data from the past week
#
# To schedule with cron, run: crontab -e
# Then add this line:
# 0 6 * * 1 /home/ubuntu/Illuminate-Data-Extract/run_weekly_update.sh >> /home/ubuntu/Illuminate-Data-Extract/weekly_update.log 2>&1
#
# This runs every Monday at 6:00 AM

cd /home/ubuntu/Illuminate-Data-Extract

echo ""
echo "================================================================================"
echo "Illuminate Weekly Update - $(date)"
echo "================================================================================"
echo ""

# Run the weekly update script
python3 weekly_update.py

EXIT_CODE=$?

echo ""
echo "================================================================================"
echo "Update completed at $(date) with exit code: $EXIT_CODE"
echo "================================================================================"
echo ""

exit $EXIT_CODE
