from database import get_connection


# Function to update factor weights and recalculate total score
def update_weights(dest_type, hotel_count_weight=0, country_hotel_count_weight=0, agoda_score_weight=0, google_score_weight=0, expenditure_score_weight=0, departure_score_weight=0):
    conn = get_connection()
    cursor = conn.cursor()

    # Validate weights (should be between 0 and 1)
    if not all(0 <= w <= 1 for w in [hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight]):
        conn.close()
        return False

    # Validate destination type
    if dest_type not in ["city", "area", "hotel"]:
        conn.close()
        return False

    # Update the weights for the specified destination type
    if dest_type == "hotel":
        cursor.execute('''
            UPDATE factor_weights
            SET agoda_score_weight = ?,
                google_score_weight = ?,
                expenditure_score_weight = ?,
                departure_score_weight = ?
            WHERE type = ?
        ''', (agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight, dest_type))
    else:
        cursor.execute('''
            UPDATE factor_weights
            SET hotel_count_weight = ?,
                country_hotel_count_weight = ?,
                expenditure_score_weight = ?,
                departure_score_weight = ?
            WHERE type = ?
        ''', (hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight, dest_type))

    # Recalculate scores based on destination type
    if dest_type == "hotel":
        _recalculate_hotel_scores(cursor, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight)
    else:
        _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight)

    conn.commit()
    conn.close()
    return True


def _recalculate_hotel_scores(cursor, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight):
    """Recalculate scores for hotels based on agoda, google, expenditure and departure scores"""
    
    # Get max scores for normalization
    cursor.execute("SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores")
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100

    # Get all hotel destinations using the offset
    cursor.execute('''
        SELECT d.id as destination_id, d.country_id
        FROM destination d
        WHERE d.type = 'hotel'
    ''')
    hotel_destinations = cursor.fetchall()

    for destination_id, country_id in hotel_destinations:
        # Get original hotel ID by removing offset
        hotel_id = destination_id - 20000
        
        # Get hotel scores
        cursor.execute('SELECT agoda_score, google_score FROM hotel_scores WHERE hotel_id = ?', (hotel_id,))
        result = cursor.fetchone()
        if result:
            agoda_score, google_score = result
        else:
            agoda_score, google_score = 0, 0
        
        # Normalize scores (0-100 scale)
        agoda_normalized = int((agoda_score / max_agoda_score) * 100) if agoda_score else 0
        google_normalized = int((google_score / max_google_score) * 100) if google_score else 0
        
        # Get outbound scores for this country
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
        
        # Calculate weighted total score with four factors
        weighted_sum = (
            (agoda_normalized * agoda_score_weight) + 
            (google_normalized * google_score_weight) +
            (expenditure_score_normalized * expenditure_score_weight) +
            (departure_score_normalized * departure_score_weight)
        )
        factor_sum = agoda_score_weight + google_score_weight + expenditure_score_weight + departure_score_weight
        
        total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

        # Update score for hotel using destination_id, with 0 for hotel count factors
        cursor.execute('''
            INSERT OR REPLACE INTO destination_score 
            (destination_id, hotel_count_normalized, country_hotel_count_normalized, 
             agoda_score_normalized, google_score_normalized, expenditure_score_normalized, 
             departure_score_normalized, total_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (destination_id, 0, 0, agoda_normalized, google_normalized, expenditure_score_normalized, departure_score_normalized, total_score))


def _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight):
    """Recalculate scores for cities and areas with four factors"""
    
    # Get max city hotel count for normalization
    cursor.execute("SELECT MAX(total_hotels) FROM city")
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1

    # Get all destinations of the specified type with their relationships
    cursor.execute("SELECT id, city_id, area_id, country_id FROM destination WHERE type = ?", (dest_type,))
    destinations = cursor.fetchall()

    for dest_id, city_id, area_id, country_id in destinations:
        if not country_id:
            continue

        # Get hotel count from appropriate location table using direct queries
        if dest_type == "city":
            cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1
        else:  # area
            # For areas, count actual hotels in this area
            cursor.execute('SELECT COUNT(*) FROM hotel WHERE area_id = ?', (area_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1

        # Normalize hotel counts
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = (
            int((hotel_count / max_country_city_hotels) * 100)
            if max_country_city_hotels > 200
            else 0
        )

        # Get outbound scores for this country
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

        # Calculate weighted total score with four factors
        weighted_sum = (
            (hotel_count_normalized * hotel_count_weight) + 
            (country_hotel_count_normalized * country_hotel_count_weight) +
            (expenditure_score_normalized * expenditure_score_weight) +
            (departure_score_normalized * departure_score_weight)
        )
        factor_sum = hotel_count_weight + country_hotel_count_weight + expenditure_score_weight + departure_score_weight

        total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

        # Update the score
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, 
                expenditure_score_normalized = ?, departure_score_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''', (hotel_count_normalized, country_hotel_count_normalized, expenditure_score_normalized, departure_score_normalized, total_score, dest_id))


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
        -- direct_city
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.agoda_score_normalized,
            s.google_score_normalized,
            s.expenditure_score_normalized,
            s.departure_score_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            w.agoda_score_weight,
            w.google_score_weight,
            w.expenditure_score_weight,
            w.departure_score_weight,
            co.total_hotels as country_total_hotels
        FROM city ci
        JOIN city_fts fts ON ci.id = fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'city'
        WHERE fts.name MATCH ?
        
        UNION
        
        -- direct_area
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            (SELECT COUNT(*) FROM hotel WHERE area_id = ar.id) as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.agoda_score_normalized,
            s.google_score_normalized,
            s.expenditure_score_normalized,
            s.departure_score_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            w.agoda_score_weight,
            w.google_score_weight,
            w.expenditure_score_weight,
            w.departure_score_weight,
            co.total_hotels as country_total_hotels
        FROM area ar
        JOIN area_fts fts ON ar.id = fts.rowid
        LEFT JOIN city ci ON ar.city_id = ci.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'area'
        WHERE fts.name MATCH ?

        UNION
        
        -- city_by_country_fts
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.agoda_score_normalized,
            s.google_score_normalized,
            s.expenditure_score_normalized,
            s.departure_score_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            w.agoda_score_weight,
            w.google_score_weight,
            w.expenditure_score_weight,
            w.departure_score_weight,
            co.total_hotels as country_total_hotels
        FROM city ci
        LEFT JOIN country co ON ci.country_id = co.id
        JOIN country_fts country_fts ON co.id = country_fts.rowid
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'city'
        WHERE country_fts.name MATCH ?
        
        UNION
        
        -- area_by_city_fts
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            (SELECT COUNT(*) FROM hotel WHERE area_id = ar.id) as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.agoda_score_normalized,
            s.google_score_normalized,
            s.expenditure_score_normalized,
            s.departure_score_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
            w.agoda_score_weight,
            w.google_score_weight,
            w.expenditure_score_weight,
            w.departure_score_weight,
            co.total_hotels as country_total_hotels
        FROM area ar
        LEFT JOIN city ci ON ar.city_id = ci.id
        JOIN city_fts city_fts ON ci.id = city_fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'area'
        WHERE city_fts.name MATCH ?
        
        UNION
        
        -- direct_hotel
        SELECT DISTINCT
            'hotel' as type,
            h.name, 
            co.name as country_name,
            ci.name as city_name,
            CASE WHEN ar.name IS NOT NULL THEN ar.name ELSE NULL END as area_name,
            1 as hotel_count,
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.agoda_score_normalized, 0) as agoda_score_normalized,
            COALESCE(s.google_score_normalized, 0) as google_score_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            COALESCE(s.total_score, 0) as total_score,
            COALESCE(w.hotel_count_weight, 0) as hotel_count_weight,
            COALESCE(w.country_hotel_count_weight, 0) as country_hotel_count_weight,
            COALESCE(w.agoda_score_weight, 0) as agoda_score_weight,
            COALESCE(w.google_score_weight, 0) as google_score_weight,
            COALESCE(w.expenditure_score_weight, 0) as expenditure_score_weight,
            COALESCE(w.departure_score_weight, 0) as departure_score_weight,
            co.total_hotels as country_total_hotels
        FROM hotel h
        JOIN hotel_fts fts ON h.id = fts.rowid
        LEFT JOIN city ci ON h.city_id = ci.id
        LEFT JOIN area ar ON h.area_id = ar.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.id = (h.id + 20000) AND d.type = 'hotel'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'hotel'
        WHERE fts.name MATCH ?
        
        ORDER BY total_score DESC, hotel_count DESC, type
        LIMIT 20
    ''', (match_pattern, match_pattern, match_pattern, match_pattern, match_pattern))

    results = cursor.fetchall()
    conn.close()
    return results