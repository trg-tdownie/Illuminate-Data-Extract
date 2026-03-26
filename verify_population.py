#!/usr/bin/env python3
"""Verify Illuminate lookup tables population"""
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

# Get record counts
cursor.execute("SELECT COUNT(*) FROM Illuminate_Assessment_Results")
results_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM Illuminate_Assessment_Summary")
summary_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM Illuminate_Assignments")
assignments_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM Illuminate_Standards")
standards_count = cursor.fetchone()[0]

print("="*80)
print("ILLUMINATE TABLES POPULATION VERIFICATION")
print("="*80)
print()
print("Record Counts:")
print(f"  - Illuminate_Assessment_Results:  {results_count:,} records")
print(f"  - Illuminate_Assessment_Summary:  {summary_count:,} records")
print(f"  - Illuminate_Assignments:         {assignments_count:,} records")
print(f"  - Illuminate_Standards:           {standards_count:,} records")
print()

# Get unique counts from source
cursor.execute("""
    SELECT COUNT(DISTINCT ProgramName + '|' + Component + '|' + AssignmentName)
    FROM Illuminate_Assessment_Results
""")
unique_assignments = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT StandardSet + '|' + StandardCodingNumber)
    FROM Illuminate_Assessment_Results
    WHERE StandardCodingNumber IS NOT NULL
      AND StandardCodingNumber != ''
      AND StandardCodingNumber != 'Overall'
""")
unique_standards = cursor.fetchone()[0]

print("Data Validation:")
print(f"  - Unique assignments in source:  {unique_assignments:,}")
print(f"  - Assignments in lookup table:   {assignments_count:,}")
if assignments_count >= unique_assignments:
    print("    ✓ Assignments lookup table is complete!")
else:
    print(f"    ⚠ Missing {unique_assignments - assignments_count} assignments!")
print()
print(f"  - Unique standards in source:    {unique_standards:,}")
print(f"  - Standards in lookup table:     {standards_count:,}")
if standards_count >= unique_standards:
    print("    ✓ Standards lookup table is complete!")
else:
    print(f"    ⚠ Missing {unique_standards - standards_count} standards!")
print()

# Get date ranges
cursor.execute("""
    SELECT MIN(DateCompleted), MAX(DateCompleted)
    FROM Illuminate_Assessment_Results
""")
row = cursor.fetchone()
if row[0]:
    print(f"Data range: {row[0]} to {row[1]}")

cursor.execute("""
    SELECT MIN(CreatedDate), MAX(CreatedDate)
    FROM Illuminate_Assignments
""")
row = cursor.fetchone()
if row[0]:
    print(f"Illuminate_Assignments created: {row[0]} to {row[1]}")

cursor.execute("""
    SELECT MIN(CreatedDate), MAX(CreatedDate)
    FROM Illuminate_Standards
""")
row = cursor.fetchone()
if row[0]:
    print(f"Illuminate_Standards created: {row[0]} to {row[1]}")
print()

# Sample data
print("Sample Assignments (top 5):")
cursor.execute("""
    SELECT TOP 5 ProgramName, Component, AssignmentName, Subject
    FROM Illuminate_Assignments
    ORDER BY CreatedDate DESC
""")
for row in cursor.fetchall():
    print(f"  - {row[0]} | {row[1]} | {row[2]} | {row[3]}")
print()

print("Sample Standards (top 5):")
cursor.execute("""
    SELECT TOP 5 StandardCodingNumber, LEFT(StandardDescription, 50), Subject
    FROM Illuminate_Standards
    ORDER BY CreatedDate DESC
""")
for row in cursor.fetchall():
    desc = row[1] + '...' if row[1] and len(row[1]) >= 50 else row[1]
    print(f"  - {row[0]} | {desc} | {row[2]}")
print()

# Final status
print("="*80)
if assignments_count > 0 and standards_count > 0 and assignments_count >= unique_assignments and standards_count >= unique_standards:
    print("✓ SUCCESS - All lookup tables populated successfully!")
    print("="*80)
    print()
    print("Summary:")
    print(f"  ✓ {results_count:,} assessment results extracted")
    print(f"  ✓ {assignments_count:,} unique assignments in lookup table")
    print(f"  ✓ {standards_count:,} unique standards in lookup table")
    print(f"  ✓ All data integrity checks passed")
else:
    print("⚠ WARNING - Some issues detected")
    print("="*80)

cursor.close()
conn.close()