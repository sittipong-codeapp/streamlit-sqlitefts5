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
    
    # Create the factor table (raw data)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_factor (
            destination_id INTEGER PRIMARY KEY,
            rating INTEGER DEFAULT 0,
            hotel_count INTEGER DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destinations(id)
        )
    ''')
    
    # Create the score table (normalized factors and total score)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            rating_normalized INTEGER DEFAULT 0,
            hotel_count_normalized INTEGER DEFAULT 0,
            rating_weight REAL DEFAULT 0.5,
            hotel_count_weight REAL DEFAULT 0.5,
            total_score INTEGER DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destinations(id)
        )
    ''')

    # Create the FTS5 virtual table
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS destinations_fts USING fts5(name, content=destinations, content_rowid=id)
    ''')

    # Insert sample data if the table is empty
    cursor.execute('SELECT COUNT(*) FROM destinations')
    if cursor.fetchone()[0] == 0:
        # Insert destinations first
        destinations_data = [
            ('city', 'Paris'),
            ('city', 'London'),
            ('city', 'New York'),
            ('area', 'Eiffel Tower'),
            ('area', 'Buckingham Palace'),
            ('area', 'Central Park'),
            ('city', 'Tokyo'),
            ('area', 'Shibuya Crossing'),
        ]
        cursor.executemany('INSERT INTO destinations (type, name) VALUES (?, ?)', destinations_data)
        
        # Insert into FTS table
        cursor.execute('INSERT INTO destinations_fts (rowid, name) SELECT id, name FROM destinations')
        
        # Define raw factor data
        raw_factors = [
            (1, 95, 320),  # Paris
            (2, 90, 270),  # London
            (3, 88, 420),  # New York
            (4, 92, 35),   # Eiffel Tower
            (5, 85, 15),   # Buckingham Palace
            (6, 80, 50),   # Central Park
            (7, 91, 380),  # Tokyo
            (8, 87, 25),   # Shibuya Crossing
        ]
        
        # Calculate max hotel count for normalization
        max_hotel_count = max([row[2] for row in raw_factors])
        
        # Insert raw factor data
        factors = [(dest_id, rating, hotel_count) for dest_id, rating, hotel_count in raw_factors]
        cursor.executemany('INSERT INTO destination_factor (destination_id, rating, hotel_count) VALUES (?, ?, ?)', factors)
        
        # Set default weights
        rating_weight = 0.7  # Higher weight for rating
        hotel_count_weight = 0.3  # Lower weight for hotel count
        
        # Create scores data
        scores = []
        for dest_id, rating, hotel_count in raw_factors:
            # Calculate normalized values on scale of 0-100
            rating_normalized = rating  # Already on 0-100 scale
            hotel_count_normalized = int((hotel_count / max_hotel_count) * 100)  # Convert to 0-100 scale
            
            # Calculate weighted total score
            weighted_sum = (rating_normalized * rating_weight) + (hotel_count_normalized * hotel_count_weight)
            weights_sum = rating_weight + hotel_count_weight
            total_score = int(weighted_sum / weights_sum)
            
            # Double score for cities with rating >= 90
            cursor.execute('SELECT type FROM destinations WHERE id = ?', (dest_id,))
            dest_type = cursor.fetchone()[0]
            if dest_type == 'city' and rating >= 90:
                total_score = min(100, total_score * 2)  # Double but cap at 100
            
            scores.append((
                dest_id, 
                rating_normalized, 
                hotel_count_normalized,
                rating_weight,
                hotel_count_weight,
                total_score
            ))
        
        # Insert scores
        cursor.executemany('''
            INSERT INTO destination_score (
                destination_id, rating_normalized, hotel_count_normalized,
                rating_weight, hotel_count_weight, total_score
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', scores)

    conn.commit()
    conn.close()

# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')

# Function to update factor weights and recalculate total score
def update_weights(rating_weight, hotel_count_weight):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Validate weights (should be between 0 and 1)
    if not (0 <= rating_weight <= 1 and 0 <= hotel_count_weight <= 1):
        conn.close()
        return False
    
    # First update the weights and calculate the base scores
    cursor.execute('''
        UPDATE destination_score 
        SET 
            rating_weight = ?,
            hotel_count_weight = ?,
            total_score = CAST(
                ((rating_normalized * ?) + (hotel_count_normalized * ?)) / (? + ?) 
                AS INTEGER
            )
    ''', (
        rating_weight, 
        hotel_count_weight, 
        rating_weight, 
        hotel_count_weight,
        rating_weight,
        hotel_count_weight
    ))
    
    # Then, double the score for cities with rating >= 90
    cursor.execute('''
        UPDATE destination_score
        SET total_score = CASE
            WHEN total_score * 2 > 100 THEN 100
            ELSE total_score * 2
        END
        WHERE destination_id IN (
            SELECT d.id
            FROM destinations d
            JOIN destination_factor f ON d.id = f.destination_id
            WHERE d.type = 'city' AND f.rating >= 90
        )
    ''')
    
    conn.commit()
    conn.close()
    return True

# Function to search destinations
def search_destinations(query):
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"
    cursor.execute('''
        SELECT 
            d.type, 
            d.name, 
            f.rating, 
            f.hotel_count, 
            s.rating_normalized, 
            s.hotel_count_normalized,
            s.rating_weight,
            s.hotel_count_weight,
            s.total_score
        FROM destinations d
        JOIN destinations_fts fts ON d.id = fts.rowid
        LEFT JOIN destination_factor f ON d.id = f.destination_id
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE fts.name MATCH ?
        ORDER BY s.total_score DESC
        LIMIT 20
    ''', (match_pattern,))
    results = cursor.fetchall()
    conn.close()
    return results

# Streamlit app
def main():
    # Initialize the database
    init_database()

    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Destination Search Sandbox",
        initial_sidebar_state="collapsed"
    )
    
    # Web interface
    st.title("Destination Search Sandbox")
    st.write("Enter a search term to find matching cities and areas.")
    
    # Notification about score bonus
    st.info("📈 Cities with ratings of 90 or higher receive a 2x score bonus!")
    
    # Weight adjustment sidebar
    st.sidebar.header("Factor Weights")
    st.sidebar.write("Adjust the importance of each factor (between 0 and 1)")
    
    # Get current weights from first destination
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT rating_weight, hotel_count_weight FROM destination_score LIMIT 1")
    weights = cursor.fetchone()
    conn.close()
    
    if weights:
        current_rating_weight, current_hotel_weight = weights
    else:
        current_rating_weight, current_hotel_weight = 0.7, 0.3
    
    # Weight adjustment sliders
    with st.sidebar.form("weight_form"):
        rating_weight = st.slider("Rating Weight:", 0.0, 1.0, float(current_rating_weight), 0.05)
        hotel_weight = st.slider("Hotel Count Weight:", 0.0, 1.0, float(current_hotel_weight), 0.05)
        
        submit_weights = st.form_submit_button("Update Weights")
        
        if submit_weights:
            if update_weights(rating_weight, hotel_weight):
                st.sidebar.success("Weights updated successfully!")
            else:
                st.sidebar.error("Failed to update weights. Make sure values are between 0 and 1.")
    
    # Search section
    query = st.text_input("Search for a destination:")
    if query:
        results = search_destinations(query)
        if results:
            # Create main results dataframe
            df = pd.DataFrame(results, columns=[
                "Type", "Name", "Rating", "Hotel Count", 
                "Rating (Normalized)", "Hotel Count (Normalized)",
                "Rating Weight", "Hotel Weight", "Total Score"
            ])
            
            st.write(f"Found {len(results)} matching destinations:")
            
            # Format weights to show 2 decimal places
            df["Rating Weight"] = df["Rating Weight"].apply(lambda x: f"{x:.2f}")
            df["Hotel Weight"] = df["Hotel Weight"].apply(lambda x: f"{x:.2f}")
            
            # Show simplified dataframe with most relevant columns
            display_df = df[["Name", "Type", "Total Score", "Rating (Normalized)", "Hotel Count (Normalized)"]]
            st.dataframe(display_df)
        else:
            st.write("No matching destinations found.")

if __name__ == "__main__":
    main()