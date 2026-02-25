"""
Test Teacher and Roster Endpoints
Check what data is available for enriching assessment results with teacher info
"""

from illuminate_extractor import IlluminateAPIExtractor
import json

def test_roster_endpoint():
    """Test /Api/Roster endpoint"""
    print("=" * 80)
    print("Testing /Api/Roster/ endpoint...")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')

    params = {
        'page': 1,
        'limit': 5
    }

    data = extractor._make_api_request('/Api/Roster/', params)

    if data and 'results' in data:
        print(f"\nTotal roster records: {data.get('num_results', 0)}")
        print(f"Number of pages: {data.get('num_pages', 0)}")
        print("\nSample roster data (student-teacher assignments):")
        print("-" * 80)

        for i, record in enumerate(data['results'][:3], 1):
            print(f"\nRecord {i}:")
            print(json.dumps(record, indent=2))
            print("-" * 80)
    else:
        print("No roster data found")

    print("\n")

def test_users_endpoint():
    """Test /Api/Users endpoint"""
    print("=" * 80)
    print("Testing /Api/Users/ endpoint (Teachers)...")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')

    params = {
        'page': 1,
        'limit': 5,
        'role': 'teacher'  # Try to filter for teachers only
    }

    data = extractor._make_api_request('/Api/Users/', params)

    if data and 'results' in data:
        print(f"\nTotal users: {data.get('num_results', 0)}")
        print(f"Number of pages: {data.get('num_pages', 0)}")
        print("\nSample user/teacher data:")
        print("-" * 80)

        for i, user in enumerate(data['results'][:3], 1):
            print(f"\nUser {i}:")
            print(json.dumps(user, indent=2))
            print("-" * 80)
    else:
        print("No user data found")

    print("\n")

def test_students_endpoint():
    """Test /Api/Students endpoint for homeroom teacher"""
    print("=" * 80)
    print("Testing /Api/Students/ endpoint (homeroom teacher info)...")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')

    params = {
        'page': 1,
        'limit': 3
    }

    data = extractor._make_api_request('/Api/Students/', params)

    if data and 'results' in data:
        print(f"\nTotal students: {data.get('num_results', 0)}")
        print("\nSample student data with homeroom teacher:")
        print("-" * 80)

        for i, student in enumerate(data['results'][:3], 1):
            print(f"\nStudent {i}:")
            print(f"  Name: {student.get('first_name')} {student.get('last_name')}")
            print(f"  Student ID: {student.get('district_student_id')}")
            print(f"  Grade Level: {student.get('grade_level')}")
            print(f"  Homeroom Teacher: {student.get('current_homeroom_teacher')}")
            print(f"  Homeroom Teacher ID: {student.get('current_homeroom_teacher_id')}")
            print("-" * 80)
    else:
        print("No student data found")

    print("\n")

def test_master_schedule_endpoint():
    """Test /Api/MasterSchedule endpoint"""
    print("=" * 80)
    print("Testing /Api/MasterSchedule/ endpoint...")
    print("=" * 80)

    extractor = IlluminateAPIExtractor('config.ini')

    params = {
        'page': 1,
        'limit': 3
    }

    data = extractor._make_api_request('/Api/MasterSchedule/', params)

    if data and 'results' in data:
        print(f"\nTotal schedule records: {data.get('num_results', 0)}")
        print(f"Number of pages: {data.get('num_pages', 0)}")
        print("\nSample master schedule data:")
        print("-" * 80)

        for i, record in enumerate(data['results'][:3], 1):
            print(f"\nSchedule Record {i}:")
            print(json.dumps(record, indent=2))
            print("-" * 80)
    else:
        print("No master schedule data found")

    print("\n")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("TEACHER AND ROSTER DATA DISCOVERY")
    print("=" * 80 + "\n")

    # Test all endpoints
    test_roster_endpoint()
    test_users_endpoint()
    test_students_endpoint()
    test_master_schedule_endpoint()

    print("=" * 80)
    print("Testing complete!")
    print("=" * 80)
