-- Add missing columns to Illuminate_Standards table
-- These columns will be populated from the GLCE table

PRINT 'Adding missing columns to Illuminate_Standards table...'
GO

-- Add GradeLevel column
IF NOT EXISTS (SELECT * FROM sys.columns
               WHERE object_id = OBJECT_ID('Illuminate_Standards')
               AND name = 'GradeLevel')
BEGIN
    ALTER TABLE Illuminate_Standards
    ADD GradeLevel NVARCHAR(2) NULL;

    PRINT 'Added GradeLevel column';
END
ELSE
BEGIN
    PRINT 'GradeLevel column already exists';
END
GO

-- Add Strand column
IF NOT EXISTS (SELECT * FROM sys.columns
               WHERE object_id = OBJECT_ID('Illuminate_Standards')
               AND name = 'Strand')
BEGIN
    ALTER TABLE Illuminate_Standards
    ADD Strand NVARCHAR(MAX) NULL;

    PRINT 'Added Strand column';
END
ELSE
BEGIN
    PRINT 'Strand column already exists';
END
GO

-- Add Category column
IF NOT EXISTS (SELECT * FROM sys.columns
               WHERE object_id = OBJECT_ID('Illuminate_Standards')
               AND name = 'Category')
BEGIN
    ALTER TABLE Illuminate_Standards
    ADD Category NVARCHAR(50) NULL;

    PRINT 'Added Category column';
END
ELSE
BEGIN
    PRINT 'Category column already exists';
END
GO

-- Show updated table structure
PRINT 'Updated Illuminate_Standards structure:'
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Illuminate_Standards'
ORDER BY ORDINAL_POSITION;
GO

PRINT 'Column additions complete!'
GO
