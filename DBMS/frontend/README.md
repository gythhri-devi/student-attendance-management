# MySQL Database Interface with Streamlit

This is a Streamlit-based frontend application for interacting with MySQL databases.

## Setup Instructions

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the frontend directory with your MySQL credentials:
```
DB_HOST=localhost
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=your_database
```

4. Run the application:
```bash
streamlit run app.py
```

## Features

- View all tables in the database
- Execute custom SQL queries
- Insert data into tables (placeholder for customization)
- Interactive data visualization
- Secure database connection using environment variables

## Customization

You can customize the application by:
1. Modifying the database connection parameters in `get_db_connection()`
2. Adding more operations in the sidebar
3. Customizing the data insertion functionality in the `insert_data()` function
4. Adding more visualization options using Streamlit's built-in components

## Security Notes

- Never commit your `.env` file to version control
- Use strong passwords for database access
- Consider implementing user authentication for the Streamlit app # urban-system
