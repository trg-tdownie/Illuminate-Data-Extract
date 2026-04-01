#!/usr/bin/env python3
"""Check grade level issues in Illuminate data"""
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

# Check Essix students - look for teacher Essix with grade issues
print("\n" + "="*80)
print("Checking for teacher Essix students:")
print("="*80)
cursor.execute("""
    SELECT DISTINCT TeacherLastName, TeacherFirstName, StudentGrade, COUNT(*) as StudentCount
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
    GROUP BY TeacherLastName, TeacherFirstName, StudentGrade
    ORDER BY StudentGrade
""")

for row in cursor.fetchall():
    print(f"Teacher: {row[0]}, {row[1]} | Grade: {row[2]} | Records: {row[3]}")

print("\n" + "="*80)
print("Sample recent records for Essix:")
print("="*80)
cursor.execute("""
    SELECT TOP 10
        LastName, FirstName, StudentGrade,
        AssignmentName, DateCompleted, SchoolName
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
    ORDER BY DateCompleted DESC
""")

for row in cursor.fetchall():
    print(f"{row[0]}, {row[1]} | Grade: {row[2]} | Assignment: {row[3]} | Date: {row[4]} | School: {row[5]}")

# Check grade distribution across all teachers
print("\n" + "="*80)
print("Grade distribution for recent assessments (last 35 days):")
print("="*80)
cursor.execute("""
    SELECT StudentGrade, COUNT(*) as RecordCount, COUNT(DISTINCT StudentID_LASID) as UniqueStudents
    FROM Illuminate_Assessment_Results
    WHERE DateCompleted >= DATEADD(day, -35, GETDATE())
    GROUP BY StudentGrade
    ORDER BY StudentGrade
""")

for row in cursor.fetchall():
    grade = row[0] if row[0] else 'NULL'
    print(f"Grade: {grade:6s} | Records: {row[1]:5,} | Unique Students: {row[2]:4}")

# Check what Illuminate API says about grade levels for recent data
print("\n" + "="*80)
print("Checking grade consistency for specific students:")
print("="*80)
cursor.execute("""
    SELECT DISTINCT TOP 5
        StudentID_LASID,
        LastName + ', ' + FirstName as StudentName,
        StudentGrade,
        TeacherLastName + ', ' + TeacherFirstName as TeacherName,
        SchoolName
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
        AND DateCompleted >= DATEADD(day, -35, GETDATE())
    ORDER BY LastName, FirstName
""")

essix_students = []
for row in cursor.fetchall():
    essix_students.append({
        'lasid': row[0],
        'name': row[1],
        'current_grade': row[2],
        'teacher': row[3],
        'school': row[4]
    })
    print(f"LASID: {row[0]} | {row[1]} | Current Grade in DB: {row[2]} | Teacher: {row[3]}")

# Now check the Enrollment API cache to see what grade is coming from Illuminate
print("\n" + "="*80)
print("Note: The script pulls grades from Illuminate's Enrollment API.")
print("If students show as 6th grade but are actually 5th grade, this means:")
print("  1. Illuminate's enrollment data hasn't been updated for 2025-2026")
print("  2. Or the grade_level field in Illuminate is incorrect")
print("="*80)

cursor.close()
conn.close()
