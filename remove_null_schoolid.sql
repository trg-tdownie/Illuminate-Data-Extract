-- Remove Records with Null SchoolID from Illuminate_Assessment_Results
-- This cleans up existing data where we can't determine which school the assessment belongs to

-- Step 1: Check how many records have NULL SchoolID
PRINT 'Checking for records with NULL SchoolID...'
GO

SELECT
    COUNT(*) as RecordsWithNullSchoolID
FROM Illuminate_Assessment_Results
WHERE SchoolID IS NULL;

-- Step 2: Show sample of records that will be deleted (first 10)
PRINT 'Sample of records that will be deleted:'
GO

SELECT TOP 10
    ResultID,
    StudentID_LASID,
    LastName,
    FirstName,
    AssignmentName,
    DateCompleted,
    SchoolName,
    SchoolID
FROM Illuminate_Assessment_Results
WHERE SchoolID IS NULL
ORDER BY DateCompleted DESC;

-- Step 3: Delete records with NULL SchoolID
PRINT 'Deleting records with NULL SchoolID...'
GO

BEGIN TRANSACTION;

DELETE FROM Illuminate_Assessment_Results
WHERE SchoolID IS NULL;

-- Show how many were deleted
PRINT CONCAT('Deleted ', @@ROWCOUNT, ' records with NULL SchoolID');

-- If you're satisfied with the deletion, commit the transaction
-- If something looks wrong, you can rollback instead
COMMIT TRANSACTION;
-- To rollback instead: ROLLBACK TRANSACTION;

GO

-- Step 4: Verify deletion
PRINT 'Verification - Records with NULL SchoolID remaining:'
GO

SELECT
    COUNT(*) as RecordsWithNullSchoolID
FROM Illuminate_Assessment_Results
WHERE SchoolID IS NULL;

-- Step 5: Show total remaining records
SELECT
    COUNT(*) as TotalRecordsRemaining
FROM Illuminate_Assessment_Results;

PRINT 'Cleanup complete!'
GO
