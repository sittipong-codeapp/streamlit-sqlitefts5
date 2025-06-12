from database import get_connection


def search_destinations(query):
    """
    Main search with hierarchical priority logic:
    1. Search cities and areas first
    2. Only search hotels if slots remain unfilled
    3. Always attempt to return up to 20 results total
    """
    # Phase 1: Search cities and areas
    location_results = search_locations_only(query)
    
    # Phase 2: Decision point
    if len(location_results) >= 20:
        # Enough locations found, skip hotels
        return location_results
    
    # Phase 3: Search hotels to fill remaining slots
    slots_needed = 20 - len(location_results)
    hotel_results = search_hotels_only(query, limit=slots_needed)
    
    # Phase 4: Combine results
    combined_results = location_results + hotel_results
    
    return combined_results


def search_locations_only(query):
    """
    Search cities and areas only (no hotels).
    Returns properly structured normalized data with 4 factors.
    UPDATED: Areas now include parent city hotel count for classification.
    """
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"

    # Execute queries for cities and areas only (no hotel queries)
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
            co.total_hotels as country_total_hotels,
            ci.total_hotels as parent_city_hotel_count
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
            co.total_hotels as country_total_hotels,
            ci.total_hotels as parent_city_hotel_count
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
            co.total_hotels as country_total_hotels,
            ci.total_hotels as parent_city_hotel_count
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
            co.total_hotels as country_total_hotels,
            ci.total_hotels as parent_city_hotel_count
        FROM area ar
        LEFT JOIN city ci ON ar.city_id = ci.id
        JOIN city_fts city_fts ON ci.id = city_fts.rowid
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.area_id = ar.id AND d.type = 'area'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE city_fts.name MATCH ?
    ''', (match_pattern, match_pattern, match_pattern, match_pattern))

    location_results = cursor.fetchall()
    conn.close()
    
    # Process results into clean dictionary structures
    processed_results = []
    
    # Define column mapping for location results (cities/areas - 4 factors)
    # UPDATED: Added parent_city_hotel_count column
    location_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels', 'parent_city_hotel_count'
    ]
    
    # Process location results (cities/areas - 4 factors, no agoda/google keys)
    for row in location_results:
        result = dict(zip(location_columns, row))
        processed_results.append(result)
    
    return processed_results


def search_hotels_only(query, limit=20):
    """
    Search hotels only with limit parameter.
    Returns properly structured normalized data with 6 factors.
    UPDATED: Hotels now include parent city hotel count for areas.
    """
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"

    # Execute hotel query only with LIMIT
    # UPDATED: Added parent city hotel count for hotels in areas
    cursor.execute('''
        -- direct_hotel: Get hotels matching query with limit
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
            co.total_hotels as country_total_hotels,
            ci.total_hotels as parent_city_hotel_count
        FROM hotel h
        JOIN hotel_fts fts ON h.id = fts.rowid
        LEFT JOIN city ci ON h.city_id = ci.id
        LEFT JOIN area ar ON h.area_id = ar.id
        LEFT JOIN country co ON ci.country_id = co.id
        LEFT JOIN destination d ON d.id = (h.id + 20000) AND d.type = 'hotel'
        LEFT JOIN destination_score s ON d.id = s.destination_id
        WHERE fts.name MATCH ?
        LIMIT ?
    ''', (match_pattern, limit))

    hotel_results = cursor.fetchall()
    conn.close()
    
    # Process results into clean dictionary structures
    processed_results = []
    
    # Define column mapping for hotel results (hotels - 6 factors)
    # UPDATED: Added parent_city_hotel_count column
    hotel_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'agoda_score_normalized', 'google_score_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels', 'parent_city_hotel_count'
    ]
    
    # Process hotel results (hotels - 6 factors including agoda/google)
    for row in hotel_results:
        result = dict(zip(hotel_columns, row))
        processed_results.append(result)
    
    return processed_results