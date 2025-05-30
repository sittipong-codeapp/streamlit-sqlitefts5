import streamlit as st
import sqlite3
import pandas as pd

# Function to initialize the SQLite database
def init_database():
    conn = sqlite3.connect('destinations.db')
    cursor = conn.cursor()

    # Create the destinations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            name TEXT
        )
    ''')

    # Create the FTS5 virtual table
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS destinations_fts USING fts5(name, content=destinations, content_rowid=id)
    ''')

    # Insert sample data if the table is empty
    cursor.execute('SELECT COUNT(*) FROM destinations')
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ('city', 'Paris'),
            ('city', 'London'),
            ('city', 'New York'),
            ('area', 'Eiffel Tower'),
            ('area', 'Buckingham Palace'),
            ('area', 'Central Park'),
            ('city', 'Tokyo'),
            ('area', 'Shibuya Crossing'),
        ]
        cursor.executemany('INSERT INTO destinations (type, name) VALUES (?, ?)', sample_data)
        cursor.execute('INSERT INTO destinations_fts (rowid, name) SELECT id, name FROM destinations')

    conn.commit()
    conn.close()

# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')

# Function to search destinations
def search_destinations(query):
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"
    cursor.execute('''
        SELECT d.type, d.name
        FROM destinations d
        JOIN destinations_fts f ON d.id = f.rowid
        WHERE f.name MATCH ?
        ORDER BY rank
        LIMIT 20
    ''', (match_pattern,))
    results = cursor.fetchall()
    conn.close()
    return results

# Streamlit app
def main():
    # Initialize the database
    init_database()

    # Web interface
    st.title("Destination Search Sandbox")
    st.write("Enter a search term to find matching cities and areas.")
    
    query = st.text_input("Search for a destination:")
    if query:
        results = search_destinations(query)
        if results:
            df = pd.DataFrame(results, columns=["Type", "Name"])
            st.write(f"Found {len(results)} matching destinations:")
            st.dataframe(df)
        else:
            st.write("No matching destinations found.")

if __name__ == "__main__":
    main()