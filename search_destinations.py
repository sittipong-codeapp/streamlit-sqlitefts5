from database import get_connection
from scoring import (
    load_weights_from_database, 
    load_small_city_threshold,
    calculate_location_score_on_demand
)
from score_calculator import is_small_country, get_country_classification_batch


def search_destinations(query):
    """
    Enhanced search with proper scoring and sorting at each phase:
    1. Search and score locations, sort, take top 20 if >= 20
    2. If < 20, search ALL hotels, score them, sort, take needed slots
    3. Final re-sort of combined results to allow hotels to outrank cities
    """
    # Phase 1: Get and score locations
    location_results = search_and_score_locations(query)
    
    if len(location_results) >= 20:
        return location_results[:20]  # Top 20 locations only
    
    # Phase 2: Get ALL hotels, calculate scores, sort, take needed
    slots_needed = 20 - len(location_results)
    hotel_results = search_and_score_hotels(query, slots_needed)
    
    # Phase 3: Combine and final sort to allow hotels to outrank cities
    combined = location_results + hotel_results
    combined.sort(key=lambda x: x['final_score'], reverse=True)
    
    return combined


def search_and_score_locations(query):
    """
    Search locations, calculate scores, and sort by score.
    Returns locations with calculated final_score.
    """
    # Get raw location data using existing SQL logic
    raw_results = get_raw_location_data(query)
    
    if not raw_results:
        return []
    
    # Calculate scores for all locations
    scored_results = calculate_location_scores(raw_results)
    
    # Sort by score descending
    scored_results.sort(key=lambda x: x['final_score'], reverse=True)
    
    return scored_results


def search_and_score_hotels(query, slots_needed):
    """
    Search ALL matching hotels, calculate scores including parent city/area scores,
    sort by score, and return top N hotels where N = slots_needed.
    """
    # Get ALL matching hotels (no limit)
    raw_hotel_results = get_all_matching_hotels(query)
    
    if not raw_hotel_results:
        return []
    
    # Calculate scores for all hotels (including city/area scores)
    scored_hotels = calculate_hotel_scores_with_parents(raw_hotel_results)
    
    # Sort by score descending and take only what we need
    scored_hotels.sort(key=lambda x: x['final_score'], reverse=True)
    
    return scored_hotels[:slots_needed]


def get_raw_location_data(query):
    """
    Get raw location data using the same SQL queries as before.
    Returns list of dictionaries with location data and normalized scores.
    """
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"

    # Execute the same 4 UNION queries as before
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
    
    # Define column mapping for location results
    location_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels', 'parent_city_hotel_count'
    ]
    
    # Process location results
    for row in location_results:
        result = dict(zip(location_columns, row))
        processed_results.append(result)
    
    return processed_results


def get_all_matching_hotels(query):
    """
    Get ALL matching hotels (no limit) with all necessary data for scoring.
    Returns list of dictionaries with hotel data and normalized scores.
    """
    conn = get_connection()
    cursor = conn.cursor()
    match_pattern = f"{query}*"

    # Execute hotel query WITHOUT LIMIT to get ALL matching hotels
    cursor.execute('''
        -- Get ALL hotels matching query (no limit)
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
    ''', (match_pattern,))

    hotel_results = cursor.fetchall()
    conn.close()
    
    # Process results into clean dictionary structures
    processed_results = []
    
    # Define column mapping for hotel results
    hotel_columns = [
        'type', 'name', 'country_name', 'city_name', 'area_name', 'hotel_count',
        'city_id', 'country_id', 'area_id', 'hotel_id',
        'hotel_count_normalized', 'country_hotel_count_normalized',
        'agoda_score_normalized', 'google_score_normalized',
        'expenditure_score_normalized', 'departure_score_normalized',
        'country_total_hotels', 'parent_city_hotel_count'
    ]
    
    # Process hotel results
    for row in hotel_results:
        result = dict(zip(hotel_columns, row))
        processed_results.append(result)
    
    return processed_results


def calculate_location_scores(raw_results):
    """
    Calculate scores for location results (cities/areas).
    Returns list with final_score added to each result.
    """
    if not raw_results:
        return []
    
    weights = load_weights_from_database()
    threshold = load_small_city_threshold()
    
    # Get unique country IDs for batch classification
    country_ids = list(set(result['country_id'] for result in raw_results if result.get('country_id')))
    country_classifications = get_country_classification_batch(country_ids, threshold)
    
    scored_results = []
    for result in raw_results:
        score = calculate_single_location_score(result, weights, country_classifications)
        result['final_score'] = score
        scored_results.append(result)
    
    return scored_results


def calculate_hotel_scores_with_parents(raw_hotels):
    """
    Calculate scores for hotels including parent city/area scores.
    Returns list with final_score, city_score, and area_score added to each result.
    """
    if not raw_hotels:
        return []
    
    weights = load_weights_from_database()
    threshold = load_small_city_threshold()
    
    scored_hotels = []
    for hotel in raw_hotels:
        # Calculate parent scores on-demand
        city_score, area_score = calculate_location_score_on_demand(
            hotel['city_id'], 
            hotel['area_id'], 
            weights, 
            threshold
        )
        
        # Calculate final hotel score using 6 factors
        hotel_score = calculate_single_hotel_score(hotel, city_score, area_score, weights)
        
        # Add calculated values to result
        hotel['final_score'] = hotel_score
        hotel['city_score'] = city_score
        hotel['area_score'] = area_score
        
        scored_hotels.append(hotel)
    
    return scored_hotels


def calculate_single_location_score(result, weights, country_classifications):
    """
    Calculate score for a single location (city/area) using coefficient-based formula.
    Uses country-based classification from pre-calculated batch.
    """
    dest_type = result['type']
    country_id = result['country_id']
    
    # Dynamic classification using country-based logic
    if dest_type == 'city' and country_classifications.get(country_id, False):
        dest_type = 'small_city'
    elif dest_type == 'area' and country_classifications.get(country_id, False):
        dest_type = 'small_area'
    
    # Get appropriate weights for this destination type
    location_weights = weights[dest_type]
    
    # Extract 4 factors for locations
    factors = [
        result['hotel_count_normalized'],
        result['country_hotel_count_normalized'],
        result['expenditure_score_normalized'],
        result['departure_score_normalized']
    ]
    
    factor_weight_list = [
        location_weights['hotel_count_weight'],
        location_weights['country_hotel_count_weight'],
        location_weights['expenditure_score_weight'],
        location_weights['departure_score_weight']
    ]
    
    # Calculate final score: Σ(factor × coefficient) / 4
    weighted_sum = sum(factor * coeff for factor, coeff in zip(factors, factor_weight_list))
    final_score = weighted_sum / 4
    
    return final_score


def calculate_single_hotel_score(hotel, city_score, area_score, weights):
    """
    Calculate score for a single hotel using 6 factors including calculated city/area scores.
    """
    hotel_weights = weights['hotel']
    
    # Extract 6 factors for hotels
    factors = [
        city_score,  # Calculated city score
        area_score,  # Calculated area score  
        hotel['agoda_score_normalized'],
        hotel['google_score_normalized'],
        hotel['expenditure_score_normalized'],
        hotel['departure_score_normalized']
    ]
    
    factor_weight_list = [
        hotel_weights['city_score_weight'],
        hotel_weights['area_score_weight'],
        hotel_weights['agoda_score_weight'],
        hotel_weights['google_score_weight'],
        hotel_weights['expenditure_score_weight'],
        hotel_weights['departure_score_weight']
    ]
    
    # Calculate final score: Σ(factor × coefficient) / 6
    weighted_sum = sum(factor * coeff for factor, coeff in zip(factors, factor_weight_list))
    final_score = weighted_sum / 6
    
    return final_score


# Legacy functions kept for compatibility (now simplified)
def search_locations_only(query):
    """Legacy function - now just calls the new search_and_score_locations"""
    return search_and_score_locations(query)


def search_hotels_only(query, limit=20):
    """Legacy function - now calls the new search_and_score_hotels"""
    return search_and_score_hotels(query, limit)