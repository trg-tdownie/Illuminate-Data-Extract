#!/usr/bin/env python3
"""Check if grade_level_id needs to be adjusted (K=1, 1st=2, etc.)"""
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
print("GRADE LEVEL ID vs ASSIGNMENT NAME ANALYSIS")
print("="*80)

# Get recent assessments with grade in assignment name
print("\nAnalyzing assignments where name starts with a grade number...")
print("-"*80)

cursor.execute("""
    SELECT TOP 50
        StudentGrade,
        AssignmentName,
        LastName + ', ' + FirstName as StudentName,
        TeacherLastName,
        DateCompleted
    FROM Illuminate_Assessment_Results
    WHERE AssignmentName LIKE '[0-9]%'
        AND DateCompleted >= '2025-08-01'
    ORDER BY AssignmentName, StudentGrade
""")

grade_mapping = {}
for row in cursor.fetchall():
    db_grade = row[0]  # What we have in DB (grade_level_id from Illuminate)
    assignment = row[1]

    # Extract grade from assignment name (first digit(s))
    match = re.match(r'^(\d{1,2})', assignment)
    if match:
        assignment_grade = match.group(1)

        # Track the mapping
        if assignment_grade not in grade_mapping:
            grade_mapping[assignment_grade] = set()
        grade_mapping[assignment_grade].add(db_grade)

        if len(grade_mapping[assignment_grade]) < 3:  # Show first few examples
            print(f"Assignment Grade: {assignment_grade} | DB Grade: {db_grade:2s} | Assignment: {assignment:30s} | {row[2]:25s} | Teacher: {row[3]}")

# Analyze the mapping
print("\n" + "="*80)
print("GRADE MAPPING ANALYSIS")
print("="*80)

sorted_mappings = sorted(grade_mapping.items(), key=lambda x: int(x[0]))
print("\nAssignment Grade -> Database Grade (grade_level_id from Illuminate)")
print("-"*80)

offset_detected = None
for assignment_grade, db_grades in sorted_mappings:
    db_grades_list = sorted(list(db_grades))
    print(f"Grade {assignment_grade} assignments -> Students show as grade: {', '.join(db_grades_list)}")

    # Detect offset
    if len(db_grades_list) == 1:
        db_grade_num = int(db_grades_list[0])
        assignment_grade_num = int(assignment_grade)
        offset = db_grade_num - assignment_grade_num
        if offset_detected is None:
            offset_detected = offset
        print(f"  -> Offset detected: {offset} (DB grade {db_grade_num} - Assignment grade {assignment_grade_num} = {offset})")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)

if offset_detected and offset_detected == 1:
    print("\n✓ CONFIRMED: Illuminate uses grade_level_id where:")
    print("  - Kindergarten = 1")
    print("  - 1st grade = 2")
    print("  - 2nd grade = 3")
    print("  - 3rd grade = 4")
    print("  - 4th grade = 5")
    print("  - 5th grade = 6")
    print("  - etc.")
    print("\nFIX NEEDED: Subtract 1 from grade_level_id to get actual grade number!")
    print("Example: Essix's students have grade_level_id=6, so actual grade = 6-1 = 5")
elif offset_detected:
    print(f"\n⚠ Offset of {offset_detected} detected between grade_level_id and actual grade")
    print("The extraction script needs to be adjusted.")
else:
    print("\n⚠ Unable to determine consistent offset")
    print("Manual review of Illuminate data recommended")

print("="*80)

cursor.close()
conn.close()
