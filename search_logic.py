from database import get_connection


# Function to update factor weights and recalculate total score
def update_weights(dest_type, hotel_count_weight=0, country_hotel_count_weight=0, agoda_score_weight=0, google_score_weight=0):
    conn = get_connection()
    cursor = conn.cursor()

    # Validate weights (should be between 0 and 1)
    if not all(0 <= w <= 1 for w in [hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight]):
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
                google_score_weight = ?
            WHERE type = ?
        ''', (agoda_score_weight, google_score_weight, dest_type))
    else:
        cursor.execute('''
            UPDATE factor_weights
            SET hotel_count_weight = ?,
                country_hotel_count_weight = ?
            WHERE type = ?
        ''', (hotel_count_weight, country_hotel_count_weight, dest_type))

    # Recalculate scores based on destination type
    if dest_type == "hotel":
        _recalculate_hotel_scores(cursor, agoda_score_weight, google_score_weight)
    else:
        _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight)

    conn.commit()
    conn.close()
    return True


def _recalculate_hotel_scores(cursor, agoda_score_weight, google_score_weight):
    """Recalculate scores for hotels based on agoda and google scores"""
    
    # Get max scores for normalization
    cursor.execute("SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores")
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100

    # Get all hotels with scores
    cursor.execute('''
        SELECT h.id, hs.agoda_score, hs.google_score, ci.country_id
        FROM hotel h
        LEFT JOIN hotel_scores hs ON h.id = hs.hotel_id
        LEFT JOIN city ci ON h.city_id = ci.id
    ''')
    hotels = cursor.fetchall()

    for hotel_id, agoda_score, google_score, country_id in hotels:
        # Default to 0 if no scores found
        agoda_score = agoda_score or 0
        google_score = google_score or 0
        
        # Normalize scores (0-100 scale)
        agoda_normalized = int((agoda_score / max_agoda_score) * 100)
        google_normalized = int((google_score / max_google_score) * 100)
        
        # Calculate weighted total score
        weighted_sum = (agoda_normalized * agoda_score_weight) + (google_normalized * google_score_weight)
        factor_sum = agoda_score_weight + google_score_weight
        
        # Boost score for Thailand
        boost_up = 3 * factor_sum if country_id == 106 else 1
        
        total_score = weighted_sum * boost_up / factor_sum if factor_sum > 0 else 0

        # Update or insert score for hotel
        cursor.execute('''
            INSERT OR REPLACE INTO destination_score 
            (destination_id, hotel_count_normalized, country_hotel_count_normalized, total_score)
            VALUES (?, ?, ?, ?)
        ''', (hotel_id, agoda_normalized, google_normalized, total_score))


def _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight):
    """Recalculate scores for cities and areas (existing logic)"""
    
    # Get max city hotel count for normalization
    cursor.execute("SELECT MAX(total_hotels) FROM city")
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1

    # Get all destinations of the specified type
    cursor.execute("SELECT id FROM destination WHERE type = ?", (dest_type,))
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
            continue

        # Get hotel count from appropriate location table and normalize
        if dest_type == "city":
            cursor.execute('''
                SELECT ci.total_hotels 
                FROM destination d 
                JOIN city ci ON d.city_id = ci.id 
                WHERE d.id = ?
            ''', (dest_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

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

            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1

        # Normalize hotel counts
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = (
            int((hotel_count / max_country_city_hotels) * 100)
            if max_country_city_hotels > 200
            else 0
        )

        # Calculate weighted total score
        weighted_sum = (hotel_count_normalized * hotel_count_weight) + (
            country_hotel_count_normalized * country_hotel_count_weight
        )
        factor_sum = hotel_count_weight + country_hotel_count_weight

        # Boost score for Thailand
        boost_up = 3 * factor_sum if country_id == 106 else 1

        total_score = weighted_sum * boost_up / factor_sum if factor_sum > 0 else 0

        # Update the score
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''', (hotel_count_normalized, country_hotel_count_normalized, total_score, dest_id))


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
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
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
            ar.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
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
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
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
            ar.total_hotels as hotel_count,
            s.hotel_count_normalized,
            s.country_hotel_count_normalized,
            s.total_score,
            w.hotel_count_weight,
            w.country_hotel_count_weight,
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
        
        -- direct_hotel (UPDATED to use proper scoring)
        SELECT DISTINCT
            'hotel' as type,
            h.name, 
            co.name as country_name,
            ci.name as city_name,
            CASE WHEN ar.name IS NOT NULL THEN ar.name ELSE NULL END as area_name,
            1 as hotel_count,
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.total_score, 0) as total_score,
            COALESCE(w.agoda_score_weight, 0) as hotel_count_weight,
            COALESCE(w.google_score_weight, 0) as country_hotel_count_weight,
            co.total_hotels as country_total_hotels
        FROM hotel h
        JOIN hotel_fts fts ON h.id = fts.rowid
        LEFT JOIN city ci ON h.city_id = ci.id
        LEFT JOIN area ar ON h.area_id = ar.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination_score s ON h.id = s.destination_id
        LEFT JOIN factor_weights w ON w.type = 'hotel'
        WHERE fts.name MATCH ?
        
        
        ORDER BY total_score DESC, hotel_count DESC, type
        LIMIT 20
    ''', (match_pattern, match_pattern, match_pattern, match_pattern, match_pattern))

    # Remove the match_type column from results before returning
    results = cursor.fetchall()
    conn.close()
    return results