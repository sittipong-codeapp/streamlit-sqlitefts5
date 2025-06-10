import streamlit as st
import sqlite3
from csv_loader import load_csv_data, get_sample_data


# Function to connect to the database
def get_connection():
    return sqlite3.connect('destinations.db')


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

    # Create the hotel table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city_id INTEGER,
            area_id INTEGER,
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
            type TEXT CHECK(type IN ('city', 'area', 'hotel')),
            FOREIGN KEY (country_id) REFERENCES country(id),
            FOREIGN KEY (city_id) REFERENCES city(id),
            FOREIGN KEY (area_id) REFERENCES area(id)
        )
    ''')

    # Create the hotel_scores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotel_scores (
            hotel_id INTEGER PRIMARY KEY,
            agoda_score REAL DEFAULT 0,
            google_score REAL DEFAULT 0,
            FOREIGN KEY (hotel_id) REFERENCES hotel(id)
        )
    ''')

    # Create the country_outbound table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS country_outbound (
            country_id INTEGER PRIMARY KEY,
            expenditure_score REAL DEFAULT 0,
            departure_score REAL DEFAULT 0,
            FOREIGN KEY (country_id) REFERENCES country(id)
        )
    ''')

    # Create the factor weights table (for storing user preferences)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factor_weights (
            type TEXT PRIMARY KEY,  -- 'city', 'area', or 'hotel'
            hotel_count_weight REAL DEFAULT 0.25,
            country_hotel_count_weight REAL DEFAULT 0.25,
            agoda_score_weight REAL DEFAULT 0.25,
            google_score_weight REAL DEFAULT 0.25,
            expenditure_score_weight REAL DEFAULT 0.25,
            departure_score_weight REAL DEFAULT 0.25
        )
    ''')

    # Create the category weights table (for destination type priority)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_weights (
            type TEXT PRIMARY KEY,  -- 'city', 'area', or 'hotel'
            weight REAL DEFAULT 1.0
        )
    ''')

    # Create the destination_score table (stores pre-normalized values, NO total_score)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            hotel_count_normalized INTEGER DEFAULT 0,
            country_hotel_count_normalized INTEGER DEFAULT 0,
            agoda_score_normalized INTEGER DEFAULT 0,
            google_score_normalized INTEGER DEFAULT 0,
            expenditure_score_normalized INTEGER DEFAULT 0,
            departure_score_normalized INTEGER DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destination(id)
        )
    ''')

    # Remove the old total_score column and index if they exist
    cursor.execute("PRAGMA table_info(destination_score)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'total_score' in columns:
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        cursor.execute('''
            CREATE TABLE destination_score_new (
                destination_id INTEGER PRIMARY KEY,
                hotel_count_normalized INTEGER DEFAULT 0,
                country_hotel_count_normalized INTEGER DEFAULT 0,
                agoda_score_normalized INTEGER DEFAULT 0,
                google_score_normalized INTEGER DEFAULT 0,
                expenditure_score_normalized INTEGER DEFAULT 0,
                departure_score_normalized INTEGER DEFAULT 0,
                FOREIGN KEY (destination_id) REFERENCES destination(id)
            )
        ''')
        
        cursor.execute('''
            INSERT INTO destination_score_new 
            SELECT destination_id, hotel_count_normalized, country_hotel_count_normalized,
                   agoda_score_normalized, google_score_normalized, 
                   expenditure_score_normalized, departure_score_normalized
            FROM destination_score
        ''')
        
        cursor.execute('DROP TABLE destination_score')
        cursor.execute('ALTER TABLE destination_score_new RENAME TO destination_score')

    # Drop the old total_score index if it exists
    cursor.execute('DROP INDEX IF EXISTS idx_destination_score_total_score')

    # Create necessary indexes if they don't exist
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_city_country_id ON city(country_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_area_city_id ON area(city_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hotel_area_id ON hotel(area_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hotel_city_id ON hotel(city_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_destination_city_id ON destination(city_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_destination_area_id ON destination(area_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_destination_country_id ON destination(country_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_destination_type ON destination(type)')

    # Create separate FTS5 virtual tables for countries, cities and areas
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS country_fts USING fts5(name, content=country, content_rowid=id)
    ''')

    cursor.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS city_fts USING fts5(name, content=city, content_rowid=id)''')

    cursor.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS area_fts USING fts5(name, content=area, content_rowid=id)''')

    cursor.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS hotel_fts USING fts5(name, content=hotel, content_rowid=id)''')

    # Insert data from CSV files if the table is empty
    cursor.execute('SELECT COUNT(*) FROM destination')
    if cursor.fetchone()[0] == 0:
        # Create a placeholder for status message
        loading_placeholder = None
        if 'st' in globals():
            loading_placeholder = st.empty()
            loading_placeholder.write('Loading data from CSV files...')
        else:
            print('Loading data from CSV files...')

        # Load data from CSV files
        try:
            countries_data, cities_data, areas_data, hotels_data, destinations_data, hotel_scores_data, country_outbound_data = load_csv_data()
        except Exception as e:
            error_msg = f'Error loading CSV data: {e}'
            if 'st' in globals() and loading_placeholder:
                loading_placeholder.error(error_msg)
            else:
                print(error_msg)
            countries_data, cities_data, areas_data, hotels_data, destinations_data, hotel_scores_data, country_outbound_data = get_sample_data()

        if not countries_data:
            sample_msg = 'No country data found, using sample data...'
            if 'st' in globals() and loading_placeholder:
                loading_placeholder.write(sample_msg)
            else:
                print(sample_msg)
            # Fallback to sample data if CSV files are not available
            countries_data, cities_data, areas_data, hotels_data, destinations_data, hotel_scores_data, country_outbound_data = get_sample_data()
        else:
            success_msg = f'Loaded {len(countries_data)} countries, {len(cities_data)} cities, {len(areas_data)} areas, {len(hotels_data)} hotels, {len(destinations_data)} destinations, {len(country_outbound_data)} outbound scores'
            if 'st' in globals() and loading_placeholder:
                loading_placeholder.success(success_msg)
            else:
                print(success_msg)

        # Insert countries
        for country_id, country_info in countries_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO country (id, name, total_hotels) VALUES (?, ?, ?)',
                (country_id, country_info['name'], country_info['total_hotels']),
            )

        # Insert cities
        for city_id, city_info in cities_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO city (id, name, country_id, total_hotels) VALUES (?, ?, ?, ?)',
                (
                    city_id,
                    city_info['name'],
                    city_info['country_id'],
                    city_info['total_hotels'],
                ),
            )

        # Insert areas
        for area_id, area_info in areas_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO area (id, name, city_id, total_hotels) VALUES (?, ?, ?, ?)',
                (
                    area_id,
                    area_info['name'],
                    area_info['city_id'],
                    area_info['total_hotels'],
                ),
            )

        # Insert hotels
        for hotel_id, hotel_info in hotels_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO hotel (id, name, city_id, area_id) VALUES (?, ?, ?, ?)',
                (
                    hotel_id,
                    hotel_info['name'],
                    hotel_info['city_id'],
                    hotel_info['area_id'],
                ),
            )

        # Insert country outbound scores
        for country_id, outbound_info in country_outbound_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO country_outbound (country_id, expenditure_score, departure_score) VALUES (?, ?, ?)',
                (
                    country_id,
                    outbound_info['expenditure_score'],
                    outbound_info['departure_score'],
                ),
            )

        # Process destinations from CSV or create from cities/areas/hotels
        destinations_to_insert = []

        if destinations_data:
            # Use destinations from CSV file
            for dest in destinations_data:
                if dest['is_publish'] == 1:  # Only published destinations
                    if dest['area_id']:
                        # Area destination
                        area_info = areas_data.get(dest['area_id'])
                        if area_info:
                            destinations_to_insert.append(
                                (
                                    dest['id'],
                                    area_info['name'],
                                    dest['country_id'],
                                    dest['city_id'],
                                    dest['area_id'],
                                    'area',
                                )
                            )
                    elif dest['city_id']:
                        # City destination
                        city_info = cities_data.get(dest['city_id'])
                        if city_info:
                            destinations_to_insert.append(
                                (
                                    dest['id'],
                                    city_info['name'],
                                    dest['country_id'],
                                    dest['city_id'],
                                    None,
                                    'city',
                                )
                            )
                    elif dest['country_id']:
                        # Country-only destination (treat as city)
                        country_info = countries_data.get(dest['country_id'])
                        if country_info:
                            destinations_to_insert.append(
                                (
                                    dest['id'],
                                    country_info['name'],
                                    dest['country_id'],
                                    None,
                                    None,
                                    'city',
                                )
                            )
        else:
            # Create destinations from cities and areas if no destination CSV
            for city_id, city_info in cities_data.items():
                destinations_to_insert.append(
                    (
                        city_id,
                        city_info['name'],
                        city_info['country_id'],
                        city_id,
                        None,
                        'city',
                    )
                )

            for area_id, area_info in areas_data.items():
                city_info = cities_data.get(area_info['city_id'])
                if city_info:
                    destinations_to_insert.append(
                        (
                            area_id + 10000,  # Offset to avoid ID conflicts
                            area_info['name'],
                            city_info['country_id'],
                            area_info['city_id'],
                            area_id,
                            'area',
                        )
                    )

        # **Create hotel destinations with +20000 offset**
        for hotel_id, hotel_info in hotels_data.items():
            # Get country_id from the hotel's city
            city_info = cities_data.get(hotel_info['city_id'])
            if city_info:
                destinations_to_insert.append(
                    (
                        hotel_id + 20000,  # Offset to match search query
                        hotel_info['name'],
                        city_info['country_id'],
                        hotel_info['city_id'],
                        hotel_info['area_id'],
                        'hotel',
                    )
                )

        # Insert destinations
        for dest_data in destinations_to_insert:
            cursor.execute(
                'INSERT OR IGNORE INTO destination (id, name, country_id, city_id, area_id, type) VALUES (?, ?, ?, ?, ?, ?)',
                dest_data)

        # Update country total_hotels with aggregated hotel counts from their cities
        cursor.execute(
            '''
            UPDATE country 
            SET total_hotels = (
                SELECT COALESCE(SUM(city.total_hotels), 0)
                FROM city 
                WHERE city.country_id = country.id
            )
        '''
        )

        # Insert hotel scores
        for hotel_id, scores in hotel_scores_data.items():
            cursor.execute(
                'INSERT OR IGNORE INTO hotel_scores (hotel_id, agoda_score, google_score) VALUES (?, ?, ?)',
                (hotel_id, scores['agoda_score'], scores['google_score']),
            )

        # Insert into FTS tables
        cursor.execute(
            'INSERT INTO country_fts (rowid, name) SELECT id, name FROM country'
        )
        cursor.execute('INSERT INTO city_fts (rowid, name) SELECT id, name FROM city')
        cursor.execute('INSERT INTO area_fts (rowid, name) SELECT id, name FROM area')
        cursor.execute('INSERT INTO hotel_fts (rowid, name) SELECT id, name FROM hotel')

        # Set default factor weights (for user preferences)
        default_factor_weights = [
            ('city', 1.0, 0.625, 0, 0, 0.025, 0.025),
            ('area', 1.0, 0.625, 0, 0, 0.025, 0.025),
            ('hotel', 0.001, 0.001, 0.001, 0.001, 0.001, 0.001),
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO factor_weights (type, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight) VALUES (?, ?, ?, ?, ?, ?, ?)',
            default_factor_weights,
        )

        # Set default category weights (destination type priority)
        default_category_weights = [
            ('city', 10.0),   # Cities get highest priority
            ('area', 1.0),    # Areas get medium priority  
            ('hotel', 0.1),   # Hotels get lowest priority
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO category_weights (type, weight) VALUES (?, ?)',
            default_category_weights,
        )

        # Calculate and store ONLY normalized values (no total scores)
        _calculate_and_store_normalized_scores(cursor, countries_data, cities_data, areas_data, hotels_data)

        # Clear the loading message after loading is complete
        if 'st' in globals() and loading_placeholder:
            loading_placeholder.empty()

    # Ensure category weights exist even if data was already loaded (for upgrades)
    cursor.execute('SELECT COUNT(*) FROM category_weights')
    if cursor.fetchone()[0] == 0:
        default_category_weights = [
            ('city', 10.0),   # Cities get highest priority
            ('area', 1.0),    # Areas get medium priority  
            ('hotel', 0.1),   # Hotels get lowest priority
        ]
        cursor.executemany(
            'INSERT OR IGNORE INTO category_weights (type, weight) VALUES (?, ?)',
            default_category_weights,
        )

    conn.commit()
    conn.close()


def _calculate_and_store_normalized_scores(cursor, countries_data, cities_data, areas_data, hotels_data):
    """Calculate and store only normalized scores (0-100 scale) - no total scores"""
    
    # Get the maximum city hotel count for normalization
    cursor.execute('SELECT MAX(total_hotels) FROM city')
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1

    # Get max scores for normalization
    cursor.execute("SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores")
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100

    # Get all destinations for scoring with their relationships
    cursor.execute('''
        SELECT d.id, d.type, d.country_id, d.city_id, d.area_id 
        FROM destination d
    ''')
    destinations = cursor.fetchall()

    normalized_scores = []

    for dest_id, dest_type, country_id, city_id, area_id in destinations:
        if dest_type == 'hotel':
            # **Hotel normalized scores (6 factors)**
            hotel_id = dest_id - 20000  # Remove offset to get original hotel ID
            
            # Get hotel's own review scores
            cursor.execute('SELECT agoda_score, google_score FROM hotel_scores WHERE hotel_id = ?', (hotel_id,))
            result = cursor.fetchone()
            if result:
                agoda_score, google_score = result
            else:
                agoda_score, google_score = 0, 0
            
            # Normalize hotel review scores (0-100 scale)
            agoda_normalized = int((agoda_score / max_agoda_score) * 100) if agoda_score else 0
            google_normalized = int((google_score / max_google_score) * 100) if google_score else 0
            
            # Get the city's hotel normalization scores (inherit from parent city)
            city_info = cities_data.get(city_id)
            if city_info:
                city_hotel_count = city_info['total_hotels']
                
                # Calculate city's global hotel normalization
                city_hotel_count_normalized = int((city_hotel_count / max_city_hotels) * 100)
                
                # Calculate city's country hotel normalization
                cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
                max_country_result = cursor.fetchone()
                max_country_hotels = max_country_result[0] if max_country_result and max_country_result[0] else 1
                
                city_country_hotel_count_normalized = (
                    int((city_hotel_count / max_country_hotels) * 100)
                    if max_country_hotels > 200
                    else 0
                )
            else:
                city_hotel_count_normalized = 0
                city_country_hotel_count_normalized = 0
            
            # Get outbound scores for this country (inherit from parent country)
            cursor.execute(
                'SELECT expenditure_score, departure_score FROM country_outbound WHERE country_id = ?',
                (country_id,)
            )
            outbound_result = cursor.fetchone()
            if outbound_result:
                expenditure_score_normalized = int(outbound_result[0])
                departure_score_normalized = int(outbound_result[1])
            else:
                expenditure_score_normalized = 0
                departure_score_normalized = 0

            normalized_scores.append((
                dest_id,
                city_hotel_count_normalized,  # Inherited from city
                city_country_hotel_count_normalized,  # Inherited from city
                agoda_normalized,  # Hotel-specific
                google_normalized,  # Hotel-specific
                expenditure_score_normalized,  # Inherited from country
                departure_score_normalized,  # Inherited from country
            ))
            
        else:
            # **Cities and areas normalized scores (4 factors, agoda/google are 0)**
            if dest_type == 'city':
                cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
                result = cursor.fetchone()
                hotel_count = result[0] if result else 0
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)

                cursor.execute(
                    'SELECT MAX(total_hotels) FROM city WHERE country_id = ?',
                    (country_id,),
                )
                result = cursor.fetchone()
                max_country_city_hotels = result[0] if result and result[0] else 1
                country_hotel_count_normalized = (
                    int((hotel_count / max_country_city_hotels) * 100)
                    if max_country_city_hotels > 200
                    else 0
                )
            else:  # area
                cursor.execute('SELECT COUNT(*) FROM hotel WHERE area_id = ?', (area_id,))
                result = cursor.fetchone()
                hotel_count = result[0] if result else 0
                hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)

                cursor.execute(
                    'SELECT MAX(total_hotels) FROM city WHERE country_id = ?',
                    (country_id,),
                )
                result = cursor.fetchone()
                max_country_city_hotels = result[0] if result and result[0] else 1
                country_hotel_count_normalized = (
                    int((hotel_count / max_country_city_hotels) * 100)
                    if max_country_city_hotels > 200
                    else 0
                )

            # Get outbound scores for this country (already normalized to 0-100)
            cursor.execute(
                'SELECT expenditure_score, departure_score FROM country_outbound WHERE country_id = ?',
                (country_id,)
            )
            outbound_result = cursor.fetchone()
            if outbound_result:
                expenditure_score_normalized = int(outbound_result[0])
                departure_score_normalized = int(outbound_result[1])
            else:
                expenditure_score_normalized = 0
                departure_score_normalized = 0

            normalized_scores.append((
                dest_id,
                hotel_count_normalized,
                country_hotel_count_normalized,
                0,  # agoda_score_normalized (not applicable for cities/areas)
                0,  # google_score_normalized (not applicable for cities/areas)
                expenditure_score_normalized,
                departure_score_normalized,
            ))

    # Insert normalized scores (NO total_score calculation)
    cursor.executemany('''
        INSERT OR REPLACE INTO destination_score 
        (destination_id, hotel_count_normalized, country_hotel_count_normalized, 
         agoda_score_normalized, google_score_normalized, expenditure_score_normalized, 
         departure_score_normalized)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', normalized_scores)