-- Remove Duplicate Records from Illuminate_Assessment_Results
-- Keeps the most recent entry (highest ResultID) for each unique combination
-- of student, assessment, standard, and date

-- Step 1: Check current state
PRINT 'Current record count:';
SELECT COUNT(*) as TotalRecords FROM Illuminate_Assessment_Results;

PRINT 'Checking for duplicates...';
SELECT
    COUNT(*) as TotalRecords,
    COUNT(DISTINCT CONCAT(
        ISNULL(StudentID_LASID, ''), '|',
        ISNULL(CAST(AssessmentID AS VARCHAR), ''), '|',
        ISNULL(StandardCodingNumber, ''), '|',
        ISNULL(CONVERT(VARCHAR, DateCompleted, 120), '')
    )) as UniqueRecords,
    COUNT(*) - COUNT(DISTINCT CONCAT(
        ISNULL(StudentID_LASID, ''), '|',
        ISNULL(CAST(AssessmentID AS VARCHAR), ''), '|',
        ISNULL(StandardCodingNumber, ''), '|',
        ISNULL(CONVERT(VARCHAR, DateCompleted, 120), '')
    )) as DuplicateCount
FROM Illuminate_Assessment_Results;

-- Step 2: Delete duplicates (keep the most recent one based on ResultID)
PRINT 'Removing duplicates...';

WITH CTE_Duplicates AS (
    SELECT
        ResultID,
        ROW_NUMBER() OVER (
            PARTITION BY
                StudentID_LASID,
                AssessmentID,
                StandardCodingNumber,
                DateCompleted
            ORDER BY ResultID DESC  -- Keep the most recent entry
        ) AS RowNum
    FROM Illuminate_Assessment_Results
)
DELETE FROM CTE_Duplicates
WHERE RowNum > 1;

PRINT 'Duplicates removed.';

-- Step 3: Verify results
PRINT 'Final record count:';
SELECT COUNT(*) as TotalRecords FROM Illuminate_Assessment_Results;

PRINT 'Verifying no duplicates remain...';
SELECT
    COUNT(*) as TotalRecords,
    COUNT(DISTINCT CONCAT(
        ISNULL(StudentID_LASID, ''), '|',
        ISNULL(CAST(AssessmentID AS VARCHAR), ''), '|',
        ISNULL(StandardCodingNumber, ''), '|',
        ISNULL(CONVERT(VARCHAR, DateCompleted, 120), '')
    )) as UniqueRecords,
    COUNT(*) - COUNT(DISTINCT CONCAT(
        ISNULL(StudentID_LASID, ''), '|',
        ISNULL(CAST(AssessmentID AS VARCHAR), ''), '|',
        ISNULL(StandardCodingNumber, ''), '|',
        ISNULL(CONVERT(VARCHAR, DateCompleted, 120), '')
    )) as ShouldBeZero
FROM Illuminate_Assessment_Results;

PRINT 'Duplicate removal complete!';
