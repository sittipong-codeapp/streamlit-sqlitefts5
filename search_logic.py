from database import get_connection


# Function to update factor weights and recalculate total score
def update_weights(dest_type, hotel_count_weight, country_hotel_count_weight):
    conn = get_connection()
    cursor = conn.cursor()

    # Validate weights (should be between 0 and 1)
    if not (0 <= hotel_count_weight <= 1 and 0 <= country_hotel_count_weight <= 1):
        conn.close()
        return False

    # Validate destination type
    if dest_type not in ["city", "area"]:
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
    cursor.execute("SELECT MAX(total_hotels) FROM city")
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1

    # For each destination of the specified type, recalculate the score
    cursor.execute("SELECT id FROM destination WHERE type = ?", (dest_type,))
    dest_ids = [row[0] for row in cursor.fetchall()]

    for dest_id in dest_ids:
        # Get country
        cursor.execute('''
            SELECT d.country_id 
            FROM destination d 
            WHERE d.id = ?
        ''',(dest_id,))
        result = cursor.fetchone()
        country_id = result[0] if result else None

        if not country_id:
            continue  # Skip if no country_id

        # Get hotel count from appropriate location table and normalize
        if dest_type == "city":
            cursor.execute('''
                SELECT ci.total_hotels 
                FROM destination d 
                JOIN city ci ON d.city_id = ci.id 
                WHERE d.id = ?
            ''',(dest_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''',(country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1
        else:  # area
            cursor.execute('''
                SELECT ar.total_hotels 
                FROM destination d 
                JOIN area ar ON d.area_id = ar.id 
                WHERE d.id = ?
            ''',(dest_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            # Get max hotel count within the same country
            cursor.execute('''
                SELECT MAX(ci.total_hotels) 
                FROM city ci 
                WHERE ci.country_id = ?
            ''',(country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1

        # Normalize hotel counts - global and country level
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = (
            int((hotel_count / max_country_city_hotels) * 100)
            if max_country_city_hotels > 200
            else 0
        )

        # Calculate weighted total score with two factors (no rating)
        weighted_sum = (hotel_count_normalized * hotel_count_weight) + (
            country_hotel_count_normalized * country_hotel_count_weight
        )
        cursor.execute('''
            SELECT max(hotel_count_weight) + max(country_hotel_count_weight) as max_weight_sum
            FROM factor_weights
        ''')
        factor_sum = cursor.fetchone()[0]

        # Boost score for Thailand
        boost_up = 3 * factor_sum if country_id == 106 else 1

        total_score = weighted_sum * boost_up / factor_sum if factor_sum > 0 else 0

        # Update the score
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''',(hotel_count_normalized, country_hotel_count_normalized, total_score, dest_id))

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
        
        -- direct_hotel (NEW)
        SELECT DISTINCT
            'hotel' as type,
            h.name, 
            co.name as country_name,
            ci.name as city_name,
            CASE WHEN ar.name IS NOT NULL THEN ar.name ELSE NULL END as area_name,
            1 as hotel_count,
            0 as hotel_count_normalized,
            0 as country_hotel_count_normalized,
            0 as total_score,
            0 as hotel_count_weight,
            0 as country_hotel_count_weight,
            co.total_hotels as country_total_hotels
        FROM hotel h
        JOIN hotel_fts fts ON h.id = fts.rowid
        LEFT JOIN city ci ON h.city_id = ci.id
        LEFT JOIN area ar ON h.area_id = ar.id
        LEFT JOIN country co ON ci.country_id = co.id
        WHERE fts.name MATCH ?
        
        
        ORDER BY total_score DESC, hotel_count DESC, type
        LIMIT 20
    ''', (match_pattern, match_pattern, match_pattern, match_pattern, match_pattern))

    # Remove the match_type column from results before returning
    results = cursor.fetchall()
    conn.close()
    return results
