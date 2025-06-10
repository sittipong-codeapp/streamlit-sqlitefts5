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

    # Create the factor weights table (all destination types now have 6 factors)
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

    # Create the score table (normalized factors and total score, all with 6 factors)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destination_score (
            destination_id INTEGER PRIMARY KEY,
            hotel_count_normalized INTEGER DEFAULT 0,
            country_hotel_count_normalized INTEGER DEFAULT 0,
            agoda_score_normalized INTEGER DEFAULT 0,
            google_score_normalized INTEGER DEFAULT 0,
            expenditure_score_normalized INTEGER DEFAULT 0,
            departure_score_normalized INTEGER DEFAULT 0,
            total_score REAL DEFAULT 0,
            FOREIGN KEY (destination_id) REFERENCES destination(id)
        )
    ''')

    # Create index on total_score for faster sorting in search results
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_destination_score_total_score 
        ON destination_score(total_score DESC)
    ''')

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

        # Set default weights
        city_hotel_count_weight = 1.0  # Global hotel count weight for cities
        city_country_hotel_count_weight = 0.25  # Country hotel count weight for cities
        city_expenditure_weight = 0.05  # Expenditure score weight for cities
        city_departure_weight = 0.05  # Departure score weight for cities

        area_hotel_count_weight = 1.0  # Global hotel count weight for areas
        area_country_hotel_count_weight = 0.25  # Country hotel count weight for areas
        area_expenditure_weight = 0.05  # Expenditure score weight for areas
        area_departure_weight = 0.05  # Departure score weight for areas

        # Hotels now use 6 factors: city normalization + hotel review scores + country outbound scores
        hotel_global_weight = 0.0  # Global hotel count weight for hotels (inherited from city)
        hotel_country_weight = 0.0  # Country hotel count weight for hotels (inherited from city)
        hotel_agoda_weight = 0.0  # Agoda score weight for hotels
        hotel_google_weight = 0.0  # Google score weight for hotels
        hotel_expenditure_weight = 0.0  # Expenditure score weight for hotels (inherited from country)
        hotel_departure_weight = 0.0  # Departure score weight for hotels (inherited from country)

        # Insert default factor weights (all destination types now have 6 factors)
        default_weights = [
            ('city', city_hotel_count_weight, city_country_hotel_count_weight, 0, 0, city_expenditure_weight, city_departure_weight),
            ('area', area_hotel_count_weight, area_country_hotel_count_weight, 0, 0, area_expenditure_weight, area_departure_weight),
            ('hotel', hotel_global_weight, hotel_country_weight, hotel_agoda_weight, hotel_google_weight, hotel_expenditure_weight, hotel_departure_weight),
        ]
        cursor.executemany(
            'INSERT INTO factor_weights (type, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight) VALUES (?, ?, ?, ?, ?, ?, ?)',
            default_weights,
        )

        # Calculate normalized hotel counts and scores
        # First, get the maximum city hotel count for normalization
        cursor.execute('SELECT MAX(total_hotels) FROM city')
        result = cursor.fetchone()
        max_city_hotels = (
            result[0] if result and result[0] else 1
        )  # Avoid division by zero

        # Get max scores for normalization
        cursor.execute("SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores")
        result = cursor.fetchone()
        max_agoda_score = result[0] if result and result[0] else 100
        max_google_score = result[1] if result and result[1] else 100

        # Create scores with normalized values from location tables
        scores = []

        # Get all destinations for scoring with their relationships
        cursor.execute('''
            SELECT d.id, d.type, d.country_id, d.city_id, d.area_id 
            FROM destination d
        ''')
        destinations = cursor.fetchall()

        for dest_id, dest_type, country_id, city_id, area_id in destinations:
            if dest_type == 'hotel':
                # **Hotel scores calculation (6 factors: city normalization + hotel review scores + country outbound scores)**
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
                
                # Calculate weighted total score with six factors
                weighted_sum = (
                    (city_hotel_count_normalized * hotel_global_weight) + 
                    (city_country_hotel_count_normalized * hotel_country_weight) +
                    (agoda_normalized * hotel_agoda_weight) + 
                    (google_normalized * hotel_google_weight) +
                    (expenditure_score_normalized * hotel_expenditure_weight) +
                    (departure_score_normalized * hotel_departure_weight)
                )
                factor_sum = hotel_global_weight + hotel_country_weight + hotel_agoda_weight + hotel_google_weight + hotel_expenditure_weight + hotel_departure_weight
                
                total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

                scores.append(
                    (
                        dest_id,
                        city_hotel_count_normalized,  # Inherited from city
                        city_country_hotel_count_normalized,  # Inherited from city
                        agoda_normalized,  # Hotel-specific
                        google_normalized,  # Hotel-specific
                        expenditure_score_normalized,  # Inherited from country
                        departure_score_normalized,  # Inherited from country
                        total_score,
                    )
                )
                
            else:
                # **Existing logic for cities and areas (4 factors)**
                # Get hotel count from appropriate location table using direct queries
                if dest_type == 'city':
                    cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
                    result = cursor.fetchone()
                    hotel_count = result[0] if result else 0
                    # Normalize city hotel count: city.total_hotels / max(city.total_hotels)
                    hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)

                    # Get max hotel count within the same country for country normalization
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
                    # For areas, count actual hotels in this area
                    cursor.execute('SELECT COUNT(*) FROM hotel WHERE area_id = ?', (area_id,))
                    result = cursor.fetchone()
                    hotel_count = result[0] if result else 0
                    # Normalize area hotel count: area hotel count / max(city.total_hotels)
                    hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)

                    # Get max hotel count within the same country for country normalization
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

                # Get weights for this destination type
                if dest_type == 'city':
                    hotel_count_weight = city_hotel_count_weight
                    country_hotel_count_weight = city_country_hotel_count_weight
                    expenditure_weight = city_expenditure_weight
                    departure_weight = city_departure_weight
                else:  # area
                    hotel_count_weight = area_hotel_count_weight
                    country_hotel_count_weight = area_country_hotel_count_weight
                    expenditure_weight = area_expenditure_weight
                    departure_weight = area_departure_weight

                # Calculate weighted total score with four factors
                weighted_sum = (
                    (hotel_count_normalized * hotel_count_weight) + 
                    (country_hotel_count_normalized * country_hotel_count_weight) +
                    (expenditure_score_normalized * expenditure_weight) +
                    (departure_score_normalized * departure_weight)
                )
                factor_sum = hotel_count_weight + country_hotel_count_weight + expenditure_weight + departure_weight

                total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

                scores.append(
                    (
                        dest_id,
                        hotel_count_normalized,
                        country_hotel_count_normalized,
                        0,  # agoda_score_normalized (not applicable for cities/areas)
                        0,  # google_score_normalized (not applicable for cities/areas)
                        expenditure_score_normalized,
                        departure_score_normalized,
                        total_score,
                    )
                )

        # Insert scores with all factors
        cursor.executemany(
            '''
            INSERT INTO destination_score (
                destination_id, hotel_count_normalized, country_hotel_count_normalized, 
                agoda_score_normalized, google_score_normalized, expenditure_score_normalized, 
                departure_score_normalized, total_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            scores,
        )
        # Clear the loading message after loading is complete
        if 'st' in globals() and loading_placeholder:
            loading_placeholder.empty()

    conn.commit()
    conn.close()