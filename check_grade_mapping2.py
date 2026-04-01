#!/usr/bin/env python3
"""Check grade_level_id mapping with better logic"""
import pyodbc
import re

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
print("GRADE LEVEL ID vs ASSIGNMENT NAME - DETAILED ANALYSIS")
print("="*80)

# Focus on grades 1-12 for clearer pattern
for target_grade in range(1, 13):
    cursor.execute(f"""
        SELECT TOP 5
            StudentGrade,
            AssignmentName,
            LastName + ', ' + FirstName as StudentName,
            SchoolName
        FROM Illuminate_Assessment_Results
        WHERE AssignmentName LIKE '{target_grade}%'
            AND DateCompleted >= '2025-08-01'
        ORDER BY NEWID()
    """)

    results = cursor.fetchall()
    if results:
        print(f"\n{target_grade}st/nd/rd/th Grade Assignments:")
        print("-" * 80)
        db_grades = set()
        for row in results:
            db_grade = row[0]
            db_grades.add(db_grade)
            print(f"  DB Grade: {db_grade:2s} | {row[1]:35s} | {row[2]:25s} | {row[3]}")

        # Check offset
        if len(db_grades) == 1:
            db_grade_num = int(list(db_grades)[0])
            offset = db_grade_num - target_grade
            print(f"  ✓ Consistent: All students show as grade {db_grade_num} (offset: {offset:+d})")
        else:
            print(f"  ⚠ Inconsistent: Students show as grades: {', '.join(sorted(db_grades))}")

# Now check specifically Essix's 5th grade assignments
print("\n" + "="*80)
print("ESSIX'S STUDENTS - 5th GRADE ASSIGNMENTS")
print("="*80)
cursor.execute("""
    SELECT TOP 10
        StudentGrade,
        AssignmentName,
        LastName + ', ' + FirstName as StudentName,
        DateCompleted
    FROM Illuminate_Assessment_Results
    WHERE TeacherLastName LIKE '%Essix%'
        AND AssignmentName LIKE '5%'
        AND DateCompleted >= '2025-08-01'
    ORDER BY DateCompleted DESC
""")

for row in cursor.fetchall():
    print(f"  DB Grade: {row[0]:2s} | {row[1]:35s} | {row[2]:25s} | {row[3]}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("\nIf students taking '5Math' assignments show as grade 6 in the database,")
print("then grade_level_id from Illuminate is shifted by +1")
print("(K=1, 1st=2, 2nd=3, 3rd=4, 4th=5, 5th=6, etc.)")

cursor.close()
conn.close()
