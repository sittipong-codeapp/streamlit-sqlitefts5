import streamlit as st
import sqlite3
import pandas as pd

# Function to initialize the SQLite database
def init_database():
    conn = sqlite3.connect('destinations.db')
    cursor = conn.cursor()

    # Create the country table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS country (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            total_hotels INTEGER DEFAULT 0
        )
    ''')
    
    # Create the city table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS city (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER,
            total_hotels INTEGER DEFAULT 0,
            FOREIGN KEY (country_id) REFERENCES country(id)
        )
    ''')
    
    # Create the area table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS area (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city_id INTEGER,
            total_hotels INTEGER DEFAULT 0,
            FOREIGN KEY (city_id) REFERENCES city(id)
        )
    ''')

    # Create the destination table (now with foreign keys)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country_id INTEGER,
            city_id INTEGER,
            area_id INTEGER,
            type TEXT CHECK(type IN ('city', 'area')),
            FOREIGN KEY (country_id) REFERENCES country(id),
            FOREIGN KEY (city_id) REFERENCES city(id),
            FOREIGN KEY (area_id) REFERENCES area(id)
        )
    ''')
    
    # Create the factor weights table (removed rating factor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factor_weights (
            type TEXT PRIMARY KEY,  -- 'city' or 'area'
            hotel_count_weight REAL DEFAULT 0.5,
            country_hotel_count_weight REAL DEFAULT 0.5
        )
    ''')
    
    # Create the score table (normalized factors and total score, removed rating)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            hotel_count_normalized INTEGER DEFAULT 0,
            country_hotel_count_normalized INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destination(id)
        )
    ''')

    # Create separate FTS5 virtual tables for countries, cities and areas
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS country_fts USING fts5(name, content=country, content_rowid=id)
    ''')
    
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS city_fts USING fts5(name, content=city, content_rowid=id)
    ''')
    
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS area_fts USING fts5(name, content=area, content_rowid=id)
    ''')

    # Insert sample data if the table is empty
    cursor.execute('SELECT COUNT(*) FROM destination')
    if cursor.fetchone()[0] == 0:
        # Insert countries first
        countries_data = [
            ('France',),
            ('United Kingdom',),
            ('United States',),
            ('Japan',)
        ]
        cursor.executemany('INSERT INTO country (name) VALUES (?)', countries_data)
        
        # Get country IDs for reference
        cursor.execute('SELECT id, name FROM country')
        country_map = {name: id for id, name in cursor.fetchall()}
        
        # Insert cities
        cities_data = [
            ('Paris', country_map['France']),
            ('London', country_map['United Kingdom']),
            ('New York', country_map['United States']),
            ('Tokyo', country_map['Japan'])
        ]
        cursor.executemany('INSERT INTO city (name, country_id) VALUES (?, ?)', cities_data)
        
        # Get city IDs for reference
        cursor.execute('SELECT id, name FROM city')
        city_map = {name: id for id, name in cursor.fetchall()}
        
        # Insert areas
        areas_data = [
            ('Eiffel Tower', city_map['Paris']),
            ('Buckingham Palace', city_map['London']),
            ('Central Park', city_map['New York']),
            ('Shibuya Crossing', city_map['Tokyo'])
        ]
        cursor.executemany('INSERT INTO area (name, city_id) VALUES (?, ?)', areas_data)
        
        # Get area IDs for reference
        cursor.execute('SELECT id, name FROM area')
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
        cursor.executemany('INSERT INTO destination (name, country_id, city_id, area_id, type) VALUES (?, ?, ?, ?, ?)', destinations_data)
        
        # Insert into separate FTS tables
        cursor.execute('INSERT INTO country_fts (rowid, name) SELECT id, name FROM country')
        cursor.execute('INSERT INTO city_fts (rowid, name) SELECT id, name FROM city')
        cursor.execute('INSERT INTO area_fts (rowid, name) SELECT id, name FROM area')
        
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
        
        # Update city with total_hotels
        for city_name, hotel_count in city_hotel_counts.items():
            cursor.execute('UPDATE city SET total_hotels = ? WHERE name = ?', (hotel_count, city_name))
        
        # Update area with total_hotels
        for area_name, hotel_count in area_hotel_counts.items():
            cursor.execute('UPDATE area SET total_hotels = ? WHERE name = ?', (hotel_count, area_name))
        
        # Update country with aggregated hotel counts from their cities
        cursor.execute('''
            UPDATE country 
            SET total_hotels = (
                SELECT COALESCE(SUM(city.total_hotels), 0)
                FROM city 
                WHERE city.country_id = country.id
            )
        ''')
        
        # Set default weights with two-factor weighting (no rating)
        city_hotel_count_weight = 0.8  # Global hotel count weight for cities
        city_country_hotel_count_weight = 0.5  # Country hotel count weight for cities
        area_hotel_count_weight = 0.8  # Global hotel count weight for areas
        area_country_hotel_count_weight = 0.5  # Country hotel count weight for areas
        
        # Insert default factor weights (removed rating)
        default_weights = [
            ('city', city_hotel_count_weight, city_country_hotel_count_weight),
            ('area', area_hotel_count_weight, area_country_hotel_count_weight)
        ]
        cursor.executemany('INSERT INTO factor_weights (type, hotel_count_weight, country_hotel_count_weight) VALUES (?, ?, ?)', default_weights)
        
        # Calculate normalized hotel counts and scores
        # First, get the maximum city hotel count for normalization
        cursor.execute('SELECT MAX(total_hotels) FROM city')
        max_city_hotels = cursor.fetchone()[0] or 1  # Avoid division by zero
        
        # Create scores with normalized hotel counts from location tables
        scores = []
        
        # Get all destinations for scoring
        cursor.execute('SELECT id, type, country_id FROM destination')
        destinations = cursor.fetchall()
        
        for dest_id, dest_type, country_id in destinations:
            # Get hotel count from appropriate location table
            if dest_type == 'city':
                cursor.execute('''
                    SELECT ci.total_hotels 
                    FROM destination d 
                    JOIN city ci ON d.city_id = ci.id 
                    WHERE d.id = ?
                ''', (dest_id,))
                hotel_count = cursor.fetchone()[0] or 0
                # Normalize city hotel count: city.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM city ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                max_country_city_hotels = cursor.fetchone()[0] or 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
            else:  # area
                cursor.execute('''
                    SELECT ar.total_hotels 
                    FROM destination d 
                    JOIN area ar ON d.area_id = ar.id 
                    WHERE d.id = ?
                ''', (dest_id,))
                hotel_count = cursor.fetchone()[0] or 0
                # Normalize area hotel count: area.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM city ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                max_country_city_hotels = cursor.fetchone()[0] or 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
            
            # Get weights for this destination type
            if dest_type == 'city':
                hotel_count_weight = city_hotel_count_weight
                country_hotel_count_weight = city_country_hotel_count_weight
            else:  # area
                hotel_count_weight = area_hotel_count_weight
                country_hotel_count_weight = area_country_hotel_count_weight
            
            # Calculate weighted total score with two factors (no rating)
            weighted_sum = (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
            weights_sum = hotel_count_weight + country_hotel_count_weight
            total_score = int(weighted_sum / weights_sum) if weights_sum > 0 else 0
            
            scores.append((
                dest_id, 
                hotel_count_normalized,
                country_hotel_count_normalized,
                total_score
            ))
        
        # Insert scores with both hotel count normalizations (no rating)
        cursor.executemany('''
            INSERT INTO destination_score (
                destination_id, hotel_count_normalized, country_hotel_count_normalized, total_score
            ) VALUES (?, ?, ?, ?)
        ''', scores)

    conn.commit()
    conn.close()

# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')

# Function to update factor weights and recalculate total score
def update_weights(dest_type, hotel_count_weight, country_hotel_count_weight):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Validate weights (should be between 0 and 1)
    if not (0 <= hotel_count_weight <= 1 and 0 <= country_hotel_count_weight <= 1):
        conn.close()
        return False
    
    # Validate destination type
    if dest_type not in ['city', 'area']:
        conn.close()
        return False
    
    # Update the weights for the specified destination type
    cursor.execute('''
        UPDATE factor_weights
        SET hotel_count_weight = ?,
            country_hotel_count_weight = ?
        WHERE type = ?
    ''', (hotel_count_weight, country_hotel_count_weight, dest_type))
    
    # Get max city hotel count for normalization
    cursor.execute('SELECT MAX(total_hotels) FROM city')
    max_city_hotels = cursor.fetchone()[0] or 1
    
    # For each destination of the specified type, recalculate the score
    cursor.execute('SELECT id FROM destination WHERE type = ?', (dest_type,))
    dest_ids = [row[0] for row in cursor.fetchall()]
    
    for dest_id in dest_ids:
        # Get country
        cursor.execute('''
            SELECT d.country_id 
            FROM destination d 
            WHERE d.id = ?
        ''', (dest_id,))
        country_id = cursor.fetchone()[0]
        
        # Get hotel count from appropriate location table and normalize
        if dest_type == 'city':
            cursor.execute('''
                SELECT ci.total_hotels 
                FROM destination d 
                JOIN city ci ON d.city_id = ci.id 
                WHERE d.id = ?
            ''', (dest_id,))
            hotel_count = cursor.fetchone()[0] or 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            max_country_city_hotels = cursor.fetchone()[0] or 1
        else:  # area
            cursor.execute('''
                SELECT ar.total_hotels 
                FROM destination d 
                JOIN area ar ON d.area_id = ar.id 
                WHERE d.id = ?
            ''', (dest_id,))
            hotel_count = cursor.fetchone()[0] or 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            max_country_city_hotels = cursor.fetchone()[0] or 1
        
        # Normalize hotel counts - global and country level
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100)
        
        # Calculate weighted total score with two factors (no rating)
        weighted_sum = (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
        weights_sum = hotel_count_weight + country_hotel_count_weight
        total_score = int(weighted_sum / weights_sum) if weights_sum > 0 else 0
        
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
    cursor.execute('SELECT id, name, total_hotels FROM country ORDER BY name')
    countries = cursor.fetchall()
    
    # Get cities with country names
    cursor.execute('''
        SELECT ci.id, ci.name, co.name, ci.total_hotels
        FROM city ci
        JOIN country co ON ci.country_id = co.id
        ORDER BY ci.name
    ''')
    cities = cursor.fetchall()
    
    # Get areas with city and country names  
    cursor.execute('''
        SELECT ar.id, ar.name, ci.name, co.name, ar.total_hotels
        FROM area ar
        JOIN city ci ON ar.city_id = ci.id
        JOIN country co ON ci.country_id = co.id
        ORDER BY ar.name
    ''')
    areas = cursor.fetchall()
    
    # Get destination counts by type
    cursor.execute('SELECT type, COUNT(*) FROM destination GROUP BY type ORDER BY type')
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
    
    # Enhanced search with multiple FTS strategies:
    # 1. Direct city name match (FTS search)
    # 2. Direct area name match (FTS search)
    # 3. Cities by country name match (FTS search on country names)
    # 4. Areas by city name match (FTS search on city names)
    cursor.execute('''
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            co.total_hotels as country_total_hotels,
            'direct_city' as match_type
        FROM city ci
        JOIN city_fts fts ON ci.id = fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'city'
        WHERE fts.name MATCH ?
        
        UNION
        
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            ar.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            co.total_hotels as country_total_hotels,
            'direct_area' as match_type
        FROM area ar
        JOIN area_fts fts ON ar.id = fts.rowid
        LEFT JOIN city ci ON ar.city_id = ci.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'area'
        WHERE fts.name MATCH ?
        
        UNION
        
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            co.total_hotels as country_total_hotels,
            'city_by_country_fts' as match_type
        FROM city ci
        LEFT JOIN country co ON ci.country_id = co.id
        JOIN country_fts country_fts ON co.id = country_fts.rowid
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'city'
        WHERE country_fts.name MATCH ?
        
        UNION
        
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            ar.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            co.total_hotels as country_total_hotels,
            'area_by_city_fts' as match_type
        FROM area ar
        LEFT JOIN city ci ON ar.city_id = ci.id
        JOIN city_fts city_fts ON ci.id = city_fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'area'
        WHERE city_fts.name MATCH ?
        
        ORDER BY total_score DESC
        LIMIT 20
    ''', (match_pattern, match_pattern, match_pattern, match_pattern))
    
    # Remove the match_type column from results before returning
    results = cursor.fetchall()
    results = [row[:-1] for row in results]  # Remove last column (match_type)
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
    st.title("🎯 Destination Search Engine")
    st.write("**Enhanced FTS Search with Multi-Strategy Support** - Search destinations with flexible query options")
    
    # Enhanced search capabilities info
    st.info("""
    🔍 **Enhanced FTS Search Capabilities**:
    • **Direct Search**: Find cities and areas by name using Full Text Search
    • **City by Country (FTS)**: Find cities by typing country names (e.g., "France" → Paris)
    • **Area by City (FTS)**: Find areas by typing city names (e.g., "Paris" → Eiffel Tower)  
    • **Two-Factor Scoring**: Global Hotel Count + Country Hotel Count with adjustable weights
    • **Prefix Matching**: "Franc" finds "France", "Par" finds "Paris"
    """)
    
    # Simplified sidebar header
    st.sidebar.header("⚖️ Factor Weight Configuration")
    st.sidebar.write("Adjust the importance of each factor for your search preferences")
    
    # Get current weights from factor_weights table
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, hotel_count_weight, country_hotel_count_weight FROM factor_weights")
    weights_data = cursor.fetchall()
    conn.close()
    
    # Create dictionary of current weights by destination type
    current_weights = {}
    for dest_type, hotel_count_weight, country_hotel_count_weight in weights_data:
        current_weights[dest_type] = {
            'hotel_count_weight': hotel_count_weight,
            'country_hotel_count_weight': country_hotel_count_weight
        }
    
    # Default values if no weights found (two-factor system)
    if 'city' not in current_weights:
        current_weights['city'] = {'hotel_count_weight': 0.5, 'country_hotel_count_weight': 0.5}
    if 'area' not in current_weights:
        current_weights['area'] = {'hotel_count_weight': 0.5, 'country_hotel_count_weight': 0.5}
    
    # Weight adjustment forms - one for each destination type
    st.sidebar.markdown("""
    ### 🎯 Two-Factor Scoring System
    **Adjustable Weight Configuration**
    
    Customize the importance of each factor for optimal search results:
    - **Global Hotel Normalization**: Compare destinations worldwide
    - **Country Hotel Normalization**: Fair regional competition
    
    *Adjust weights below to fine-tune your search experience.*
    """)
    
    dest_types = ['city', 'area']
    
    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")
        
        with st.sidebar.form(f"{dest_type}_weight_form"):
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
            weight_sum = hotel_count_weight + country_hotel_count_weight
            if weight_sum > 0:
                st.write(f"Weight Sum: {weight_sum:.2f}")
                if weight_sum != 1.0:
                    st.warning("💡 Weights don't sum to 1.0 - will be normalized automatically")
            
            submit_weights = st.form_submit_button(f"Update {dest_type.title()} Weights")
            
            if submit_weights:
                if update_weights(dest_type, hotel_count_weight, country_hotel_count_weight):
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
                "Hotel Count", 
                "Hotel Count (Normalized)", "Country Hotel Count (Normalized)",
                "Total Score", "Hotel Count Weight", "Country Hotel Count Weight", "Country Total Hotels"
            ])
            
            st.write(f"Found {len(results)} matching destinations:")
            
            # Show results with location hierarchy
            display_df = df[["Name", "Type", "Country", "City", "Area", "Total Score", "Hotel Count (Normalized)", "Country Hotel Count (Normalized)", "Hotel Count", "Country Total Hotels"]]
            st.dataframe(display_df)
            
            # Show factor weights explanation
            with st.expander("View Factor Weights for Results"):
                # Group by type and show weights
                weights_df = df[["Type", "Hotel Count Weight", "Country Hotel Count Weight"]].drop_duplicates()
                st.dataframe(weights_df)
                
                st.markdown("""
                ### 🎯 Two-Factor Scoring System:
                **Customizable weights for personalized search results:**
                
                - **Global Hotel Count (adjustable weight)**: Compare destinations worldwide
                  - **Cities**: city.total_hotels / max(city.total_hotels globally) × 100
                  - **Areas**: area.total_hotels / max(city.total_hotels globally) × 100
                
                - **Country Hotel Count (adjustable weight)**: Fair regional competition  
                  - **Cities**: city.total_hotels / max(city.total_hotels in same country) × 100
                  - **Areas**: area.total_hotels / max(city.total_hotels in same country) × 100
                
                - **Final Score**: (Global Hotel Count × Global Weight) + (Country Hotel Count × Country Weight)
                
                ### Weight Configuration Benefits:
                - **Customizable balance** - adjust global vs regional focus
                - **Personalized results** - tune weights for your travel preferences
                - **Fair competition** - areas can compete with cities in their region
                - **Real-time updates** - changes apply immediately to search results
                
                ### Hotel Count Storage:
                - **Cities**: Hotel count stored directly in city.total_hotels
                - **Areas**: Hotel count stored directly in area.total_hotels  
                - **Countries**: Automatically calculated from constituent cities
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