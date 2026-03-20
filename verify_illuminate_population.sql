-- ============================================================================
-- Illuminate Tables Population Verification Script
-- ============================================================================
-- This script verifies that the population script successfully populated:
--   1. Illuminate_Assignments (lookup table)
--   2. Illuminate_Standards (lookup table)
-- from the source tables:
--   - Illuminate_Assessment_Results
--   - Illuminate_Assessment_Summary
-- ============================================================================

SET NOCOUNT ON;

PRINT '============================================================================';
PRINT 'Illuminate Tables Population Verification';
PRINT '============================================================================';
PRINT '';

-- ============================================================================
-- 1. Check if tables exist
-- ============================================================================
PRINT '1. Checking if required tables exist...';
PRINT '----------------------------------------';

IF OBJECT_ID('Illuminate_Assessment_Results', 'U') IS NOT NULL
    PRINT '   ✓ Illuminate_Assessment_Results exists';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Assessment_Results does NOT exist!';

IF OBJECT_ID('Illuminate_Assessment_Summary', 'U') IS NOT NULL
    PRINT '   ✓ Illuminate_Assessment_Summary exists';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Assessment_Summary does NOT exist!';

IF OBJECT_ID('Illuminate_Assignments', 'U') IS NOT NULL
    PRINT '   ✓ Illuminate_Assignments exists';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Assignments does NOT exist!';

IF OBJECT_ID('Illuminate_Standards', 'U') IS NOT NULL
    PRINT '   ✓ Illuminate_Standards exists';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Standards does NOT exist!';

PRINT '';

-- ============================================================================
-- 2. Check record counts in all tables
-- ============================================================================
PRINT '2. Record counts in all tables:';
PRINT '----------------------------------------';

DECLARE @ResultsCount INT, @SummaryCount INT, @AssignmentsCount INT, @StandardsCount INT;

SELECT @ResultsCount = COUNT(*) FROM Illuminate_Assessment_Results;
SELECT @SummaryCount = COUNT(*) FROM Illuminate_Assessment_Summary;
SELECT @AssignmentsCount = COUNT(*) FROM Illuminate_Assignments;
SELECT @StandardsCount = COUNT(*) FROM Illuminate_Standards;

PRINT '   Source Tables (should have data):';
PRINT '   - Illuminate_Assessment_Results:  ' + CAST(@ResultsCount AS VARCHAR(20)) + ' records';
PRINT '   - Illuminate_Assessment_Summary:  ' + CAST(@SummaryCount AS VARCHAR(20)) + ' records';
PRINT '';
PRINT '   Lookup Tables (populated by script):';
PRINT '   - Illuminate_Assignments:         ' + CAST(@AssignmentsCount AS VARCHAR(20)) + ' records';
PRINT '   - Illuminate_Standards:           ' + CAST(@StandardsCount AS VARCHAR(20)) + ' records';
PRINT '';

-- Warn if lookup tables are empty
IF @AssignmentsCount = 0
    PRINT '   ⚠ WARNING: Illuminate_Assignments is EMPTY!';
IF @StandardsCount = 0
    PRINT '   ⚠ WARNING: Illuminate_Standards is EMPTY!';
PRINT '';

-- ============================================================================
-- 3. Check date ranges to verify recent data
-- ============================================================================
PRINT '3. Data date ranges:';
PRINT '----------------------------------------';

-- Check Illuminate_Assessment_Results date range
IF EXISTS (SELECT 1 FROM Illuminate_Assessment_Results)
BEGIN
    SELECT
        '   Results Data Range:' AS Info,
        MIN(DateCompleted) AS EarliestDate,
        MAX(DateCompleted) AS LatestDate,
        MAX(CreatedDate) AS LastCreatedDate
    FROM Illuminate_Assessment_Results;
END
ELSE
    PRINT '   No data in Illuminate_Assessment_Results';

-- Check Illuminate_Assignments last created
IF EXISTS (SELECT 1 FROM Illuminate_Assignments)
BEGIN
    SELECT
        '   Assignments Lookup:' AS Info,
        MIN(CreatedDate) AS FirstCreated,
        MAX(CreatedDate) AS LastCreated
    FROM Illuminate_Assignments;
END
ELSE
    PRINT '   No data in Illuminate_Assignments';

-- Check Illuminate_Standards last created
IF EXISTS (SELECT 1 FROM Illuminate_Standards)
BEGIN
    SELECT
        '   Standards Lookup:' AS Info,
        MIN(CreatedDate) AS FirstCreated,
        MAX(CreatedDate) AS LastCreated
    FROM Illuminate_Standards;
END
ELSE
    PRINT '   No data in Illuminate_Standards';

PRINT '';

-- ============================================================================
-- 4. Verify Illuminate_Assignments population
-- ============================================================================
PRINT '4. Illuminate_Assignments Verification:';
PRINT '----------------------------------------';

-- Count unique assignments in source data
DECLARE @UniqueAssignmentsInSource INT;
SELECT @UniqueAssignmentsInSource = COUNT(DISTINCT ProgramName + '|' + Component + '|' + AssignmentName)
FROM Illuminate_Assessment_Results;

PRINT '   Unique assignments in source data:  ' + CAST(@UniqueAssignmentsInSource AS VARCHAR(20));
PRINT '   Records in Illuminate_Assignments:  ' + CAST(@AssignmentsCount AS VARCHAR(20));

IF @AssignmentsCount >= @UniqueAssignmentsInSource
    PRINT '   ✓ Population appears successful!';
ELSE IF @AssignmentsCount > 0
    PRINT '   ⚠ WARNING: Fewer assignments than expected!';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Assignments is empty!';

-- Show sample assignments
IF @AssignmentsCount > 0
BEGIN
    PRINT '';
    PRINT '   Sample assignments (top 5):';
    SELECT TOP 5
        AssignmentID,
        ProgramName,
        Component,
        AssignmentName,
        Subject,
        CreatedDate
    FROM Illuminate_Assignments
    ORDER BY CreatedDate DESC;
END

PRINT '';

-- ============================================================================
-- 5. Verify Illuminate_Standards population
-- ============================================================================
PRINT '5. Illuminate_Standards Verification:';
PRINT '----------------------------------------';

-- Count unique standards in source data
DECLARE @UniqueStandardsInSource INT;
SELECT @UniqueStandardsInSource = COUNT(DISTINCT StandardSet + '|' + StandardCodingNumber)
FROM Illuminate_Assessment_Results
WHERE StandardCodingNumber IS NOT NULL
  AND StandardCodingNumber != ''
  AND StandardCodingNumber != 'Overall';

PRINT '   Unique standards in source data:   ' + CAST(@UniqueStandardsInSource AS VARCHAR(20));
PRINT '   Records in Illuminate_Standards:   ' + CAST(@StandardsCount AS VARCHAR(20));

IF @StandardsCount >= @UniqueStandardsInSource
    PRINT '   ✓ Population appears successful!';
ELSE IF @StandardsCount > 0
    PRINT '   ⚠ WARNING: Fewer standards than expected!';
ELSE
    PRINT '   ✗ ERROR: Illuminate_Standards is empty!';

-- Show sample standards
IF @StandardsCount > 0
BEGIN
    PRINT '';
    PRINT '   Sample standards (top 5):';
    SELECT TOP 5
        StandardID,
        StandardSet,
        StandardCodingNumber,
        LEFT(StandardDescription, 50) + '...' AS StandardDescription,
        Subject,
        CreatedDate
    FROM Illuminate_Standards
    ORDER BY CreatedDate DESC;
END

PRINT '';

-- ============================================================================
-- 6. Check for any missing data that should be in lookup tables
-- ============================================================================
PRINT '6. Data Integrity Checks:';
PRINT '----------------------------------------';

-- Check for assignments in results that aren't in lookup table
DECLARE @MissingAssignments INT;
SELECT @MissingAssignments = COUNT(DISTINCT ProgramName + '|' + Component + '|' + AssignmentName)
FROM Illuminate_Assessment_Results r
WHERE NOT EXISTS (
    SELECT 1 FROM Illuminate_Assignments a
    WHERE a.ProgramName = r.ProgramName
      AND a.Component = r.Component
      AND a.AssignmentName = r.AssignmentName
);

IF @MissingAssignments = 0
    PRINT '   ✓ All assignments from results are in lookup table';
ELSE
    PRINT '   ✗ WARNING: ' + CAST(@MissingAssignments AS VARCHAR(20)) + ' assignments missing from lookup table!';

-- Check for standards in results that aren't in lookup table
DECLARE @MissingStandards INT;
SELECT @MissingStandards = COUNT(DISTINCT StandardSet + '|' + StandardCodingNumber)
FROM Illuminate_Assessment_Results r
WHERE StandardCodingNumber IS NOT NULL
  AND StandardCodingNumber != ''
  AND StandardCodingNumber != 'Overall'
  AND NOT EXISTS (
    SELECT 1 FROM Illuminate_Standards s
    WHERE s.StandardSet = r.StandardSet
      AND s.StandardCodingNumber = r.StandardCodingNumber
);

IF @MissingStandards = 0
    PRINT '   ✓ All standards from results are in lookup table';
ELSE
    PRINT '   ✗ WARNING: ' + CAST(@MissingStandards AS VARCHAR(20)) + ' standards missing from lookup table!';

PRINT '';

-- ============================================================================
-- 7. Summary and Recommendations
-- ============================================================================
PRINT '============================================================================';
PRINT 'SUMMARY';
PRINT '============================================================================';

DECLARE @Status VARCHAR(50);

IF @AssignmentsCount > 0 AND @StandardsCount > 0 AND @MissingAssignments = 0 AND @MissingStandards = 0
BEGIN
    SET @Status = '✓ SUCCESS';
    PRINT @Status;
    PRINT '';
    PRINT 'The lookup tables were successfully populated!';
    PRINT '  - Illuminate_Assignments: ' + CAST(@AssignmentsCount AS VARCHAR(20)) + ' assignments';
    PRINT '  - Illuminate_Standards:   ' + CAST(@StandardsCount AS VARCHAR(20)) + ' standards';
    PRINT '  - No missing data detected';
END
ELSE IF @AssignmentsCount > 0 OR @StandardsCount > 0
BEGIN
    SET @Status = '⚠ PARTIAL SUCCESS';
    PRINT @Status;
    PRINT '';
    PRINT 'The lookup tables have some data, but there may be issues:';
    IF @AssignmentsCount = 0
        PRINT '  ✗ Illuminate_Assignments is EMPTY';
    ELSE
        PRINT '  ✓ Illuminate_Assignments: ' + CAST(@AssignmentsCount AS VARCHAR(20)) + ' assignments';

    IF @StandardsCount = 0
        PRINT '  ✗ Illuminate_Standards is EMPTY';
    ELSE
        PRINT '  ✓ Illuminate_Standards: ' + CAST(@StandardsCount AS VARCHAR(20)) + ' standards';

    IF @MissingAssignments > 0
        PRINT '  ⚠ ' + CAST(@MissingAssignments AS VARCHAR(20)) + ' assignments missing from lookup table';
    IF @MissingStandards > 0
        PRINT '  ⚠ ' + CAST(@MissingStandards AS VARCHAR(20)) + ' standards missing from lookup table';

    PRINT '';
    PRINT 'RECOMMENDATION: Review the population script and re-run if needed.';
END
ELSE
BEGIN
    SET @Status = '✗ FAILED';
    PRINT @Status;
    PRINT '';
    PRINT 'The lookup tables are EMPTY! The population script may not have run.';
    PRINT '';
    PRINT 'RECOMMENDATION: Run populate_lookup_tables.py to populate the tables.';
END

PRINT '';
PRINT '============================================================================';
