import streamlit as st
import mysql.connector
import pandas as pd
from datetime import datetime, date
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Faculty Attendance Portal",
    page_icon="👨‍🏫",
    layout="wide"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'faculty_id' not in st.session_state:
    st.session_state.faculty_id = None
if 'faculty_name' not in st.session_state:
    st.session_state.faculty_name = None

def get_db_connection():
    #Establish a connection to the MySQL database.
    try:
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', 'tiger'),
            database=os.getenv('DB_NAME', 'dbms')
        )
    except mysql.connector.Error as err:
        st.error(f"Error connecting to MySQL: {err}")
        return None

def execute_query(query, params=None, fetch=True):
    #Execute a database query and handle connection cleanup.
    connection = get_db_connection()
    if not connection:
        return None
        
    try:
        cursor = connection.cursor()
        cursor.execute(query, params or ())
        if fetch:
            result = cursor.fetchall()
        else:
            result = None
            connection.commit()
        return result
    except mysql.connector.Error as err:
        st.error(f"Database error: {err}")
        return None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

def login_page():
    #Display the login page and handle authentication.
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>" * 4, unsafe_allow_html=True)
        with st.container():
            st.markdown(
                """
                <div style='text-align: center;'>
                    <h1 style='color: #0066cc;'>👨‍🏫</h1>
                    <h2 style='color: #0066cc;'>Faculty Attendance Portal</h2>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    submit = st.form_submit_button("Login", use_container_width=True)
                
                if submit:
                    if username and password:
                        result = execute_query(
                            """
                            SELECT Faculty_ID, CONCAT(First_name, ' ', Last_name) as name 
                            FROM faculty 
                            WHERE Username = %s AND Password = %s
                            """,
                            (username, password)
                        )
                        
                        if result and result[0]:
                            st.session_state.logged_in = True
                            st.session_state.faculty_id = result[0][0]
                            st.session_state.faculty_name = result[0][1]
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                    else:
                        st.error("Please enter both username and password")

def logout():
    #Handle user logout.
    st.session_state.logged_in = False
    st.session_state.faculty_id = None
    st.session_state.faculty_name = None
    st.rerun()

def get_all_semesters():
    #Retrieve all available semesters.
    result = execute_query(
        """
        SELECT Sem_ID, CONCAT('Year ', Year, ' - Term ', Term) as semester_name
        FROM semester 
        ORDER BY Sem_ID
        """
    )
    return result if result else []

def get_current_semester():
    #Get the current semester and handle semester selection.
    semesters = get_all_semesters()
    if not semesters:
        return None, None
        
    # Create a dictionary for semester selection
    semester_options = {name: sem_id for sem_id, name in semesters}
    
    # Add semester selection to session state if not exists
    if 'selected_semester' not in st.session_state:
        st.session_state.selected_semester = list(semester_options.keys())[0]
        
    # Display semester selector in sidebar
    with st.sidebar:
        selected_semester_name = st.selectbox(
            "Select Semester",
            options=list(semester_options.keys()),
            index=list(semester_options.keys()).index(st.session_state.selected_semester)
        )
        st.session_state.selected_semester = selected_semester_name
        
    # Get the selected semester details
    result = execute_query(
        """
        SELECT Sem_ID, CONCAT('Year ', Year, ' - Term ', Term) as semester_name
        FROM semester 
        WHERE Sem_ID = %s
        LIMIT 1
        """,
        (semester_options[selected_semester_name],)
    )
    return result[0] if result else (None, None)

def get_faculty_courses(sem_id):
    #Get courses assigned to the faculty for a given semester.
    return execute_query(
        """
        SELECT c.Code, c.Title
        FROM course_allot ca
        JOIN course c ON ca.Code = c.Code
        WHERE ca.Faculty_ID = %s AND ca.Sem_ID = %s
        """,
        (st.session_state.faculty_id, sem_id)
    )

def show_dashboard():
    #Display the faculty dashboard.
    st.subheader(f"Welcome, {st.session_state.faculty_name}")
    
    current_sem_id, semester_name = get_current_semester()
    if not current_sem_id:
        st.error("No semester data found")
        return
    
    st.write(f"Current Semester: {semester_name}")
    
    courses = get_faculty_courses(current_sem_id)
    if courses:
        st.subheader("Your Courses")
        for code, title in courses:
            with st.expander(f"{code} - {title}"):
                # Get today's attendance summary
                result = execute_query(
                    """
                    SELECT 
                        COUNT(CASE WHEN Status = 'Present' THEN 1 END) as present,
                        COUNT(CASE WHEN Status = 'Absent' THEN 1 END) as absent,
                        COUNT(CASE WHEN Status = 'Unmarked' THEN 1 END) as unmarked
                    FROM attendance
                    WHERE Faculty_ID = %s 
                    AND Sem_ID = %s 
                    AND Code = %s
                    AND Date = CURDATE()
                    """,
                    (st.session_state.faculty_id, current_sem_id, code)
                )
                
                if result and result[0]:
                    summary = result[0]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Present", summary[0])
                    with col2:
                        st.metric("Absent", summary[1])
                    with col3:
                        st.metric("Unmarked", summary[2])
    else:
        st.info("No courses assigned for the current semester")

def mark_attendance():
    #Handle attendance marking for faculty.
    st.subheader("Mark Attendance")
    
    current_sem_id, semester_name = get_current_semester()
    if not current_sem_id:
        st.error("No semester data found")
        return
    
    courses = get_faculty_courses(current_sem_id)
    if not courses:
        st.info("No courses assigned for the current semester")
        return
    
    # Course selection
    course_options = {f"{code} - {title}": code for code, title in courses}
    selected_course = st.selectbox("Select Course", options=list(course_options.keys()))
    course_code = course_options[selected_course]
    
    # Date and session selection
    col1, col2 = st.columns(2)
    with col1:
        attendance_date = st.date_input("Select Date", value=date.today())
    with col2:
        session = st.selectbox("Select Session", options=list(range(1, 11)))
    
    # Get students
    students = execute_query(
        """
        SELECT s.Regno, s.First_name, s.Last_name
        FROM course_reg cr
        JOIN student s ON cr.Regno = s.Regno
        WHERE cr.Code = %s AND cr.Sem_ID = %s
        ORDER BY s.Regno
        """,
        (course_code, current_sem_id)
    )
    
    if not students:
        st.info("No students registered for this course")
        return
    
    with st.form("attendance_form"):
        st.write("Mark attendance for each student:")
        
        attendance_data = []
        for regno, fname, lname in students:
            status = st.selectbox(
                f"{fname} {lname} (Regno: {regno})",
                ["Present", "Absent", "Unmarked"],
                index=2,  # Default to Unmarked
                key=f"status_{regno}"
            )
            attendance_data.append((regno, status))
        
        submitted = st.form_submit_button("Submit Attendance")
        
        if submitted:
            try:
                for regno, status in attendance_data:
                    # Check if attendance record exists
                    result = execute_query(
                        """
                        SELECT Regno
                        FROM attendance
                        WHERE Regno = %s 
                        AND Faculty_ID = %s 
                        AND Sem_ID = %s 
                        AND Code = %s 
                        AND Date = %s 
                        AND Session = %s
                        """,
                        (regno, st.session_state.faculty_id, current_sem_id, 
                         course_code, attendance_date, session)
                    )
                    
                    if result and result[0]:
                        # Update existing record
                        execute_query(
                            """
                            UPDATE attendance
                            SET Status = %s
                            WHERE Regno = %s 
                            AND Faculty_ID = %s 
                            AND Sem_ID = %s 
                            AND Code = %s 
                            AND Date = %s 
                            AND Session = %s
                            """,
                            (status, regno, st.session_state.faculty_id, current_sem_id, 
                             course_code, attendance_date, session),
                            fetch=False
                        )
                    else:
                        # Insert new record
                        execute_query(
                            """
                            INSERT INTO attendance 
                            (Regno, Faculty_ID, Sem_ID, Code, Date, Session, Status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (regno, st.session_state.faculty_id, current_sem_id, 
                             course_code, attendance_date, session, status),
                            fetch=False
                        )
                
                st.success("Attendance recorded successfully!")
            except Exception as e:
                st.error(f"Error recording attendance: {str(e)}")

def view_attendance():
    #Display attendance records for faculty.
    st.subheader("View Attendance")
    
    current_sem_id, semester_name = get_current_semester()
    if not current_sem_id:
        st.error("No semester data found")
        return
    
    courses = get_faculty_courses(current_sem_id)
    if not courses:
        st.info("No courses assigned for the current semester")
        return
    
    # Course selection
    course_options = {f"{code} - {title}": code for code, title in courses}
    selected_course = st.selectbox("Select Course", options=list(course_options.keys()))
    course_code = course_options[selected_course]
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
    with col2:
        end_date = st.date_input("End Date", value=date.today())
    
    if st.button("View Attendance"):
        result = execute_query(
            """
            SELECT s.Regno, s.First_name, s.Last_name,
                   COUNT(CASE WHEN a.Status = 'Present' THEN 1 END) as present_count,
                   COUNT(CASE WHEN a.Status = 'Absent' THEN 1 END) as absent_count,
                   COUNT(CASE WHEN a.Status = 'Unmarked' THEN 1 END) as unmarked_count
            FROM course_reg cr
            JOIN student s ON cr.Regno = s.Regno
            LEFT JOIN attendance a ON s.Regno = a.Regno 
                AND a.Faculty_ID = %s 
                AND a.Sem_ID = %s 
                AND a.Code = %s 
                AND a.Date BETWEEN %s AND %s
            WHERE cr.Code = %s AND cr.Sem_ID = %s
            GROUP BY s.Regno, s.First_name, s.Last_name
            ORDER BY s.Regno
            """,
            (st.session_state.faculty_id, current_sem_id, course_code,
             start_date, end_date, course_code, current_sem_id)
        )
        
        if result:
            df = pd.DataFrame(result, columns=[
                'Registration No', 'First Name', 'Last Name',
                'Present', 'Absent', 'Unmarked'
            ])
            
            # Calculate attendance percentage
            df['Total Classes'] = df['Present'] + df['Absent'] + df['Unmarked']
            df['Attendance %'] = (df['Present'] / df['Total Classes'] * 100).round(2)
            
            st.dataframe(df)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                "Download Report",
                csv,
                f"attendance_report_{course_code}_{start_date}_to_{end_date}.csv",
                "text/csv"
            )
        else:
            st.info("No attendance records found for the selected period")

def main():
    #Main application function.
    if not st.session_state.logged_in:
        login_page()
    else:
        st.title("Faculty Attendance Portal")
        
        # Sidebar for navigation
        with st.sidebar:
            st.header("Navigation")
            page = st.selectbox(
                "Select Page",
                ["Dashboard", "Mark Attendance", "View Attendance"]
            )
            
            # Add logout button
            st.sidebar.markdown("---")
            if st.sidebar.button("Logout"):
                logout()
        
        # Main content area
        if page == "Dashboard":
            show_dashboard()
        elif page == "Mark Attendance":
            mark_attendance()
        elif page == "View Attendance":
            view_attendance()

if __name__ == "__main__":
    main()