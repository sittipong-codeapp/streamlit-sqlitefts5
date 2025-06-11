from database import get_connection


def search_destinations(query):
    """
    Clean FTS search that returns properly structured normalized data.
    Cities/Areas: 4 factors only (no agoda/google keys)
    Hotels: 6 factors (all factors included)
    """
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"

    # Execute separate queries for different destination types to get clean factor structures
    
    # === CITIES AND AREAS QUERIES (4 factors) ===
    cursor.execute('''
        -- direct_city: Get cities matching query
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            ci.id as city_id,
            co.id as country_id,
            NULL as area_id,
            NULL as hotel_id,
            -- Get pre-normalized scores from destination_score (4 factors only)
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            co.total_hotels as country_total_hotels
        FROM city ci
        JOIN city_fts fts ON ci.id = fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE fts.name MATCH ?
        
        UNION
        
        -- direct_area: Get areas matching query
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            (SELECT COUNT(*) FROM hotel WHERE area_id = ar.id) as hotel_count,
            ci.id as city_id,
            co.id as country_id,
            ar.id as area_id,
            NULL as hotel_id,
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            co.total_hotels as country_total_hotels
        FROM area ar
        JOIN area_fts fts ON ar.id = fts.rowid
        LEFT JOIN city ci ON ar.city_id = ci.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE fts.name MATCH ?

        UNION
        
        -- city_by_country: Get cities when searching by country name
        SELECT DISTINCT
            'city' as type,
            ci.name, 
            co.name as country_name,
            ci.name as city_name,
            NULL as area_name,
            ci.total_hotels as hotel_count,
            ci.id as city_id,
            co.id as country_id,
            NULL as area_id,
            NULL as hotel_id,
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            co.total_hotels as country_total_hotels
        FROM city ci
        LEFT JOIN country co ON ci.country_id = co.id
        JOIN country_fts country_fts ON co.id = country_fts.rowid
        LEFT JOIN destination d ON d.city_id = ci.id AND d.type = 'city'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE country_fts.name MATCH ?
        
        UNION
        
        -- area_by_city: Get areas when searching by city name
        SELECT DISTINCT
            'area' as type,
            ar.name, 
            co.name as country_name,
            ci.name as city_name,
            ar.name as area_name,
            (SELECT COUNT(*) FROM hotel WHERE area_id = ar.id) as hotel_count,
            ci.id as city_id,
            co.id as country_id,
            ar.id as area_id,
            NULL as hotel_id,
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            co.total_hotels as country_total_hotels
        FROM area ar
        LEFT JOIN city ci ON ar.city_id = ci.id
        JOIN city_fts city_fts ON ci.id = city_fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE city_fts.name MATCH ?
    ''', (match_pattern, match_pattern, match_pattern, match_pattern))

    location_results = cursor.fetchall()
    
    # === HOTELS QUERY (6 factors) ===
    cursor.execute('''
        -- direct_hotel: Get hotels matching query
        SELECT DISTINCT
            'hotel' as type,
            h.name, 
            co.name as country_name,
            ci.name as city_name,
            CASE WHEN ar.name IS NOT NULL THEN ar.name ELSE NULL END as area_name,
            1 as hotel_count,
            ci.id as city_id,
            co.id as country_id,
            ar.id as area_id,
            h.id as hotel_id,
            -- Get pre-normalized scores from destination_score (6 factors for hotels)
            COALESCE(s.hotel_count_normalized, 0) as hotel_count_normalized,
            COALESCE(s.country_hotel_count_normalized, 0) as country_hotel_count_normalized,
            COALESCE(s.agoda_score_normalized, 0) as agoda_score_normalized,
            COALESCE(s.google_score_normalized, 0) as google_score_normalized,
            COALESCE(s.expenditure_score_normalized, 0) as expenditure_score_normalized,
            COALESCE(s.departure_score_normalized, 0) as departure_score_normalized,
            co.total_hotels as country_total_hotels
        FROM hotel h
        JOIN hotel_fts fts ON h.id = fts.rowid
        LEFT JOIN city ci ON h.city_id = ci.id
        LEFT JOIN area ar ON h.area_id = ar.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.id = (h.id + 20000) AND d.type = 'hotel'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE fts.name MATCH ?
    ''', (match_pattern,))

    hotel_results = cursor.fetchall()
    conn.close()
    
    # Process results into clean dictionary structures
    processed_results = []
    
    # Define column mappings for different result types
    location_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels'
    ]
    
    hotel_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'agoda_score_normalized', 'google_score_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels'
    ]
    
    # Process location results (cities/areas - 4 factors)
    for row in location_results:
        result = dict(zip(location_columns, row))
        # No agoda/google keys for locations - they're simply not included
        processed_results.append(result)
    
    # Process hotel results (hotels - 6 factors)
    for row in hotel_results:
        result = dict(zip(hotel_columns, row))
        # Hotels have all 6 factors including agoda/google
        processed_results.append(result)
    
    return processed_results


def search_destinations_legacy(query):
    """
    Legacy function that adds agoda/google keys with 0 values for backward compatibility.
    Use this if other parts of the code expect all results to have agoda/google keys.
    """
    results = search_destinations(query)
    
    # Add missing agoda/google keys for location results
    for result in results:
        if result['type'] in ['city', 'area']:
            if 'agoda_score_normalized' not in result:
                result['agoda_score_normalized'] = 0
            if 'google_score_normalized' not in result:
                result['google_score_normalized'] = 0
    
    return results