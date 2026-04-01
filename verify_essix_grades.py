#!/usr/bin/env python3
"""Verify Essix's students have correct grade levels after update"""
import pyodbc

conn_str = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=10.10.10.200;'
    r'DATABASE=TRG_Dashboard;'
    r'UID=trg-dashboard;'
    r'PWD=qptpP<xf/rv#:5S;'
)

print("Connecting to database...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("\n" + "="*80)
print("ESSIX GRADE LEVEL VERIFICATION")
print("="*80)

# Check current grade distribution for Essix
print("\nGrade distribution for teacher Essix (all data):")
print("-"*80)
cursor.execute("""
    SELECT StudentGrade, COUNT(DISTINCT StudentID_LASID) as UniqueStudents, COUNT(*) as TotalRecords
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
    GROUP BY StudentGrade
    ORDER BY StudentGrade
""")

for row in cursor.fetchall():
    grade = row[0] if row[0] else 'NULL'
    print(f"  Grade {grade}: {row[1]} students, {row[2]} total records")

# Check recent data (last 30 days)
print("\n" + "="*80)
print("Recent assessments for Essix (last 30 days):")
print("-"*80)
cursor.execute("""
    SELECT StudentGrade, COUNT(DISTINCT StudentID_LASID) as UniqueStudents, COUNT(*) as TotalRecords
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
      AND DateCompleted >= DATEADD(day, -30, GETDATE())
    GROUP BY StudentGrade
    ORDER BY StudentGrade
""")

for row in cursor.fetchall():
    grade = row[0] if row[0] else 'NULL'
    print(f"  Grade {grade}: {row[1]} students, {row[2]} total records")

# Show sample students
print("\n" + "="*80)
print("Sample students from Essix (most recent assessments):")
print("-"*80)
cursor.execute("""
    SELECT TOP 10
        LastName + ', ' + FirstName as StudentName,
        StudentGrade,
        AssignmentName,
        DateCompleted,
        SchoolName
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
    ORDER BY DateCompleted DESC
""")

for row in cursor.fetchall():
    print(f"  {row[0]:30s} | Grade: {row[1]:2s} | {row[2]:30s} | {row[3]} | {row[4]}")

# Overall summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

cursor.execute("""
    SELECT
        COUNT(DISTINCT StudentID_LASID) as TotalStudents,
        MIN(DateCompleted) as EarliestAssessment,
        MAX(DateCompleted) as LatestAssessment,
        COUNT(*) as TotalAssessments
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
""")

row = cursor.fetchone()
print(f"\nEssix's Class Statistics:")
print(f"  Total Students: {row[0]}")
print(f"  Total Assessments: {row[3]}")
print(f"  Date Range: {row[1]} to {row[2]}")

# Check if grade 6 students still exist
cursor.execute("""
    SELECT COUNT(DISTINCT StudentID_LASID)
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
      AND StudentGrade = '6'
      AND DateCompleted >= '2025-08-01'
""")

grade_6_count = cursor.fetchone()[0]

print(f"\n" + "="*80)
if grade_6_count > 0:
    print(f"⚠ WARNING: Still {grade_6_count} students showing as grade 6 in current school year!")
    print("The grade levels may not have been updated in Illuminate.")
else:
    print("✓ SUCCESS: No grade 6 students found for Essix in 2025-2026 school year!")
    print("Grade levels appear to be correct.")
print("="*80)

cursor.close()
conn.close()
