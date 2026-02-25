-- Fix schema to allow NULL values for fields not provided by API
-- The /Api/AssessmentAggregateStudentResponsesStandard/ endpoint doesn't return all fields

ALTER TABLE Illuminate_Assessment_Results
ALTER COLUMN SchoolName VARCHAR(200) NULL;

ALTER TABLE Illuminate_Assessment_Results
ALTER COLUMN AcademicYear VARCHAR(20) NULL;

ALTER TABLE Illuminate_Assessment_Summary
ALTER COLUMN SchoolName VARCHAR(200) NULL;

ALTER TABLE Illuminate_Assessment_Summary
ALTER COLUMN AcademicYear VARCHAR(20) NULL;
