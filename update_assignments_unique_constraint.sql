-- Update Unique Constraint on Illuminate_Assignments to Include SchoolID
-- This allows the same assessment name to exist for different schools

PRINT 'Updating unique constraint on Illuminate_Assignments to include SchoolID...'
GO

-- Step 1: Drop the existing unique constraint
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'UQ_Illuminate_Assignment' AND object_id = OBJECT_ID('Illuminate_Assignments'))
BEGIN
    ALTER TABLE Illuminate_Assignments
    DROP CONSTRAINT UQ_Illuminate_Assignment;

    PRINT 'Dropped existing unique constraint: UQ_Illuminate_Assignment';
END
ELSE
BEGIN
    PRINT 'Constraint UQ_Illuminate_Assignment does not exist.';
END
GO

-- Step 2: Create new unique constraint that includes SchoolID
-- This allows the same ProgramName/Component/AssignmentName at different schools
ALTER TABLE Illuminate_Assignments
ADD CONSTRAINT UQ_Illuminate_Assignment
UNIQUE (ProgramName, Component, AssignmentName, SchoolID);

PRINT 'Created new unique constraint including SchoolID';
PRINT 'Same assessment names can now exist for different schools';
GO

-- Step 3: Show the new constraint
SELECT
    i.name AS ConstraintName,
    COL_NAME(ic.object_id, ic.column_id) AS ColumnName,
    ic.key_ordinal AS ColumnOrder
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
WHERE i.name = 'UQ_Illuminate_Assignment'
AND i.object_id = OBJECT_ID('Illuminate_Assignments')
ORDER BY ic.key_ordinal;
GO

PRINT 'Constraint update complete!'
GO
