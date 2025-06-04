import streamlit as st
import sqlite3
import pandas as pd

# Function to initialize the SQLite database
def init_database():
    conn = sqlite3.connect('destinations.db')
    cursor = conn.cursor()

    # Create the countries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_hotels INTEGER DEFAULT 0
        )
    ''')
    
    # Create the cities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER,
            total_hotels INTEGER DEFAULT 0,
            FOREIGN KEY (country_id) REFERENCES countries(id)
        )
    ''')
    
    # Create the areas table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city_id INTEGER,
            total_hotels INTEGER DEFAULT 0,
            FOREIGN KEY (city_id) REFERENCES cities(id)
        )
    ''')

    # Create the destinations table (now with foreign keys)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER,
            city_id INTEGER,
            area_id INTEGER,
            type TEXT CHECK(type IN ('city', 'area')),
            FOREIGN KEY (country_id) REFERENCES countries(id),
            FOREIGN KEY (city_id) REFERENCES cities(id),
            FOREIGN KEY (area_id) REFERENCES areas(id)
        )
    ''')
    
    # Create the factor table (raw data) - removed hotel_count
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_factor (
            destination_id INTEGER PRIMARY KEY,
            rating INTEGER DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destinations(id)
        )
    ''')
    
    # Create the factor weights table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factor_weights (
            type TEXT PRIMARY KEY,  -- 'city' or 'area'
            rating_weight REAL DEFAULT 0.5,
            hotel_count_weight REAL DEFAULT 0.3,
            country_hotel_count_weight REAL DEFAULT 0.2
        )
    ''')
    
    # Create the score table (normalized factors and total score)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            rating_normalized INTEGER DEFAULT 0,
            hotel_count_normalized INTEGER DEFAULT 0,
            country_hotel_count_normalized INTEGER DEFAULT 0,
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
        # Insert countries first
        countries_data = [
            ('France',),
            ('United Kingdom',),
            ('United States',),
            ('Japan',)
        ]
        cursor.executemany('INSERT INTO countries (name) VALUES (?)', countries_data)
        
        # Get country IDs for reference
        cursor.execute('SELECT id, name FROM countries')
        country_map = {name: id for id, name in cursor.fetchall()}
        
        # Insert cities
        cities_data = [
            ('Paris', country_map['France']),
            ('London', country_map['United Kingdom']),
            ('New York', country_map['United States']),
            ('Tokyo', country_map['Japan'])
        ]
        cursor.executemany('INSERT INTO cities (name, country_id) VALUES (?, ?)', cities_data)
        
        # Get city IDs for reference
        cursor.execute('SELECT id, name FROM cities')
        city_map = {name: id for id, name in cursor.fetchall()}
        
        # Insert areas
        areas_data = [
            ('Eiffel Tower', city_map['Paris']),
            ('Buckingham Palace', city_map['London']),
            ('Central Park', city_map['New York']),
            ('Shibuya Crossing', city_map['Tokyo'])
        ]
        cursor.executemany('INSERT INTO areas (name, city_id) VALUES (?, ?)', areas_data)
        
        # Get area IDs for reference
        cursor.execute('SELECT id, name FROM areas')
        area_map = {name: id for id, name in cursor.fetchall()}
        
        # Insert destinations (both cities and areas)
        destinations_data = [
            # Cities
            ('Paris', country_map['France'], city_map['Paris'], None, 'city'),
            ('London', country_map['United Kingdom'], city_map['London'], None, 'city'),
            ('New York', country_map['United States'], city_map['New York'], None, 'city'),
            ('Tokyo', country_map['Japan'], city_map['Tokyo'], None, 'city'),
            # Areas
            ('Eiffel Tower', country_map['France'], city_map['Paris'], area_map['Eiffel Tower'], 'area'),
            ('Buckingham Palace', country_map['United Kingdom'], city_map['London'], area_map['Buckingham Palace'], 'area'),
            ('Central Park', country_map['United States'], city_map['New York'], area_map['Central Park'], 'area'),
            ('Shibuya Crossing', country_map['Japan'], city_map['Tokyo'], area_map['Shibuya Crossing'], 'area')
        ]
        cursor.executemany('INSERT INTO destinations (name, country_id, city_id, area_id, type) VALUES (?, ?, ?, ?, ?)', destinations_data)
        
        # Insert into FTS table
        cursor.execute('INSERT INTO destinations_fts (rowid, name) SELECT id, name FROM destinations')
        
        # Define hotel counts for locations
        city_hotel_counts = {
            'Paris': 320,
            'London': 270, 
            'New York': 420,
            'Tokyo': 380
        }
        
        area_hotel_counts = {
            'Eiffel Tower': 35,
            'Buckingham Palace': 15,
            'Central Park': 50,
            'Shibuya Crossing': 25
        }
        
        # Update cities with total_hotels
        for city_name, hotel_count in city_hotel_counts.items():
            cursor.execute('UPDATE cities SET total_hotels = ? WHERE name = ?', (hotel_count, city_name))
        
        # Update areas with total_hotels
        for area_name, hotel_count in area_hotel_counts.items():
            cursor.execute('UPDATE areas SET total_hotels = ? WHERE name = ?', (hotel_count, area_name))
        
        # Update countries with aggregated hotel counts from their cities
        cursor.execute('''
            UPDATE countries 
            SET total_hotels = (
                SELECT COALESCE(SUM(cities.total_hotels), 0)
                FROM cities 
                WHERE cities.country_id = countries.id
            )
        ''')
        
        # Define rating data only (hotel_count removed)
        rating_data = [
            (1, 95),  # Paris
            (2, 90),  # London
            (3, 88),  # New York
            (4, 92),  # Eiffel Tower
            (5, 85),  # Buckingham Palace
            (6, 80),  # Central Park
            (7, 91),  # Tokyo
            (8, 87),  # Shibuya Crossing
        ]
        
        # Insert rating data only
        cursor.executemany('INSERT INTO destination_factor (destination_id, rating) VALUES (?, ?)', rating_data)
        
        # Set default weights with three-factor weighting
        city_rating_weight = 0.5  # Rating weight for cities
        city_hotel_count_weight = 0.3  # Global hotel count weight for cities
        city_country_hotel_count_weight = 0.2  # Country hotel count weight for cities
        area_rating_weight = 0.4  # Rating weight for areas
        area_hotel_count_weight = 0.3  # Global hotel count weight for areas
        area_country_hotel_count_weight = 0.3  # Country hotel count weight for areas
        
        # Insert default factor weights
        default_weights = [
            ('city', city_rating_weight, city_hotel_count_weight, city_country_hotel_count_weight),
            ('area', area_rating_weight, area_hotel_count_weight, area_country_hotel_count_weight)
        ]
        cursor.executemany('INSERT INTO factor_weights (type, rating_weight, hotel_count_weight, country_hotel_count_weight) VALUES (?, ?, ?, ?)', default_weights)
        
        # Calculate normalized hotel counts and scores
        # First, get the maximum city hotel count for normalization
        cursor.execute('SELECT MAX(total_hotels) FROM cities')
        max_city_hotels = cursor.fetchone()[0] or 1  # Avoid division by zero
        
        # Create scores with normalized hotel counts from location tables
        scores = []
        for dest_id, rating in rating_data:
            # Get destination type, country, and location hotel count
            cursor.execute('''
                SELECT d.type, d.country_id 
                FROM destinations d 
                WHERE d.id = ?
            ''', (dest_id,))
            dest_type, country_id = cursor.fetchone()
            
            # Get hotel count from appropriate location table
            if dest_type == 'city':
                cursor.execute('''
                    SELECT ci.total_hotels 
                    FROM destinations d 
                    JOIN cities ci ON d.city_id = ci.id 
                    WHERE d.id = ?
                ''', (dest_id,))
                hotel_count = cursor.fetchone()[0] or 0
                # Normalize city hotel count: city.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM cities ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                max_country_city_hotels = cursor.fetchone()[0] or 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
            else:  # area
                cursor.execute('''
                    SELECT ar.total_hotels 
                    FROM destinations d 
                    JOIN areas ar ON d.area_id = ar.id 
                    WHERE d.id = ?
                ''', (dest_id,))
                hotel_count = cursor.fetchone()[0] or 0
                # Normalize area hotel count: area.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM cities ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                max_country_city_hotels = cursor.fetchone()[0] or 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
            
            # Rating is already on 0-100 scale
            rating_normalized = rating
            
            # Get weights for this destination type
            if dest_type == 'city':
                rating_weight = city_rating_weight
                hotel_count_weight = city_hotel_count_weight
                country_hotel_count_weight = city_country_hotel_count_weight
            else:  # area
                rating_weight = area_rating_weight
                hotel_count_weight = area_hotel_count_weight
                country_hotel_count_weight = area_country_hotel_count_weight
            
            # Calculate weighted total score with three factors
            weighted_sum = (rating_normalized * rating_weight) + (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
            weights_sum = rating_weight + hotel_count_weight + country_hotel_count_weight
            total_score = int(weighted_sum / weights_sum) if weights_sum > 0 else rating_normalized
            
            # Double score for cities with rating >= 90
            if dest_type == 'city' and rating >= 90:
                total_score = min(100, total_score * 2)  # Double but cap at 100
            
            scores.append((
                dest_id, 
                rating_normalized,
                hotel_count_normalized,
                country_hotel_count_normalized,
                total_score
            ))
        
        # Insert scores with both hotel count normalizations
        cursor.executemany('''
            INSERT INTO destination_score (
                destination_id, rating_normalized, hotel_count_normalized, country_hotel_count_normalized, total_score
            ) VALUES (?, ?, ?, ?, ?)
        ''', scores)

    conn.commit()
    conn.close()

# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')

# Function to update factor weights and recalculate total score
def update_weights(dest_type, rating_weight, hotel_count_weight, country_hotel_count_weight):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Validate weights (should be between 0 and 1)
    if not (0 <= rating_weight <= 1 and 0 <= hotel_count_weight <= 1 and 0 <= country_hotel_count_weight <= 1):
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
            hotel_count_weight = ?,
            country_hotel_count_weight = ?
        WHERE type = ?
    ''', (rating_weight, hotel_count_weight, country_hotel_count_weight, dest_type))
    
    # Get max city hotel count for normalization
    cursor.execute('SELECT MAX(total_hotels) FROM cities')
    max_city_hotels = cursor.fetchone()[0] or 1
    
    # For each destination of the specified type, recalculate the score
    cursor.execute('SELECT id FROM destinations WHERE type = ?', (dest_type,))
    dest_ids = [row[0] for row in cursor.fetchall()]
    
    for dest_id in dest_ids:
        # Get rating and country
        cursor.execute('''
            SELECT f.rating, d.country_id 
            FROM destination_factor f 
            JOIN destinations d ON f.destination_id = d.id 
            WHERE f.destination_id = ?
        ''', (dest_id,))
        rating, country_id = cursor.fetchone()
        rating = rating or 0
        
        # Get hotel count from appropriate location table and normalize
        if dest_type == 'city':
            cursor.execute('''
                SELECT ci.total_hotels 
                FROM destinations d 
                JOIN cities ci ON d.city_id = ci.id 
                WHERE d.id = ?
            ''', (dest_id,))
            hotel_count = cursor.fetchone()[0] or 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM cities ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            max_country_city_hotels = cursor.fetchone()[0] or 1
        else:  # area
            cursor.execute('''
                SELECT ar.total_hotels 
                FROM destinations d 
                JOIN areas ar ON d.area_id = ar.id 
                WHERE d.id = ?
            ''', (dest_id,))
            hotel_count = cursor.fetchone()[0] or 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM cities ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            max_country_city_hotels = cursor.fetchone()[0] or 1
        
        # Normalize hotel counts - global and country level
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
        
        # Calculate weighted total score with three factors
        weighted_sum = (rating * rating_weight) + (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
        weights_sum = rating_weight + hotel_count_weight + country_hotel_count_weight
        total_score = int(weighted_sum / weights_sum) if weights_sum > 0 else rating
        
        # Double score for cities with rating >= 90
        if dest_type == 'city' and rating >= 90:
            total_score = min(100, total_score * 2)
        
        # Update the score
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''', (hotel_count_normalized, country_hotel_count_normalized, total_score, dest_id))
    
    conn.commit()
    conn.close()
    return True

# Function to get database structure information
def get_database_info():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get countries
    cursor.execute('SELECT id, name, total_hotels FROM countries ORDER BY name')
    countries = cursor.fetchall()
    
    # Get cities with country names
    cursor.execute('''
        SELECT ci.id, ci.name, co.name, ci.total_hotels
        FROM cities ci
        JOIN countries co ON ci.country_id = co.id
        ORDER BY ci.name
    ''')
    cities = cursor.fetchall()
    
    # Get areas with city and country names  
    cursor.execute('''
        SELECT ar.id, ar.name, ci.name, co.name, ar.total_hotels
        FROM areas ar
        JOIN cities ci ON ar.city_id = ci.id
        JOIN countries co ON ci.country_id = co.id
        ORDER BY ar.name
    ''')
    areas = cursor.fetchall()
    
    # Get destination counts by type
    cursor.execute('SELECT type, COUNT(*) FROM destinations GROUP BY type ORDER BY type')
    destination_counts = cursor.fetchall()
    
    conn.close()
    
    return {
        'countries': countries,
        'cities': cities,
        'areas': areas,
        'destination_counts': destination_counts
    }

# Function to search destinations
def search_destinations(query):
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"
    cursor.execute('''
        SELECT 
            d.type, 
            d.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            f.rating,
            CASE 
                WHEN d.type = 'city' THEN ci.total_hotels
                WHEN d.type = 'area' THEN ar.total_hotels
                ELSE 0
            END as hotel_count,
            s.rating_normalized, 
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.rating_weight,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            co.total_hotels as country_total_hotels
        FROM destinations d
        JOIN destinations_fts fts ON d.id = fts.rowid
        LEFT JOIN countries co ON d.country_id = co.id
        LEFT JOIN cities ci ON d.city_id = ci.id
        LEFT JOIN areas ar ON d.area_id = ar.id
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
    
    # Notification about score bonus and hotel count structure
    st.info("📈 Cities with ratings of 90 or higher receive a 2x score bonus!")
    st.info("🏨 **Three-Factor Scoring**: Rating + Global Hotel Normalization + Country Hotel Normalization")
    st.info("🌍 Hotel counts normalized both globally and within each country for fair competition")
    
    # Weight adjustment sidebar
    st.sidebar.header("Factor Weights")
    st.sidebar.write("Adjust the importance of each factor (between 0 and 1)")
    
    # Get current weights from factor_weights table
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, rating_weight, hotel_count_weight, country_hotel_count_weight FROM factor_weights")
    weights_data = cursor.fetchall()
    conn.close()
    
    # Create dictionary of current weights by destination type
    current_weights = {}
    for dest_type, rating_weight, hotel_count_weight, country_hotel_count_weight in weights_data:
        current_weights[dest_type] = {
            'rating_weight': rating_weight,
            'hotel_count_weight': hotel_count_weight,
            'country_hotel_count_weight': country_hotel_count_weight
        }
    
    # Default values if no weights found (three-factor system)
    if 'city' not in current_weights:
        current_weights['city'] = {'rating_weight': 0.5, 'hotel_count_weight': 0.3, 'country_hotel_count_weight': 0.2}
    if 'area' not in current_weights:
        current_weights['area'] = {'rating_weight': 0.4, 'hotel_count_weight': 0.3, 'country_hotel_count_weight': 0.3}
    
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
                f"{dest_type.title()} Global Hotel Count Weight:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['hotel_count_weight']), 
                0.05
            )
            
            country_hotel_count_weight = st.slider(
                f"{dest_type.title()} Country Hotel Count Weight:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['country_hotel_count_weight']), 
                0.05
            )
            
            # Show weight sum for validation
            weight_sum = rating_weight + hotel_count_weight + country_hotel_count_weight
            if weight_sum > 0:
                st.write(f"Weight Sum: {weight_sum:.2f}")
                if weight_sum != 1.0:
                    st.warning("💡 Weights don't sum to 1.0 - will be normalized automatically")
            
            submit_weights = st.form_submit_button(f"Update {dest_type.title()} Weights")
            
            if submit_weights:
                if update_weights(dest_type, rating_weight, hotel_count_weight, country_hotel_count_weight):
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
                "Type", "Name", "Country", "City", "Area",
                "Rating", "Hotel Count", 
                "Rating (Normalized)", "Hotel Count (Normalized)", "Country Hotel Count (Normalized)",
                "Total Score", "Rating Weight", "Hotel Count Weight", "Country Hotel Count Weight", "Country Total Hotels"
            ])
            
            st.write(f"Found {len(results)} matching destinations:")
            
            # Show results with location hierarchy
            display_df = df[["Name", "Type", "Country", "City", "Area", "Total Score", "Rating (Normalized)", "Hotel Count (Normalized)", "Country Hotel Count (Normalized)", "Hotel Count", "Country Total Hotels"]]
            st.dataframe(display_df)
            
            # Show factor weights explanation
            with st.expander("View Factor Weights for Results"):
                # Group by type and show weights
                weights_df = df[["Type", "Rating Weight", "Hotel Count Weight", "Country Hotel Count Weight"]].drop_duplicates()
                st.dataframe(weights_df)
                
                st.markdown("""
                ### How scores are calculated:
                - Scores use **three weighted factors**: rating, global hotel normalization, and country hotel normalization
                - **Rating**: Destination rating (0-100 scale)
                - **Global Hotel Count Normalization**:
                  - **Cities**: city.total_hotels / max(city.total_hotels globally) × 100
                  - **Areas**: area.total_hotels / max(city.total_hotels globally) × 100
                - **Country Hotel Count Normalization**:
                  - **Cities**: city.total_hotels / max(city.total_hotels in same country) × 100
                  - **Areas**: area.total_hotels / max(city.total_hotels in same country) × 100
                - **Final Score**: (Rating × Rating Weight) + (Global Hotel Count Normalized × Global Hotel Count Weight) + (Country Hotel Count Normalized × Country Hotel Count Weight)
                - Cities with ratings ≥ 90 receive a 2× score bonus (capped at 100)
                
                ### Hotel Count Storage:
                - **Cities**: Hotel count stored in cities table as total_hotels
                - **Areas**: Hotel count stored in areas table as total_hotels  
                - **Countries**: Aggregated hotel count from all cities in that country
                
                ### Dual-Level Normalization Benefits:
                - **Global normalization** allows comparison across all destinations worldwide
                - **Country normalization** enables fair competition within regional markets
                - Areas can compete more effectively against cities within their country
                - Configurable weights allow balancing between global reach and local market dominance
                """)
        else:
            st.write("No matching destinations found.")
    
    # Database structure section
    st.sidebar.header("Database Structure")
    if st.sidebar.button("Show Database Structure"):
        info = get_database_info()
        
        st.subheader("Countries")
        st.write(info['countries'])
        
        st.subheader("Cities (with Countries)")
        st.write(info['cities'])
        
        st.subheader("Areas (with Cities and Countries)")
        st.write(info['areas'])
        
        st.subheader("Destination Counts by Type")
        st.write(info['destination_counts'])
    
    # Add database structure viewer
    with st.expander("📊 View Database Structure"):
        db_info = get_database_info()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Countries")
            if db_info['countries']:
                countries_df = pd.DataFrame(db_info['countries'], columns=['ID', 'Name', 'Total Hotels'])
                st.dataframe(countries_df, hide_index=True)
            else:
                st.write("No countries found")
        
        with col2:
            st.subheader("Cities")
            if db_info['cities']:
                cities_df = pd.DataFrame(db_info['cities'], columns=['ID', 'City', 'Country', 'Total Hotels'])
                st.dataframe(cities_df, hide_index=True)
            else:
                st.write("No cities found")
        
        with col3:
            st.subheader("Areas")
            if db_info['areas']:
                areas_df = pd.DataFrame(db_info['areas'], columns=['ID', 'Area', 'City', 'Country', 'Total Hotels'])
                st.dataframe(areas_df, hide_index=True)
            else:
                st.write("No areas found")
        
        # Show destination type counts
        if db_info['destination_counts']:
            st.subheader("Destination Summary")
            counts_df = pd.DataFrame(db_info['destination_counts'], columns=['Type', 'Count'])
            st.dataframe(counts_df, hide_index=True)

if __name__ == "__main__":
    main()