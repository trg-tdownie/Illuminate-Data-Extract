-- Populate Illuminate_Standards from Assessment Results and GLCE
-- This combines standards from Illuminate assessment results with detailed standard information from GLCE table
--
-- IMPORTANT: Run add_columns_to_standards.sql FIRST
-- to add the GradeLevel, Strand, and Category columns
--
-- Field Mapping from GLCE to Illuminate_Standards:
--   GLCE.GLCE_Code -> StandardCodingNumber (join key)
--   GLCE.Description -> StandardDescription
--   GLCE.ContentArea -> StandardSet
--   GLCE.Subject -> Subject
--   GLCE.GradeLevel -> GradeLevel
--   GLCE.SubjectDesc1 -> Strand
--   GLCE.Type -> Category

PRINT 'Populating Illuminate_Standards from assessment results and GLCE data...'
GO

-- Step 1: Show current state
PRINT 'Current state:'
SELECT COUNT(*) as CurrentStandardsCount FROM Illuminate_Standards;
SELECT COUNT(DISTINCT StandardCodingNumber) as UniqueStandardsInResults
FROM Illuminate_Assessment_Results
WHERE StandardCodingNumber IS NOT NULL;
GO

-- Step 2: Insert unique standards from results table, enriched with GLCE data
-- Uses MERGE to avoid duplicates and update existing records if needed
MERGE Illuminate_Standards AS target
USING (
    SELECT
        StandardCodingNumber,
        StandardDescription,
        StandardSet,
        Subject,
        GradeLevel,
        Strand,
        Category
    FROM (
        SELECT
            r.StandardCodingNumber,
            -- Prefer GLCE description over Illuminate description
            COALESCE(g.Description, r.StandardDescription) as StandardDescription,
            -- Get StandardSet from GLCE ContentArea
            g.ContentArea as StandardSet,
            -- Get Subject from our extracted value or GLCE
            COALESCE(r.Subject, g.Subject) as Subject,
            -- Get additional fields from GLCE
            g.GradeLevel,
            g.SubjectDesc1 as Strand,
            g.[Type] as Category,
            -- Deduplicate by StandardCodingNumber
            ROW_NUMBER() OVER (
                PARTITION BY r.StandardCodingNumber
                ORDER BY r.StandardCodingNumber
            ) as rn
        FROM (
            SELECT DISTINCT
                StandardCodingNumber,
                StandardDescription,
                -- Extract Subject from StandardCodingNumber if Subject is NULL
                CASE
                    WHEN StandardCodingNumber LIKE 'ELA%' THEN 'ELA'
                    WHEN StandardCodingNumber LIKE 'Math%' THEN 'Math'
                    WHEN StandardCodingNumber LIKE 'CCSS.ELA%' THEN 'ELA'
                    WHEN StandardCodingNumber LIKE 'CCSS.Math%' THEN 'Math'
                    ELSE Subject
                END as Subject
            FROM Illuminate_Assessment_Results
            WHERE StandardCodingNumber IS NOT NULL
            AND StandardCodingNumber <> ''
        ) r
        LEFT JOIN LessonPlan_Production.dbo.GLCE g
            ON r.StandardCodingNumber = g.GLCE_Code
    ) deduplicated
    WHERE rn = 1
) AS source
ON (target.StandardCodingNumber = source.StandardCodingNumber)
WHEN MATCHED THEN
    UPDATE SET
        target.StandardDescription = COALESCE(source.StandardDescription, target.StandardDescription),
        target.StandardSet = COALESCE(source.StandardSet, target.StandardSet),
        target.Subject = COALESCE(source.Subject, target.Subject),
        target.GradeLevel = COALESCE(source.GradeLevel, target.GradeLevel),
        target.Strand = COALESCE(source.Strand, target.Strand),
        target.Category = COALESCE(source.Category, target.Category)
WHEN NOT MATCHED THEN
    INSERT (
        StandardCodingNumber,
        StandardDescription,
        StandardSet,
        Subject,
        GradeLevel,
        Strand,
        Category
    )
    VALUES (
        source.StandardCodingNumber,
        source.StandardDescription,
        source.StandardSet,
        source.Subject,
        source.GradeLevel,
        source.Strand,
        source.Category
    );

PRINT CONCAT('Merged standards - Inserted/Updated: ', @@ROWCOUNT, ' records');
GO

-- Step 3: Show results
PRINT 'Results after population:'
SELECT COUNT(*) as TotalStandards FROM Illuminate_Standards;
GO

-- Step 4: Show sample of populated data
PRINT 'Sample of populated standards:'
SELECT TOP 10
    StandardCodingNumber,
    StandardDescription,
    StandardSet,
    Subject,
    GradeLevel,
    Strand
FROM Illuminate_Standards
ORDER BY StandardCodingNumber;
GO

-- Step 5: Show breakdown by subject
PRINT 'Breakdown by Subject:'
SELECT
    Subject,
    COUNT(*) as StandardCount
FROM Illuminate_Standards
WHERE Subject IS NOT NULL
GROUP BY Subject
ORDER BY StandardCount DESC;
GO

-- Step 6: Show enrichment statistics
PRINT 'Enrichment statistics:'
SELECT
    COUNT(*) as TotalStandards,
    SUM(CASE WHEN StandardSet IS NOT NULL THEN 1 ELSE 0 END) as WithStandardSet,
    SUM(CASE WHEN GradeLevel IS NOT NULL THEN 1 ELSE 0 END) as WithGradeLevel,
    SUM(CASE WHEN Strand IS NOT NULL THEN 1 ELSE 0 END) as WithStrand,
    SUM(CASE WHEN Category IS NOT NULL THEN 1 ELSE 0 END) as WithCategory
FROM Illuminate_Standards;
GO

PRINT 'Population complete!'
GO
