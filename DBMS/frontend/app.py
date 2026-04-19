import streamlit as st
import mysql.connector
from mysql.connector import pooling
import pandas as pd
from datetime import date
import os
import bcrypt
from dotenv import load_dotenv

load_dotenv()

ATTENDANCE_STATUSES = ["Present", "Absent", "Unmarked"]
DEFAULT_STATUS_INDEX = 2   # "Unmarked"
MAX_SESSION = 10

st.set_page_config(
    page_title="Faculty Attendance Portal",
    page_icon="👨‍🏫",
    layout="wide",
)

for key, default in {
    "logged_in": False,
    "faculty_id": None,
    "faculty_name": None,
    "selected_semester": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default
        
@st.cache_resource
def _get_pool() -> pooling.MySQLConnectionPool:
    return pooling.MySQLConnectionPool(
        pool_name="faculty_pool",
        pool_size=5,
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "your_username"),
        password=os.getenv("DB_PASSWORD", "your_password"),
        database=os.getenv("DB_NAME", "your_database"),
    )


def execute_query(query: str, params: tuple = (), *, fetch: bool = True):
    cursor = None
    connection = None
    try:
        connection = _get_pool().get_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        connection.commit()
        return None
    except mysql.connector.Error as err:
        st.error(f"Database error: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
def execute_many(query: str, data: list[tuple]) -> bool:
    if not data:
        return True
    cursor = None
    connection = None
    try:
        connection = _get_pool().get_connection()
        cursor = connection.cursor()
        cursor.executemany(query, data)
        connection.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Database error: {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
def _verify_password(plain: str, stored: str) -> bool:
    if stored.startswith("$2b$") or stored.startswith("$2a$"):
        return bcrypt.checkpw(plain.encode(), stored.encode())
    return plain == stored

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

@st.cache_data(ttl=300)
def get_all_semesters() -> list[tuple]:
    result = execute_query(
        "SELECT Sem_ID, CONCAT('Year ', Year, ' - Term ', Term) FROM semester ORDER BY Sem_ID"
    )
    return result or []

@st.cache_data(ttl=60)
def get_faculty_courses(faculty_id: int, sem_id: int) -> list[tuple]:
    result = execute_query(
        """
        SELECT c.Code, c.Title
        FROM course_allot ca
        JOIN course c ON ca.Code = c.Code
        WHERE ca.Faculty_ID = %s AND ca.Sem_ID = %s
        """,
        (faculty_id, sem_id),
    )
    return result or []


@st.cache_data(ttl=30)
def get_enrolled_students(course_code: str, sem_id: int) -> list[tuple]:
    result = execute_query(
        """
        SELECT s.Regno, s.First_name, s.Last_name
        FROM course_reg cr
        JOIN student s ON cr.Regno = s.Regno
        WHERE cr.Code = %s AND cr.Sem_ID = %s
        ORDER BY s.Regno
        """,
        (course_code, sem_id),
    )
    return result or []


def get_existing_attendance(
    faculty_id: int,
    sem_id: int,
    course_code: str,
    attendance_date: date,
    session: int,
) -> set[str]:
    """Return the set of Regnos that already have an attendance record."""
    result = execute_query(
        """
        SELECT Regno FROM attendance
        WHERE Faculty_ID = %s AND Sem_ID = %s AND Code = %s
          AND Date = %s AND Session = %s
        """,
        (faculty_id, sem_id, course_code, attendance_date, session),
    )
    return {row[0] for row in result} if result else set()

def render_semester_selector() -> tuple[int | None, str | None]:
    semesters = get_all_semesters()
    if not semesters:
        return None, None

    semester_map = {name: sem_id for sem_id, name in semesters}
    names = list(semester_map.keys())

    # Restore previous selection or default to first
    default_idx = 0
    if st.session_state.selected_semester in names:
        default_idx = names.index(st.session_state.selected_semester)

    with st.sidebar:
        chosen = st.selectbox("Select Semester", options=names, index=default_idx)
        st.session_state.selected_semester = chosen

    return semester_map[chosen], chosen

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br>" * 4, unsafe_allow_html=True)
        st.markdown(
            """
            <div style='text-align:center;'>
                <h1 style='color:#0066cc;'>👨‍🏫</h1>
                <h2 style='color:#0066cc;'>Faculty Attendance Portal</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            _, btn_col, _ = st.columns([1, 2, 1])
            with btn_col:
                submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
                return

            row = execute_query(
                """
                SELECT Faculty_ID, CONCAT(First_name,' ',Last_name), Password
                FROM faculty WHERE Username = %s
                """,
                (username,),
            )

            if row and _verify_password(password, row[0][2]):
                st.session_state.logged_in = True
                st.session_state.faculty_id = row[0][0]
                st.session_state.faculty_name = row[0][1]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")


def show_dashboard(sem_id: int, semester_name: str):
    st.subheader(f"Welcome, {st.session_state.faculty_name}")
    st.write(f"Current Semester: {semester_name}")

    courses = get_faculty_courses(st.session_state.faculty_id, sem_id)
    if not courses:
        st.info("No courses assigned for the current semester")
        return

    st.subheader("Your Courses")
    for code, title in courses:
        with st.expander(f"{code} — {title}"):
            result = execute_query(
                """
                SELECT
                    COUNT(CASE WHEN Status='Present' THEN 1 END),
                    COUNT(CASE WHEN Status='Absent'  THEN 1 END),
                    COUNT(CASE WHEN Status='Unmarked' THEN 1 END)
                FROM attendance
                WHERE Faculty_ID=%s AND Sem_ID=%s AND Code=%s AND Date=CURDATE()
                """,
                (st.session_state.faculty_id, sem_id, code),
            )
            if result and result[0]:
                present, absent, unmarked = result[0]
                c1, c2, c3 = st.columns(3)
                c1.metric("Present",  present)
                c2.metric("Absent",   absent)
                c3.metric("Unmarked", unmarked)


def mark_attendance(sem_id: int):
    st.subheader("Mark Attendance")

    courses = get_faculty_courses(st.session_state.faculty_id, sem_id)
    if not courses:
        st.info("No courses assigned for the current semester")
        return

    course_map = {f"{code} — {title}": code for code, title in courses}
    selected = st.selectbox("Select Course", list(course_map))
    course_code = course_map[selected]

    col1, col2 = st.columns(2)
    with col1:
        attendance_date = st.date_input("Select Date", value=date.today())
    with col2:
        session = st.selectbox("Select Session", range(1, MAX_SESSION + 1))

    students = get_enrolled_students(course_code, sem_id)
    if not students:
        st.info("No students registered for this course")
        return

    with st.form("attendance_form"):
        st.write("Mark attendance for each student:")
        attendance_data: list[tuple[str, str]] = []
        for regno, fname, lname in students:
            status = st.selectbox(
                f"{fname} {lname}  (Reg: {regno})",
                ATTENDANCE_STATUSES,
                index=DEFAULT_STATUS_INDEX,
                key=f"status_{regno}",
            )
            attendance_data.append((regno, status))

        submitted = st.form_submit_button("Submit Attendance")

    if submitted:
        faculty_id = st.session_state.faculty_id
        existing = get_existing_attendance(faculty_id, sem_id, course_code, attendance_date, session)

        inserts = [
            (regno, faculty_id, sem_id, course_code, attendance_date, session, status)
            for regno, status in attendance_data
            if regno not in existing
        ]
        updates = [
            (status, regno, faculty_id, sem_id, course_code, attendance_date, session)
            for regno, status in attendance_data
            if regno in existing
        ]

        ok_insert = execute_many(
            "INSERT INTO attendance (Regno,Faculty_ID,Sem_ID,Code,Date,Session,Status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            inserts,
        )
        ok_update = execute_many(
            "UPDATE attendance SET Status=%s "
            "WHERE Regno=%s AND Faculty_ID=%s AND Sem_ID=%s AND Code=%s AND Date=%s AND Session=%s",
            updates,
        )

        if ok_insert and ok_update:
            st.success(
                f"Attendance saved — {len(inserts)} inserted, {len(updates)} updated."
            )
            # Invalidate cached attendance-dependent queries
            get_enrolled_students.clear()


def view_attendance(sem_id: int):
    st.subheader("View Attendance")

    courses = get_faculty_courses(st.session_state.faculty_id, sem_id)
    if not courses:
        st.info("No courses assigned for the current semester")
        return

    course_map = {f"{code} — {title}": code for code, title in courses}
    selected = st.selectbox("Select Course", list(course_map))
    course_code = course_map[selected]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
    with col2:
        end_date = st.date_input("End Date", value=date.today())

    if st.button("View Attendance"):
        if end_date < start_date:
            st.error("End date must be on or after start date")
            return

        result = execute_query(
            """
            SELECT s.Regno, s.First_name, s.Last_name,
                   COUNT(CASE WHEN a.Status='Present' THEN 1 END),
                   COUNT(CASE WHEN a.Status='Absent'  THEN 1 END),
                   COUNT(CASE WHEN a.Status='Unmarked' THEN 1 END)
            FROM course_reg cr
            JOIN student s ON cr.Regno = s.Regno
            LEFT JOIN attendance a
                ON s.Regno = a.Regno
               AND a.Faculty_ID = %s
               AND a.Sem_ID    = %s
               AND a.Code      = %s
               AND a.Date BETWEEN %s AND %s
            WHERE cr.Code = %s AND cr.Sem_ID = %s
            GROUP BY s.Regno, s.First_name, s.Last_name
            ORDER BY s.Regno
            """,
            (
                st.session_state.faculty_id, sem_id, course_code,
                start_date, end_date,
                course_code, sem_id,
            ),
        )

        if not result:
            st.info("No attendance records found for the selected period")
            return

        df = pd.DataFrame(
            result,
            columns=["Registration No", "First Name", "Last Name", "Present", "Absent", "Unmarked"],
        )
        df["Total Classes"] = df["Present"] + df["Absent"] + df["Unmarked"]
        df["Attendance %"] = df.apply(
            lambda r: round(r["Present"] / r["Total Classes"] * 100, 2)
            if r["Total Classes"] > 0 else 0.0,
            axis=1,
        )

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False)
        st.download_button(
            "Download Report",
            csv,
            f"attendance_{course_code}_{start_date}_to_{end_date}.csv",
            "text/csv",
        )

def logout():
    for key in ("logged_in", "faculty_id", "faculty_name", "selected_semester"):
        st.session_state[key] = None if key != "logged_in" else False
    st.rerun()


def main():
    if not st.session_state.logged_in:
        login_page()
        return

    st.title("Faculty Attendance Portal")

    with st.sidebar:
        st.header("Navigation")
        page = st.selectbox("Select Page", ["Dashboard", "Mark Attendance", "View Attendance"])
        st.markdown("---")
        if st.button("Logout"):
            logout()

    # Semester selector rendered once; result passed to every page
    sem_id, semester_name = render_semester_selector()

    if not sem_id:
        st.error("No semester data found. Please contact your administrator.")
        return

    if page == "Dashboard":
        show_dashboard(sem_id, semester_name)
    elif page == "Mark Attendance":
        mark_attendance(sem_id)
    elif page == "View Attendance":
        view_attendance(sem_id)


if __name__ == "__main__":
    main()
