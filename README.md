# Student Attendance Portal

A Streamlit web application that lets faculty log in, mark student attendance, and export attendance reports — backed by a MySQL database.

---

## Features

- **Secure login** — bcrypt password hashing with a plain-text migration path for existing accounts
- **Semester-aware** — switch between semesters from the sidebar; all pages respect the selection
- **Mark attendance** — per-student Present / Absent / Unmarked selection with bulk DB writes (`executemany`)
- **View & export** — date-range attendance summary with one-click CSV download
- **Dashboard** — today's attendance snapshot for every assigned course

---

## Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.11 |
| streamlit | ≥ 1.33 |
| mysql-connector-python | ≥ 8.3 |
| pandas | ≥ 2.2 |
| bcrypt | ≥ 4.1 |
| python-dotenv | ≥ 1.0 |

Install everything at once:

```bash
pip install streamlit mysql-connector-python pandas bcrypt python-dotenv
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/faculty-attendance-portal.git
cd faculty-attendance-portal
```

### 2. Configure the database connection

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

**.env.example**
```
DB_HOST=localhost
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=your_database_name
```

### 3. Database schema

The app expects these tables (column names must match exactly):

| Table | Key columns |
|---|---|
| `faculty` | `Faculty_ID`, `First_name`, `Last_name`, `Username`, `Password` |
| `semester` | `Sem_ID`, `Year`, `Term` |
| `course` | `Code`, `Title` |
| `course_allot` | `Faculty_ID`, `Sem_ID`, `Code` |
| `course_reg` | `Regno`, `Sem_ID`, `Code` |
| `student` | `Regno`, `First_name`, `Last_name` |
| `attendance` | `Regno`, `Faculty_ID`, `Sem_ID`, `Code`, `Date`, `Session`, `Status` |

### 4. Password hashing (important)

New accounts should store bcrypt hashes. To hash an existing plain-text password:

```python
import bcrypt
hashed = bcrypt.hashpw(b"plaintext_password", bcrypt.gensalt()).decode()
print(hashed)   # store this in the Password column
```

The login function automatically detects bcrypt hashes (starting with `$2b$`) vs. legacy plain-text passwords, so you can migrate accounts gradually. **Remove the plain-text fallback once all passwords are hashed.**

---

## Running the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501` by default.

---

## Project structure

```
.
├── app.py          # Main application
├── .env            # DB credentials (never commit this)
├── .env.example    # Template for .env
└── README.md
```

---

## Optimisations vs. the original

| Area | Change | Benefit |
|---|---|---|
| **Security** | bcrypt password hashing | Passwords safe at rest |
| **DB connections** | `MySQLConnectionPool` (size 5) via `@st.cache_resource` | Eliminates per-query connect/disconnect overhead |
| **Query caching** | `@st.cache_data` on semesters (5 min) and courses (1 min) | Fewer redundant round-trips |
| **Bulk writes** | `executemany` for attendance insert + update | One round-trip per batch instead of one per student |
| **Cursor safety** | Explicit `cursor = None` before try/finally | Eliminates `NameError` if connection fails |
| **Semester selector** | Rendered once in `main()`, result passed to pages | No duplicate sidebar widgets |
| **Division guard** | `Attendance %` guarded against zero total | No `ZeroDivisionError` for new students |
| **Date validation** | End date checked against start date | User-friendly error instead of empty results |
| **Constants** | `ATTENDANCE_STATUSES`, `MAX_SESSION` at module level | Single place to change magic values |

---

## Security notes

- Never commit `.env` to version control — add it to `.gitignore`
- Use a dedicated MySQL user with only the permissions the app needs (`SELECT`, `INSERT`, `UPDATE` on the relevant tables)
- Consider HTTPS / a reverse proxy (nginx, Caddy) when deploying beyond localhost
- For production, replace `bcrypt` with a secrets manager and rotate DB credentials regularly

---

## License

MIT
