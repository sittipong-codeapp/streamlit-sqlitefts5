from database import get_connection


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