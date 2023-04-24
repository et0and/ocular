import os.path
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
import dateutil.parser
import sys
import time
import threading
from termcolor import colored

# Scopes for the Google Classroom API
SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly',
          'https://www.googleapis.com/auth/classroom.rosters.readonly',
          'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly']

# Function to authenticate and create the API client
def create_api_client():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('classroom', 'v1', credentials=creds)

def list_courses():
    try:
        api_client = create_api_client()
        courses = api_client.courses().list(courseStates=['ACTIVE']).execute()
        return courses.get('courses', [])
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []
    
def list_course_work(course_id):
    try:
        api_client = create_api_client()
        course_work = api_client.courses().courseWork().list(courseId=course_id).execute()
        return course_work.get('courseWork', [])
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []
    
def get_course_role(course_id):
    try:
        api_client = create_api_client()
        user_profile = api_client.userProfiles().get(userId='me').execute()
        my_id = user_profile['id']
        teacher = api_client.courses().teachers().get(courseId=course_id, userId=my_id).execute()
        if teacher:
            return 'TEACHER'
    except HttpError as error:
        if error.resp.status == 404:
            return 'STUDENT'
        else:
            print(f"An error occurred: {error}")
            return None
        
def spinner_animation():
    spinner = "|/-\\"
    i = 0
    while spinner_active:
        sys.stdout.write("\r" + colored("Ocular is thinking... ", "green", attrs=['bold']) + spinner[i % len(spinner)])
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)

# Function to get students
def get_students(course_id):
    try:
        api_client = create_api_client()
        students = api_client.courses().students().list(courseId=course_id).execute()
        return students.get('students', [])
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

# Function to get coursework submissions
def get_submissions(course_id, assignment_id):
    try:
        api_client = create_api_client()
        submissions = api_client.courses().courseWork().studentSubmissions().list(courseId=course_id, courseWorkId=assignment_id).execute()
        return submissions.get('studentSubmissions', [])
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

# Function to get last update time for a Google Slides attachment
def get_last_update_time(submission):
    attachments = submission.get('assignmentSubmission', {}).get('attachments', [])
    last_update_time = None
    is_turned_in = submission.get('state') == 'TURNED_IN'

    for attachment in attachments:
        if 'driveFile' in attachment:
            drive_file = attachment['driveFile']
            file_title = drive_file['title']

            if '.gslides' in file_title:
                update_time = dateutil.parser.parse(drive_file['updateTime'])
                if not last_update_time or update_time > last_update_time:
                    last_update_time = update_time

    if last_update_time:
        return last_update_time.strftime('%Y-%m-%d %H:%M:%S'), is_turned_in
    else:
        return None, is_turned_in

def main():
    # Define the global variable to control the spinner
    global spinner_active

    # Start the spinner animation on a separate thread
    spinner_active = True
    spinner_thread = threading.Thread(target=spinner_animation)
    spinner_thread.start()

    # Fetch and display courses
    courses = list_courses()

    # Stop the spinner animation
    spinner_active = False
    spinner_thread.join()
    sys.stdout.write("\r" + colored("Here are your classes ↴", "green", attrs=['bold']) + " " * 30 + "\n")

    course_id_map = {}
    course_work_cache = {}  # Cache for course works

    for course in courses:
        course_id = course['id']
        course_name = course['name']
        course_role = get_course_role(course_id)

        if course_role == 'TEACHER':
            print(f"{course_name} ID: {colored(course_id, attrs=['bold'])}")
            course_id_map[course_id] = course_name

    while True:
        # Ask for user input for course ID
        user_course_id = input(colored("Enter course ID: ", "green", attrs=['bold']))

        if user_course_id in course_id_map:
            # Fetch and display assignments for the chosen course
            if user_course_id not in course_work_cache:
                course_work_cache[user_course_id] = list_course_work(user_course_id)

            course_work_list = course_work_cache[user_course_id]
            for course_work in course_work_list:
                assignment_id = course_work['id']
                assignment_title = course_work['title']
                print(f"  {assignment_title} ID: {colored(assignment_id, attrs=['bold'])}")
            print()

            # Ask for user input for assignment ID
            user_assignment_id = input(colored("Enter assignment ID: ", "green", attrs=['bold']))

            # Fetch and display the turn-in status for the specified course and assignment
            students = get_students(user_course_id)
            submissions = get_submissions(user_course_id, user_assignment_id)

            for student in students:
                student_id = student['userId']
                student_name = f"{student['profile']['name']['givenName']} {student['profile']['name']['familyName']}"

                for submission in submissions:
                    if submission['userId'] == student_id:
                        is_turned_in = submission.get('state') == 'TURNED_IN'
                        turn_in_status = 'turned in' if is_turned_in else 'not turned in'
                        turn_in_state = '😀' if is_turned_in else '💀'
                        print(f"    {colored(student_name, 'cyan', attrs=['bold'])} has {colored(turn_in_status, attrs=['bold'])} this assignment {turn_in_state}")

            # Ask the user if they want to look at another class
            another_class = input(colored("Do you want to look at another class? (Yes/No): ", "green", attrs=['bold']))
            if another_class.lower() == 'no':
                print(colored("Bye!", "green", attrs=['bold']))
                break
            else:
                print(colored("Returning to class lists...", "green", attrs=['bold']))
                for course_id in course_id_map:
                    print(f"{course_id_map[course_id]}: {course_id}")
        else:
            print("Invalid course ID. Try again.")

if __name__ == '__main__':
    main()