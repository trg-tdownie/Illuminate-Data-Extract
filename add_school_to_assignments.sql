-- Add SchoolID column to Illuminate_Assignments table
-- This will store the school(s) where each assessment is used

-- Step 1: Add the column if it doesn't exist
IF NOT EXISTS (SELECT * FROM sys.columns
               WHERE object_id = OBJECT_ID('Illuminate_Assignments')
               AND name = 'SchoolID')
BEGIN
    ALTER TABLE Illuminate_Assignments
    ADD SchoolID INT NULL;

    PRINT 'Added SchoolID column to Illuminate_Assignments';
END
ELSE
BEGIN
    PRINT 'SchoolID column already exists';
END
GO

-- Step 2: Update SchoolID based on assessment results data
-- For assessments used in multiple schools, this will pick one school
-- (the one with the most recent assessment result)
UPDATE a
SET a.SchoolID = sub.SchoolID
FROM Illuminate_Assignments a
INNER JOIN (
    SELECT
        AssessmentID,
        SchoolID,
        ROW_NUMBER() OVER (PARTITION BY AssessmentID ORDER BY DateCompleted DESC) as rn
    FROM Illuminate_Assessment_Results
    WHERE AssessmentID IS NOT NULL
    AND SchoolID IS NOT NULL
) sub ON a.IlluminateAssessmentID = sub.AssessmentID
WHERE sub.rn = 1;

PRINT 'Updated SchoolID for assignments based on assessment results';

-- Step 3: Verify the update
SELECT
    COUNT(*) as TotalAssignments,
    COUNT(SchoolID) as AssignmentsWithSchool,
    COUNT(*) - COUNT(SchoolID) as AssignmentsWithoutSchool
FROM Illuminate_Assignments;

-- Step 4: Show which schools use which assessments
SELECT
    a.AssignmentName,
    a.ProgramName,
    a.SchoolID,
    s.site_name as SchoolName,
    COUNT(DISTINCT r.StudentID_LASID) as NumStudents,
    MAX(r.DateCompleted) as MostRecentUse
FROM Illuminate_Assignments a
LEFT JOIN Illuminate_Assessment_Results r ON a.IlluminateAssessmentID = r.AssessmentID
LEFT JOIN (
    -- Get school names from Sites cache or create a temp table
    SELECT DISTINCT SchoolID, SchoolName as site_name
    FROM Illuminate_Assessment_Results
    WHERE SchoolID IS NOT NULL
) s ON a.SchoolID = s.SchoolID
GROUP BY a.AssignmentName, a.ProgramName, a.SchoolID, s.site_name
ORDER BY a.AssignmentName;
