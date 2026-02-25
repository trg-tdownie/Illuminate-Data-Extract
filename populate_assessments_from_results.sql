-- Populate Illuminate_Assignments from Illuminate_Assessment_Results
-- This extracts unique assessments from the results data
--
-- IMPORTANT: Run update_assignments_unique_constraint.sql FIRST
-- to update the unique constraint to include SchoolID
-- This allows the same assessment name to exist for different schools

PRINT 'Populating Illuminate_Assignments from assessment results data...'
GO

-- Step 1: Show current state
PRINT 'Current state:'
SELECT COUNT(*) as CurrentAssignmentsCount FROM Illuminate_Assignments;
SELECT COUNT(DISTINCT AssessmentID) as UniqueAssessmentsInResults FROM Illuminate_Assessment_Results WHERE AssessmentID IS NOT NULL;
GO

-- Step 2: Insert unique assessments from results table
-- Creates separate entries for the same assessment at different schools
-- Uses MERGE to avoid duplicates and update existing records if needed
MERGE Illuminate_Assignments AS target
USING (
    SELECT
        AssessmentID,
        AssignmentName,
        Subject,
        ProgramName,
        Publisher,
        Component,
        SchoolID
    FROM (
        SELECT
            AssessmentID,
            AssignmentName,
            Subject,
            ProgramName,
            Publisher,
            Component,
            SchoolID,
            -- Deduplicate by the unique constraint columns (ProgramName, Component, AssignmentName, SchoolID)
            -- This prevents inserting multiple assessments with the same unique key
            ROW_NUMBER() OVER (
                PARTITION BY
                    COALESCE(ProgramName, ''),
                    COALESCE(Component, ''),
                    COALESCE(AssignmentName, ''),
                    SchoolID
                ORDER BY AssessmentID
            ) as rn
        FROM (
            SELECT DISTINCT
                AssessmentID,
                AssignmentName,
                -- Extract Subject from StandardCodingNumber if Subject is NULL
                -- Examples: "ELA-Literacy.RL.3.5" -> "ELA", "Math.1.OA.1" -> "Math"
                COALESCE(
                    Subject,
                    CASE
                        WHEN StandardCodingNumber LIKE 'ELA%' THEN 'ELA'
                        WHEN StandardCodingNumber LIKE 'Math%' THEN 'Math'
                        WHEN StandardCodingNumber LIKE 'CCSS.ELA%' THEN 'ELA'
                        WHEN StandardCodingNumber LIKE 'CCSS.Math%' THEN 'Math'
                        ELSE NULL
                    END
                ) as Subject,
                ProgramName,
                Publisher,
                Component,
                SchoolID
            FROM Illuminate_Assessment_Results
            WHERE AssessmentID IS NOT NULL
            AND SchoolID IS NOT NULL  -- Only include records with SchoolID
        ) r1
    ) deduplicated
    WHERE rn = 1
) AS source
ON (
    ISNULL(target.ProgramName, '') = ISNULL(source.ProgramName, '')
    AND ISNULL(target.Component, '') = ISNULL(source.Component, '')
    AND ISNULL(target.AssignmentName, '') = ISNULL(source.AssignmentName, '')
    AND target.SchoolID = source.SchoolID
)
WHEN MATCHED THEN
    UPDATE SET
        target.AssignmentName = COALESCE(source.AssignmentName, target.AssignmentName),
        target.Subject = COALESCE(source.Subject, target.Subject),
        target.ProgramName = COALESCE(source.ProgramName, target.ProgramName),
        target.Publisher = COALESCE(source.Publisher, target.Publisher),
        target.Component = COALESCE(source.Component, target.Component),
        target.SchoolID = COALESCE(source.SchoolID, target.SchoolID)
WHEN NOT MATCHED THEN
    INSERT (
        IlluminateAssessmentID,
        AssignmentName,
        Subject,
        ProgramName,
        Publisher,
        Component,
        SchoolID
    )
    VALUES (
        source.AssessmentID,
        source.AssignmentName,
        source.Subject,
        source.ProgramName,
        source.Publisher,
        source.Component,
        source.SchoolID
    );

PRINT CONCAT('Merged assignments - Inserted/Updated: ', @@ROWCOUNT, ' records');
GO

-- Step 3: Show results
PRINT 'Results after population:'
SELECT COUNT(*) as TotalAssignments FROM Illuminate_Assignments;
GO

-- Step 4: Show sample of populated data
PRINT 'Sample of populated assignments:'
SELECT TOP 10
    AssignmentID,
    IlluminateAssessmentID,
    AssignmentName,
    Subject,
    ProgramName,
    Component,
    SchoolID
FROM Illuminate_Assignments
ORDER BY AssignmentID DESC;
GO

-- Step 5: Show breakdown by program/subject
PRINT 'Breakdown by Program and Subject:'
SELECT
    ProgramName,
    Subject,
    COUNT(*) as AssignmentCount
FROM Illuminate_Assignments
WHERE ProgramName IS NOT NULL OR Subject IS NOT NULL
GROUP BY ProgramName, Subject
ORDER BY AssignmentCount DESC;
GO

PRINT 'Population complete!'
GO
