#!/bin/bash

################################################################################
# Populate Illuminate Lookup Tables
# This script populates Illuminate_Assignments and Illuminate_Standards tables
# from the extracted assessment results data.
#
# Must be run AFTER illuminate_extractor.py completes successfully.
################################################################################

# SQL Server connection details (modify these for your environment)
SERVER="localhost"
DATABASE="YourDatabaseName"
USE_WINDOWS_AUTH=true  # Set to false if using SQL authentication
SQL_USER=""            # Only needed if USE_WINDOWS_AUTH=false
SQL_PASS=""            # Only needed if USE_WINDOWS_AUTH=false

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "================================================================================"
echo "Illuminate Lookup Tables Population Script"
echo "================================================================================"
echo ""
echo "This will populate:"
echo "  - Illuminate_Assignments (from assessment results)"
echo "  - Illuminate_Standards (from assessment results + GLCE)"
echo ""
echo "Server: $SERVER"
echo "Database: $DATABASE"
echo "================================================================================"
echo ""

# Function to run SQL script
run_sql_script() {
    local script_name=$1
    local description=$2

    echo -e "${BLUE}Running: $description${NC}"
    echo "Script: $script_name"
    echo ""

    if [ "$USE_WINDOWS_AUTH" = true ]; then
        sqlcmd -S "$SERVER" -d "$DATABASE" -E -i "$script_name" -b
    else
        sqlcmd -S "$SERVER" -d "$DATABASE" -U "$SQL_USER" -P "$SQL_PASS" -i "$script_name" -b
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Success: $description completed${NC}"
        echo ""
    else
        echo -e "${RED}✗ Error: $description failed${NC}"
        echo "Please check the error messages above and fix any issues before continuing."
        exit 1
    fi
}

# Step 1: Update unique constraint on Illuminate_Assignments
run_sql_script \
    "update_assignments_unique_constraint.sql" \
    "Step 1/4: Updating Illuminate_Assignments unique constraint"

# Step 2: Populate Illuminate_Assignments from results
run_sql_script \
    "populate_assessments_from_results.sql" \
    "Step 2/4: Populating Illuminate_Assignments table"

# Step 3: Add columns to Illuminate_Standards
run_sql_script \
    "add_columns_to_standards.sql" \
    "Step 3/4: Adding columns to Illuminate_Standards table"

# Step 4: Populate Illuminate_Standards from results and GLCE
run_sql_script \
    "populate_standards_from_results_and_glce.sql" \
    "Step 4/4: Populating Illuminate_Standards table"

echo "================================================================================"
echo -e "${GREEN}All lookup tables populated successfully!${NC}"
echo "================================================================================"
echo ""
echo "Summary:"
echo "  ✓ Illuminate_Assignments - Populated from assessment results"
echo "  ✓ Illuminate_Standards - Populated and enriched with GLCE data"
echo ""
echo "Next steps:"
echo "  - Verify the data in your database"
echo "  - Set up incremental updates using illuminate_extractor_incremental.py"
echo ""
