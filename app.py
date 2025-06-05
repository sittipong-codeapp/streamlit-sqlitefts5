import streamlit as st
import sqlite3
import pandas as pd
import csv
import os

# Function to load data from CSV files
def load_csv_data():
    """Load data from CSV files and return as dictionaries"""
    data_dir = 'data'
    
    # Load countries
    countries = {}
    country_file = os.path.join(data_dir, 'country.csv')
    if os.path.exists(country_file):
        try:
            with open(country_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        countries[int(row['id'])] = {
                            'name': row['name'],
                            'total_hotels': int(row.get('total_hotels', 0))
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f"Error reading country file: {e}")
    
    # Load cities
    cities = {}
    city_file = os.path.join(data_dir, 'city.csv')
    if os.path.exists(city_file):
        try:
            with open(city_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        cities[int(row['id'])] = {
                            'name': row['name'],
                            'country_id': int(row['country_id']),
                            'total_hotels': int(row.get('total_hotels', 0))
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f"Error reading city file: {e}")
    
    # Load areas
    areas = {}
    area_file = os.path.join(data_dir, 'area.csv')
    if os.path.exists(area_file):
        try:
            with open(area_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        areas[int(row['id'])] = {
                            'name': row['name'],
                            'city_id': int(row['city_id']),
                            'total_hotels': int(row.get('total_hotels', 0))
                        }
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f"Error reading area file: {e}")
    
    # Load destinations
    destinations = []
    destination_file = os.path.join(data_dir, 'destination.csv')
    if os.path.exists(destination_file):
        try:
            with open(destination_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Handle empty string values that should be None
                        country_id = int(row['country_id']) if row['country_id'] and row['country_id'].strip() else None
                        city_id = int(row['city_id']) if row['city_id'] and row['city_id'].strip() else None
                        area_id = int(row['area_id']) if row['area_id'] and row['area_id'].strip() else None
                        
                        destinations.append({
                            'id': int(row['id']),
                            'country_id': country_id,
                            'country_name': row.get('country_name', '').strip(),
                            'city_id': city_id,
                            'city_name': row.get('city_name', '').strip(),
                            'area_id': area_id,
                            'area_name': row.get('area_name', '').strip(),
                            'is_publish': int(row.get('is_publish', 1))
                        })
                    except (ValueError, KeyError) as e:
                        continue  # Skip invalid rows
        except Exception as e:
            print(f"Error reading destination file: {e}")
    
    # If no countries were loaded from CSV but we have destinations with country names,
    # create countries from destination data
    if not countries and destinations:
        country_names = set()
        for dest in destinations:
            if dest['country_name'] and dest['country_id']:
                country_names.add((dest['country_id'], dest['country_name']))
        
        for country_id, country_name in country_names:
            countries[country_id] = {
                'name': country_name,
                'total_hotels': 0
            }
    
    return countries, cities, areas, destinations

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
            total_score REAL DEFAULT 0,
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

    # Insert data from CSV files if the table is empty
    cursor.execute('SELECT COUNT(*) FROM destination')
    if cursor.fetchone()[0] == 0:
        st.write("Loading data from CSV files...") if 'st' in globals() else print("Loading data from CSV files...")
        
        # Load data from CSV files
        try:
            countries_data, cities_data, areas_data, destinations_data = load_csv_data()
        except Exception as e:
            st.error(f"Error loading CSV data: {e}") if 'st' in globals() else print(f"Error loading CSV data: {e}")
            countries_data, cities_data, areas_data, destinations_data = {}, {}, {}, []
        
        if not countries_data:
            st.write("No country data found, using sample data...") if 'st' in globals() else print("No country data found, using sample data...")
            # Fallback to sample data if CSV files are not available
            countries_data = {
                1: {'name': 'France', 'total_hotels': 0},
                2: {'name': 'United Kingdom', 'total_hotels': 0},
                3: {'name': 'United States', 'total_hotels': 0},
                4: {'name': 'Japan', 'total_hotels': 0}
            }
            cities_data = {
                1: {'name': 'Paris', 'country_id': 1, 'total_hotels': 320},
                2: {'name': 'London', 'country_id': 2, 'total_hotels': 270},
                3: {'name': 'New York', 'country_id': 3, 'total_hotels': 420},
                4: {'name': 'Tokyo', 'country_id': 4, 'total_hotels': 380}
            }
            areas_data = {
                1: {'name': 'Eiffel Tower', 'city_id': 1, 'total_hotels': 35},
                2: {'name': 'Buckingham Palace', 'city_id': 2, 'total_hotels': 15},
                3: {'name': 'Central Park', 'city_id': 3, 'total_hotels': 50},
                4: {'name': 'Shibuya Crossing', 'city_id': 4, 'total_hotels': 25}
            }
        else:
            msg = f"Loaded {len(countries_data)} countries, {len(cities_data)} cities, {len(areas_data)} areas, {len(destinations_data)} destinations"
            st.success(msg) if 'st' in globals() else print(msg)
        
        # Insert countries
        for country_id, country_info in countries_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO country (id, name, total_hotels) VALUES (?, ?, ?)',
                (country_id, country_info['name'], country_info['total_hotels'])
            )
        
        # Insert cities
        for city_id, city_info in cities_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO city (id, name, country_id, total_hotels) VALUES (?, ?, ?, ?)',
                (city_id, city_info['name'], city_info['country_id'], city_info['total_hotels'])
            )
        
        # Insert areas
        for area_id, area_info in areas_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO area (id, name, city_id, total_hotels) VALUES (?, ?, ?, ?)',
                (area_id, area_info['name'], area_info['city_id'], area_info['total_hotels'])
            )
        
        # Process destinations from CSV or create from cities/areas
        destinations_to_insert = []
        
        if destinations_data:
            # Use destinations from CSV file
            for dest in destinations_data:
                if dest['is_publish'] == 1:  # Only published destinations
                    if dest['area_id']:
                        # Area destination
                        area_info = areas_data.get(dest['area_id'])
                        if area_info:
                            destinations_to_insert.append((
                                dest['id'],
                                area_info['name'],
                                dest['country_id'],
                                dest['city_id'],
                                dest['area_id'],
                                'area'
                            ))
                    elif dest['city_id']:
                        # City destination
                        city_info = cities_data.get(dest['city_id'])
                        if city_info:
                            destinations_to_insert.append((
                                dest['id'],
                                city_info['name'],
                                dest['country_id'],
                                dest['city_id'],
                                None,
                                'city'
                            ))
                    elif dest['country_id']:
                        # Country-only destination (treat as city)
                        country_info = countries_data.get(dest['country_id'])
                        if country_info:
                            destinations_to_insert.append((
                                dest['id'],
                                country_info['name'],
                                dest['country_id'],
                                None,
                                None,
                                'city'
                            ))
        else:
            # Create destinations from cities and areas if no destination CSV
            for city_id, city_info in cities_data.items():
                destinations_to_insert.append((
                    city_id,
                    city_info['name'],
                    city_info['country_id'],
                    city_id,
                    None,
                    'city'
                ))
            
            for area_id, area_info in areas_data.items():
                city_info = cities_data.get(area_info['city_id'])
                if city_info:
                    destinations_to_insert.append((
                        area_id + 10000,  # Offset to avoid ID conflicts
                        area_info['name'],
                        city_info['country_id'],
                        area_info['city_id'],
                        area_id,
                        'area'
                    ))
        
        # Insert destinations
        for dest_data in destinations_to_insert:
            cursor.execute(
                'INSERT OR IGNORE INTO destination (id, name, country_id, city_id, area_id, type) VALUES (?, ?, ?, ?, ?, ?)',
                dest_data
            )
        
        # Update country total_hotels with aggregated hotel counts from their cities
        cursor.execute('''
            UPDATE country 
            SET total_hotels = (
                SELECT COALESCE(SUM(city.total_hotels), 0)
                FROM city 
                WHERE city.country_id = country.id
            )
        ''')
        
        # Insert into FTS tables
        cursor.execute('INSERT INTO country_fts (rowid, name) SELECT id, name FROM country')
        cursor.execute('INSERT INTO city_fts (rowid, name) SELECT id, name FROM city')
        cursor.execute('INSERT INTO area_fts (rowid, name) SELECT id, name FROM area')
        
        # Set default weights with two-factor weighting (no rating)
        city_hotel_count_weight = 0.8  # Global hotel count weight for cities
        city_country_hotel_count_weight = 0.05  # Country hotel count weight for cities
        area_hotel_count_weight = 0.4  # Global hotel count weight for areas
        area_country_hotel_count_weight = 0.05  # Country hotel count weight for areas
        
        # Insert default factor weights (removed rating)
        default_weights = [
            ('city', city_hotel_count_weight, city_country_hotel_count_weight),
            ('area', area_hotel_count_weight, area_country_hotel_count_weight)
        ]
        cursor.executemany('INSERT INTO factor_weights (type, hotel_count_weight, country_hotel_count_weight) VALUES (?, ?, ?)', default_weights)
        
        # Calculate normalized hotel counts and scores
        # First, get the maximum city hotel count for normalization
        cursor.execute('SELECT MAX(total_hotels) FROM city')
        result = cursor.fetchone()
        max_city_hotels = result[0] if result and result[0] else 1  # Avoid division by zero
        
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
                result = cursor.fetchone()
                hotel_count = result[0] if result else 0
                # Normalize city hotel count: city.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM city ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                result = cursor.fetchone()
                max_country_city_hotels = result[0] if result and result[0] else 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100) if max_country_city_hotels > 200 else 0
            else:  # area
                cursor.execute('''
                    SELECT ar.total_hotels 
                    FROM destination d 
                    JOIN area ar ON d.area_id = ar.id 
                    WHERE d.id = ?
                ''', (dest_id,))
                result = cursor.fetchone()
                hotel_count = result[0] if result else 0
                # Normalize area hotel count: area.total_hotels / max(city.total_hotels)
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
                
                # Get max hotel count within the same country for country normalization
                cursor.execute('''
                    SELECT MAX(ci.total_hotels) 
                    FROM city ci 
                    WHERE ci.country_id = ?
                ''', (country_id,))
                result = cursor.fetchone()
                max_country_city_hotels = result[0] if result and result[0] else 1
                country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100) if max_country_city_hotels > 200 else 0
            
            # Get weights for this destination type
            if dest_type == 'city':
                hotel_count_weight = city_hotel_count_weight
                country_hotel_count_weight = city_country_hotel_count_weight
            else:  # area
                hotel_count_weight = area_hotel_count_weight
                country_hotel_count_weight = area_country_hotel_count_weight
            
            # Calculate weighted total score with two factors (no rating)
            weighted_sum = (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
            factor_count = 2
            
            # Boost score for Thailand
            boost_up = 3 * factor_count if country_id == 106 else 1
            
            total_score = weighted_sum * boost_up / factor_count if factor_count > 0 else 0
            
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
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1
    
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
        result = cursor.fetchone()
        country_id = result[0] if result else None
        
        if not country_id:
            continue  # Skip if no country_id
        
        # Get hotel count from appropriate location table and normalize
        if dest_type == 'city':
            cursor.execute('''
                SELECT ci.total_hotels 
                FROM destination d 
                JOIN city ci ON d.city_id = ci.id 
                WHERE d.id = ?
            ''', (dest_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1
        else:  # area
            cursor.execute('''
                SELECT ar.total_hotels 
                FROM destination d 
                JOIN area ar ON d.area_id = ar.id 
                WHERE d.id = ?
            ''', (dest_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0
            
            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1
        
        # Normalize hotel counts - global and country level
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = int((hotel_count / max_country_city_hotels) * 100) if max_country_city_hotels > 200 else 0
        
        # Calculate weighted total score with two factors (no rating)
        weighted_sum = (hotel_count_normalized * hotel_count_weight) + (country_hotel_count_normalized * country_hotel_count_weight)
        factor_count = 2
        
        # Boost score for Thailand
        boost_up = 3 * factor_count if country_id == 106 else 1
        
        total_score = weighted_sum * boost_up / factor_count if factor_count > 0 else 0
        
        # Update the score
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''', (hotel_count_normalized, country_hotel_count_normalized, total_score, dest_id))
    
    conn.commit()
    conn.close()
    return True

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
        
        ORDER BY total_score DESC, hotel_count DESC
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
        page_title="Search Suggestion Sandbox",
        initial_sidebar_state="collapsed"
    )
    
    # Web interface
    st.title("🔍 Search Suggestion Sandbox")
    
    # Simplified sidebar header
    st.sidebar.header("Factor Weight Configuration")
    
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
    Customize the importance of each factor for optimal search results:
    - **Global Hotel Normalization**: Compare destinations worldwide
    - **Country Hotel Normalization**: Compare destinations within the same country
    
    *Adjust weights below to fine-tune your search experience.*
    """)
    
    dest_types = ['city', 'area']
    
    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")
        
        with st.sidebar.form(f"{dest_type}_weight_form"):
            hotel_count_weight = st.slider(
                f"Global Hotel Normalization:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['hotel_count_weight']), 
                0.05
            )
            
            country_hotel_count_weight = st.slider(
                f"Country Hotel Normalization:", 
                0.0, 1.0, 
                float(current_weights[dest_type]['country_hotel_count_weight']), 
                0.05
            )
            
            # Show weight sum for validation
            weight_sum = hotel_count_weight + country_hotel_count_weight
            if weight_sum > 0:
                st.write(f"Weight Sum: {weight_sum:.2f}")
            
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
                "Normalized: Global Hotel Count", "Normalized: Country Hotel Count",
                "Total Score", "Hotel Count Weight", "Country Hotel Count Weight", "Country Total Hotels"
            ])
            
            # Create a display name column that formats differently based on type
            df["Display Name"] = df.apply(
                lambda row: f"{row['Name']}, {row['City']}" if row["Type"] == "area" else row["Name"], 
                axis=1
            )
            
            st.write(f"Found {len(results)} matching destinations:")
            
            # Show results with location hierarchy
            display_df = df[["Display Name", "Type", "Country", "Total Score", "Normalized: Global Hotel Count", "Normalized: Country Hotel Count", "Hotel Count", "Country Total Hotels"]]
            st.dataframe(
                display_df,
                column_config={
                    "Display Name": st.column_config.TextColumn(width="medium"),
                    "Total Score": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            
            # Show factor weights explanation
            with st.expander("View Factor Weights for Results"):
                # Group by type and show weights
                weights_df = df[["Type", "Hotel Count Weight", "Country Hotel Count Weight"]].drop_duplicates()
                st.dataframe(weights_df)
        else:
            st.write("No matching destinations found.")

if __name__ == "__main__":
    main()