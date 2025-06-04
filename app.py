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
    
    # Create the factor weights table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factor_weights (
            type TEXT PRIMARY KEY,  -- 'city' or 'area'
            rating_weight REAL DEFAULT 0.5,
            hotel_count_weight REAL DEFAULT 0.5
        )
    ''')
    
    # Create the score table (normalized factors and total score)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            rating_normalized INTEGER DEFAULT 0,
            hotel_count_normalized INTEGER DEFAULT 0,
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
        
        # Set default weights - different for city and area
        city_rating_weight = 0.7  # Higher weight for rating in cities
        city_hotel_count_weight = 0.3  # Lower weight for hotel count in cities
        area_rating_weight = 0.5  # Equal weight for rating in areas
        area_hotel_count_weight = 0.5  # Equal weight for hotel count in areas
        
        # Insert default factor weights
        default_weights = [
            ('city', city_rating_weight, city_hotel_count_weight),
            ('area', area_rating_weight, area_hotel_count_weight)
        ]
        cursor.executemany('INSERT INTO factor_weights (type, rating_weight, hotel_count_weight) VALUES (?, ?, ?)', default_weights)
        
        # Create scores data
        scores = []
        for dest_id, rating, hotel_count in raw_factors:
            # Calculate normalized values on scale of 0-100
            rating_normalized = rating  # Already on 0-100 scale
            hotel_count_normalized = int((hotel_count / max_hotel_count) * 100)  # Convert to 0-100 scale
            
            # Get destination type and appropriate weights
            cursor.execute('SELECT type FROM destinations WHERE id = ?', (dest_id,))
            dest_type = cursor.fetchone()[0]
            
            if dest_type == 'city':
                rating_weight = city_rating_weight
                hotel_count_weight = city_hotel_count_weight
            else:  # area
                rating_weight = area_rating_weight
                hotel_count_weight = area_hotel_count_weight
            
            # Calculate weighted total score
            weighted_sum = (rating_normalized * rating_weight) + (hotel_count_normalized * hotel_count_weight)
            weights_sum = rating_weight + hotel_count_weight
            total_score = int(weighted_sum / weights_sum)
            
            # Double score for cities with rating >= 90
            if dest_type == 'city' and rating >= 90:
                total_score = min(100, total_score * 2)  # Double but cap at 100
            
            scores.append((
                dest_id, 
                rating_normalized, 
                hotel_count_normalized,
                total_score
            ))
        
        # Insert scores
        cursor.executemany('''
            INSERT INTO destination_score (
                destination_id, rating_normalized, hotel_count_normalized, total_score
            ) VALUES (?, ?, ?, ?)
        ''', scores)

        # Default weights already inserted above

    conn.commit()
    conn.close()

# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')

# Function to update factor weights and recalculate total score
def update_weights(dest_type, rating_weight, hotel_count_weight):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Validate weights (should be between 0 and 1)
    if not (0 <= rating_weight <= 1 and 0 <= hotel_count_weight <= 1):
        conn.close()
        return False
    
    # Validate destination type
    if dest_type not in ['city', 'area']:
        conn.close()
        return False
    
    # Update the weights for the specified destination type
    cursor.execute('''
        UPDATE factor_weights
        SET rating_weight = ?,
            hotel_count_weight = ?
        WHERE type = ?
    ''', (rating_weight, hotel_count_weight, dest_type))
    
    # For each destination of the specified type, recalculate the score
    cursor.execute('''
        UPDATE destination_score
        SET total_score = CAST(
            ((rating_normalized * ?) + (hotel_count_normalized * ?)) / (? + ?) 
            AS INTEGER
        )
        WHERE destination_id IN (
            SELECT id FROM destinations WHERE type = ?
        )
    ''', (
        rating_weight,
        hotel_count_weight,
        rating_weight,
        hotel_count_weight,
        dest_type
    ))
    
    # Then, double the score for cities with rating >= 90 (only if updating city weights)
    if dest_type == 'city':
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
            s.total_score,
            w.rating_weight,
            w.hotel_count_weight
        FROM destinations d
        JOIN destinations_fts fts ON d.id = fts.rowid
        LEFT JOIN destination_factor f ON d.id = f.destination_id
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON d.type = w.type
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
    
    # Get current weights from factor_weights table
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, rating_weight, hotel_count_weight FROM factor_weights")
    weights_data = cursor.fetchall()
    conn.close()
    
    # Create dictionary of current weights by destination type
    current_weights = {}
    for dest_type, rating_weight, hotel_count_weight in weights_data:
        current_weights[dest_type] = {
            'rating_weight': rating_weight,
            'hotel_count_weight': hotel_count_weight
        }
    
    # Default values if no weights found
    if 'city' not in current_weights:
        current_weights['city'] = {'rating_weight': 0.7, 'hotel_count_weight': 0.3}
    if 'area' not in current_weights:
        current_weights['area'] = {'rating_weight': 0.5, 'hotel_count_weight': 0.5}
    
    # Weight adjustment forms - one for each destination type
    dest_types = ['city', 'area']
    
    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")
        
        with st.sidebar.form(f"{dest_type}_weight_form"):
            rating_weight = st.slider(
                f"{dest_type.title()} Rating Weight:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['rating_weight']), 
                0.05
            )
            
            hotel_count_weight = st.slider(
                f"{dest_type.title()} Hotel Count Weight:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['hotel_count_weight']), 
                0.05
            )
            
            submit_weights = st.form_submit_button(f"Update {dest_type.title()} Weights")
            
            if submit_weights:
                if update_weights(dest_type, rating_weight, hotel_count_weight):
                    st.sidebar.success(f"{dest_type.title()} weights updated successfully!")
                else:
                    st.sidebar.error(f"Failed to update {dest_type.title()} weights. Make sure values are between 0 and 1.")
    
    # Search section
    query = st.text_input("Search for a destination:")
    if query:
        results = search_destinations(query)
        if results:
            # Create main results dataframe
            df = pd.DataFrame(results, columns=[
                "Type", "Name", "Rating", "Hotel Count", 
                "Rating (Normalized)", "Hotel Count (Normalized)",
                "Total Score", "Rating Weight", "Hotel Count Weight"
            ])
            
            st.write(f"Found {len(results)} matching destinations:")
            
            # Show results with weights
            display_df = df[["Name", "Type", "Total Score", "Rating (Normalized)", "Hotel Count (Normalized)"]]
            st.dataframe(display_df)
            
            # Show factor weights explanation
            with st.expander("View Factor Weights for Results"):
                # Group by type and show weights
                weights_df = df[["Type", "Rating Weight", "Hotel Count Weight"]].drop_duplicates()
                st.dataframe(weights_df)
                
                st.markdown("""
                ### How scores are calculated:
                - For each destination, we calculate: `(Rating × Rating Weight) + (Hotel Count × Hotel Count Weight)`
                - The weights sum to 1.0 for each destination type
                - Cities with ratings ≥ 90 receive a 2× score bonus (capped at 100)
                """)
        else:
            st.write("No matching destinations found.")

if __name__ == "__main__":
    main()