# Teacher Matching Implementation Plan

## Problem Statement
Currently, the extractor assigns teachers based on the student's roster (homeroom/first teacher), not the actual teacher who administered the assessment. This causes incorrect teacher assignments when students have multiple teachers for different subjects.

## Solution
Use section-based teacher matching by:
1. Storing ALL student roster entries (all classes/sections)
2. Matching assessment subject to student's section for that subject
3. Looking up teacher from existing Section/Teacher tables in database
4. Storing both SectionID and correct teacher name in Illuminate_Assessment_Results

## Implementation Steps

### 1. Database Schema Changes ✓ COMPLETED
- [x] Add `SectionID` column to Illuminate_Assessment_Results table
- [x] Create index on SectionID for performance

### 2. Modify Roster Cache Loading
**File**: `illuminate_extractor.py` - `_load_roster_cache()` method (lines 174-211)

**Current behavior**: Stores only FIRST roster entry per student
```python
if str(district_student_id) not in self.roster_cache:
    self.roster_cache[str(district_student_id)] = {...}  # Only first entry
```

**New behavior**: Store ALL roster entries as a list
```python
if str(district_student_id) not in self.roster_cache:
    self.roster_cache[str(district_student_id)] = []
self.roster_cache[str(district_student_id)].append({
    'user_id': str(record.get('user_id')),
    'section_id': str(record.get('section_id')),
    'course_id': record.get('course_id'),
    'grade_level_id': record.get('grade_level_id'),
    'site_id': record.get('site_id')
})
```

### 3. Load Section/Teacher Mapping from Database
**New method to add**: `_load_section_teacher_cache()`

This will load your Section and Teacher tables into memory for fast lookups:
```python
def _load_section_teacher_cache(self):
    """Load Section -> Teacher mapping from database."""
    cursor = self.db_connection.cursor()
    cursor.execute("""
        SELECT 
            s.sectionID,
            s.SubjectArea,
            s.course_name,
            t.Firstname,
            t.Lastname,
            s.PIC_Num
        FROM Section s
        LEFT JOIN Teacher t ON s.PIC_Num = t.PIC_Num
    """)
    
    for row in cursor.fetchall():
        self.section_cache[str(row[0])] = {
            'subject_area': row[1],
            'course_name': row[2],
            'teacher_first': row[3],
            'teacher_last': row[4],
            'pic_num': row[5]
        }
```

### 4. Create Subject-to-Section Matching Logic
**New method to add**: `_match_section_for_assessment()`

```python
def _match_section_for_assessment(self, student_id, subject):
    """
    Find the correct section for a student based on assessment subject.
    
    Subject mapping:
    - 'ELA' or 'English' -> SubjectArea = 1
    - 'Math' or 'Mathematics' -> SubjectArea = 2  
    - 'Science' -> SubjectArea = 3
    - 'Social Studies' -> SubjectArea = 4
    """
    roster_entries = self.roster_cache.get(str(student_id), [])
    
    # Map assessment subject to SubjectArea code
    subject_map = {
        'ELA': 1,
        'English': 1,
        'Math': 2,
        'Mathematics': 2,
        'Science': 3,
        'Social Studies': 4
    }
    
    target_subject = subject_map.get(subject)
    if not target_subject:
        return None  # Unknown subject
    
    # Find matching section
    for roster in roster_entries:
        section_id = roster.get('section_id')
        if section_id and str(section_id) in self.section_cache:
            section_info = self.section_cache[str(section_id)]
            if section_info.get('subject_area') == target_subject:
                return section_id, section_info
    
    return None, None
```

### 5. Modify Assessment Processing to Use Section Matching
**File**: `illuminate_extractor.py` - `_process_illuminate_standards_result()` method (lines 878-1200)

**Around line 916-923** (where teacher is currently assigned from roster):

**Replace**:
```python
# Enrich with teacher data from roster and users caches
roster_info = self.roster_cache.get(str(local_student_id), {})
teacher_id = roster_info.get('user_id')

# Get teacher info from users cache
teacher_info = self.users_cache.get(str(teacher_id), {}) if teacher_id else {}
teacher_first_name = teacher_info.get('first_name')
teacher_last_name = teacher_info.get('last_name')
```

**With**:
```python
# Match section based on assessment subject
section_id, section_info = self._match_section_for_assessment(local_student_id, subject)

if section_info:
    # Use teacher from matched section
    teacher_first_name = section_info.get('teacher_first')
    teacher_last_name = section_info.get('teacher_last')
else:
    # Fallback to first roster entry if no section match
    roster_entries = self.roster_cache.get(str(local_student_id), [])
    if roster_entries:
        roster_info = roster_entries[0]
        section_id = roster_info.get('section_id')
        teacher_id = roster_info.get('user_id')
        teacher_info = self.users_cache.get(str(teacher_id), {}) if teacher_id else {}
        teacher_first_name = teacher_info.get('first_name')
        teacher_last_name = teacher_info.get('last_name')
    else:
        section_id = None
        teacher_first_name = None
        teacher_last_name = None
```

### 6. Update Database INSERT/UPDATE Statements
**Add SectionID to INSERT/UPDATE queries** (multiple locations):

**Around line 1034-1075** - Add SectionID to MERGE statement:
```sql
MERGE Illuminate_Assessment_Results AS target
...
WHEN MATCHED THEN
    UPDATE SET
        ...
        TeacherLastName = ?,
        TeacherFirstName = ?,
        SectionID = ?,  -- ADD THIS
        ...
WHEN NOT MATCHED THEN
    INSERT (
        ...
        TeacherLastName, TeacherFirstName,
        SectionID,  -- ADD THIS
        ...
    )
    VALUES (?, ?, ?, ...)  -- Add section_id to values
```

### 7. Update _save_illuminate_assessment_summary
**File**: `illuminate_extractor.py` - around line 1432

Add SectionID to summary INSERT as well (if needed for reporting).

### 8. Testing Plan
1. Test with a single assessment (9ELAMod1)
2. Verify correct teachers are assigned
3. Check that SectionID is populated
4. Run full extraction and compare results
5. Verify Summary table is correctly rebuilt

### 9. Backfill Existing Data (Optional)
Create a SQL script to update existing records with correct SectionID and teachers:

```sql
-- Backfill SectionID and correct teachers for existing data
UPDATE iar
SET 
    iar.SectionID = r.section_id,
    iar.TeacherFirstName = t.Firstname,
    iar.TeacherLastName = t.Lastname
FROM Illuminate_Assessment_Results iar
INNER JOIN (
    -- Get Illuminate roster data
    SELECT DISTINCT
        district_student_id,
        section_id
    FROM ... -- Would need to query Illuminate API or cache
) r ON iar.StudentID_LASID = r.district_student_id
INNER JOIN Section s ON r.section_id = s.sectionID
INNER JOIN Teacher t ON s.PIC_Num = t.PIC_Num
WHERE iar.Subject IN ('ELA', 'Math', ...)
  AND s.SubjectArea = CASE 
      WHEN iar.Subject = 'ELA' THEN 1
      WHEN iar.Subject = 'Math' THEN 2
      ...
  END
```

## Estimated Effort
- **Code changes**: 2-3 hours
- **Testing**: 1-2 hours
- **Full re-extraction**: 15-20 minutes
- **Total**: ~4 hours

## Files to Modify
1. `illuminate_extractor.py` - Main extractor logic
2. `weekly_update.py` - Weekly update script (same changes)
3. SQL schema file (already completed)

## Benefits
- ✓ Accurate teacher assignment based on actual class enrollment
- ✓ Links to existing Section/Teacher tables
- ✓ No dependency on Illuminate's limited API data
- ✓ SectionID enables advanced reporting and joins
