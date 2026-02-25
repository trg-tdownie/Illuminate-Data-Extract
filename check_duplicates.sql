-- Check for duplicate records in Illuminate_Assessment_Results
-- A duplicate would be same student, same assessment, same standard, same date

SELECT 
    COUNT(*) as TotalRecords,
    COUNT(DISTINCT CONCAT(StudentID_LASID, '|', AssessmentID, '|', StandardCodingNumber, '|', DateCompleted)) as UniqueRecords,
    COUNT(*) - COUNT(DISTINCT CONCAT(StudentID_LASID, '|', AssessmentID, '|', StandardCodingNumber, '|', DateCompleted)) as DuplicateCount
FROM Illuminate_Assessment_Results;

-- Show some examples of duplicates if they exist
SELECT 
    StudentID_LASID,
    FirstName,
    LastName,
    SchoolName,
    AssessmentID,
    AssignmentName,
    StandardCodingNumber,
    DateCompleted,
    COUNT(*) as Occurrences
FROM Illuminate_Assessment_Results
GROUP BY 
    StudentID_LASID,
    FirstName,
    LastName,
    SchoolName,
    AssessmentID,
    AssignmentName,
    StandardCodingNumber,
    DateCompleted
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC;
