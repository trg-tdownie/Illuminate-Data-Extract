# Closed school years: stop re-stamping them, repair them, reload them safely

November 2026. Changes in this repo plus a migration in `dashboard_backend`.

## The problem

Last year's Illuminate results showed this year's grade, school, teacher and section.
Checked read-only on prod (10.10.10.200) on 2026-11-03:

- Every 2025-2026 row for a grade-level test was one grade high: `5.ela.test1` rows said
  `StudentGrade = 6` (10,863 rows), `K.*` said 1, and so on.
- All 2,567 student/subject pairs tested in both years had the same teacher both years, and all
  1,513 students tested in both years had the same grade both years.
- 178,646 of 199,001 2025-2026 rows pointed at a 2026-2027 section.
- The `AcademicYear` labels were already right (fixed in `c0abfdf`, 2026-10-15).

So a 6th-grade teacher picking 2025-2026 on the dashboard saw the 5th-grade tests their current
students took last year, filed as grade 6 under their own name.

## Why

`extract_illuminate_assessment_data` truncated `Illuminate_Assessment_Results` and reloaded every
year from the API on every run, enriching each row from sources that only know the present:

| Field | Source | Covers |
|---|---|---|
| StudentGrade, SchoolID, SchoolName | Illuminate `/Api/Enrollment/`, one record per student | where the student is **now** |
| SectionID, Teacher | `LPC_StudentRoster` | the **current** term only (rebuilt nightly by `nightlyLookupTableBuild`) |
| Teacher (fallback) | Illuminate `/Api/Roster/` | no school year at all |

Every weekly run therefore re-stamped every closed year with the current roster. Students who
changed buildings (5th to 6th, 8th to 9th) also had last year's results under their new school.

## Changes

### 1. Only the current year is reloaded (`illuminate_extractor.py`, `weekly_update.py`)

- `extract_illuminate_assessment_data(..., school_year=None)` reloads one school year, defaulting
  to the current one (7 August rollover, as the dashboard). It deletes just that year's rows
  (`_delete_school_year`, replacing `_truncate_illuminate_tables`) and skips API results from any
  other year. Other years' rows are never touched.
- The old `academic_year` argument is gone. It overrode every row's label, which is how the
  October mislabelling happened. Each row is still labelled by its own `date_taken`.
- `weekly_update.py` rebuilds only that year's `Illuminate_Assessment_Summary` rows. It takes
  `--school-year 2025-2026` to reload a closed year on purpose.
- `illuminate_extractor_incremental.py` no longer stamps one year (rolled over on 1 July) on every
  row.
- `illuminate_extractor.py`'s `main()` takes the year as its first argument.

### 2. Repair of 2024-2025 and 2025-2026 (`dashboard_backend` migration)

`dashboard_backend/scripts/migrations/2026-11-09_illuminate_past_year_enrichment.sql`, with
`..._ROLLBACK.sql`:

- creates the view `dbo.Illuminate_PastYearRoster` (below);
- backs up both years' rows of both tables to `*_BACKUP_20261109_PAST_YEARS`;
- re-derives grade, school, section and teacher for those rows by the rule in 3;
- rebuilds those years' summary rows with the same SELECT as `weekly_update.py`.

Read-only dry run against prod on 2026-11-09:

| | 2025-2026 | 2024-2025 |
|---|---|---|
| rows | 198,191 | 153 |
| grade corrected | 192,599 | 153 |
| teacher changed | 179,128 | 9 |
| school changed | 30,005 | 0 |
| no section found (teacher left blank, not the current one) | 13,345 | 0 |
| no grade on record | 589 | 0 |

After the repair every grade-level test sits in its own grade. The 19 `0.*` rows at grade 1 and 6
`K.*` rows at grade 4 are the same few stray rows the current year has. The school moves are
students going back to last year's building, e.g. 10,665 rows from Merritt Academy Middle School
(5090611) back to Merritt Academy (50906).

### 3. A closed year is enriched from its own records (`illuminate_extractor.py`)

When the year being reloaded isn't the current one, the extractor loads that year's data instead
of the live roster (`_load_past_year_roster`, `_load_past_year_grades`,
`_prepare_past_year_values`). It refuses to start, before deleting anything, if either source is
empty.

| Field | Source |
|---|---|
| StudentGrade | `FiveYearGradeLevel` for that year, by state id (`StudentID_SASID` = `UIC`). 0 → `K`, pre-K → NULL |
| SectionID, Teacher | `dbo.Illuminate_PastYearRoster` for that year (see the rule below). No match → NULL; never the API roster's current teacher |
| SchoolID | the matched section's school; with no section, the school with most of the student's enrollments that year; with none at all, the current school (counted and logged) |

`Illuminate_PastYearRoster` reads `All_Enrollment`:
- **Subject codes** are normalised: `All_Enrollment` keeps PowerSchool's 51-58, while `Enrollment`
  and `LPC_StudentRoster` use 1-8.
- **Term dates** come from that year's copy of the section in `All_Section`. sectionIDs are reused
  across years.
- **Teacher names** come from `All_Teacher`, latest term up to that year. It only has 188 rows
  for 2025-2026, but every PIC has a name in some term.

**Section rule.** Of the student's sections for the test's subject (same SubjectArea /
ContentArea pairs as `subject_sa_map`), take in order:
1. one whose term was in session on the test date, so semester 1 and semester 2 differ;
2. a live enrollment over a dropped one (negative termID);
3. then the lowest ContentArea, SectionID and PIC_Num, just to keep the choice stable.

The migration has the same rule as an `ORDER BY`; change both together.

**How the rule was checked (read-only):**
- **2026-2027, against the live `LPC_StudentRoster`:** same teacher on 5,977 of 6,000 rows, same
  school on all of them.
- **2025-2026, against the year-end snapshot `TRG_Dashboard2526.dbo.LPC_StudentRoster`:** that
  snapshot only covers 598 of the 1,697 students, so it can't be the repair source by itself.
  Every disagreement (1,136 of 6,000) was between two sections both in session on the test date.
  773 of them were co-teachers of one section, where the old import chose arbitrarily too.

### Not changed

- Current-year enrichment is as before (LPC_StudentRoster and the enrollment API), apart from the
  school-year-keyed section lookup, which only ever matches current-year sections.
- `2026-10-13_fix_illuminate_academic_year.sql` never ran on prod (no triggers or backup tables
  exist). The fixed import relabelled the years by itself, so that migration isn't needed.
- The unused legacy paths (`_process_illuminate_assessment_result`, the HMH extract methods) still
  take an `academic_year` override. Nothing calls them.

## Deploying

Order matters: the old import truncates the table, so it would undo the repair on its next run.

1. Deploy this repo to the process server (10.10.10.196, `/home/ubuntu/Illuminate-Data-Extract`)
   **before the next weekly run**.
2. Run `dashboard_backend/scripts/migrations/2026-11-09_illuminate_past_year_enrichment.sql` on
   prod. It takes a few minutes and prints the checks at the end.
3. After the next weekly run, check that 2025-2026 still looks repaired. It should be untouched.

`python3 weekly_update.py --school-year 2025-2026` would also rebuild 2025-2026 by the same rule,
and would pick up any late results. It has no backup or rollback, though, so the migration is the
way to do the one-off repair.
