def get_max_values(cursor):
    """Get max values for normalization"""
    # Get max city hotel count
    cursor.execute('SELECT MAX(total_hotels) FROM city')
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1
    
    # Get max hotel scores
    cursor.execute('SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores')
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100
    
    return max_city_hotels, max_agoda_score, max_google_score


def normalize_hotel_count(hotel_count, max_city_hotels):
    """Normalize hotel count to 0-100 scale"""
    return int((hotel_count / max_city_hotels) * 100)


def normalize_country_hotel_count(hotel_count, max_country_hotels):
    """Normalize country hotel count to 0-100 scale"""
    return (
        int((hotel_count / max_country_hotels) * 100)
        if max_country_hotels > 200
        else 0
    )


def get_outbound_scores(cursor, country_id):
    """Get normalized outbound scores for a country"""
    cursor.execute(
        'SELECT expenditure_score, departure_score FROM country_outbound WHERE country_id = ?',
        (country_id,)
    )
    outbound_result = cursor.fetchone()
    if outbound_result:
        return int(outbound_result[0]), int(outbound_result[1])
    return 0, 0


def calculate_weighted_score(factors, weights):
    """Calculate weighted average score"""
    if not factors or not weights or len(factors) != len(weights):
        return 0
        
    weighted_sum = sum(factor * weight for factor, weight in zip(factors, weights))
    factor_sum = sum(weights)
    
    return weighted_sum / factor_sum if factor_sum > 0 else 0


def get_weights(cursor, dest_type):
    """Get weights for destination type"""
    if dest_type == 'hotel':
        cursor.execute('SELECT hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight FROM factor_weights WHERE type = ?', (dest_type,))
        weights_result = cursor.fetchone()
        return list(weights_result) if weights_result else [0, 0, 0, 0]
    else:
        cursor.execute('SELECT hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight FROM factor_weights WHERE type = ?', (dest_type,))
        weights_result = cursor.fetchone()
        return list(weights_result) if weights_result else [0, 0, 0, 0]


def get_city_normalization_scores(cursor, city_id, country_id):
    """Get normalization scores for a city"""
    max_city_hotels, _, _ = get_max_values(cursor)
    
    # Get city hotel count
    cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
    result = cursor.fetchone()
    city_hotel_count = result[0] if result else 0
    
    # Calculate global hotel normalization
    global_hotel_normalized = normalize_hotel_count(city_hotel_count, max_city_hotels)
    
    # Get max country hotel count
    cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
    result = cursor.fetchone()
    max_country_hotels = result[0] if result and result[0] else 1
    
    # Calculate country hotel normalization
    country_hotel_normalized = normalize_country_hotel_count(city_hotel_count, max_country_hotels)
    
    return global_hotel_normalized, country_hotel_normalized


def calculate_location_score(cursor, dest_type, dest_id, city_id, area_id, country_id):
    """Calculate score for city or area destination"""
    max_city_hotels, _, _ = get_max_values(cursor)
    
    # Get hotel count based on destination type
    if dest_type == 'city':
        cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
        result = cursor.fetchone()
        hotel_count = result[0] if result else 0
    else:  # area
        cursor.execute('SELECT COUNT(*) FROM hotel WHERE area_id = ?', (area_id,))
        result = cursor.fetchone()
        hotel_count = result[0] if result else 0
    
    # Get max country hotel count
    cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
    result = cursor.fetchone()
    max_country_hotels = result[0] if result and result[0] else 1
    
    # Normalize scores
    hotel_count_normalized = normalize_hotel_count(hotel_count, max_city_hotels)
    country_hotel_count_normalized = normalize_country_hotel_count(hotel_count, max_country_hotels)
    expenditure_score_normalized, departure_score_normalized = get_outbound_scores(cursor, country_id)
    
    # Get weights
    weights = get_weights(cursor, dest_type)
    
    # Calculate total score
    factors = [hotel_count_normalized, country_hotel_count_normalized, expenditure_score_normalized, departure_score_normalized]
    total_score = calculate_weighted_score(factors, weights)
    
    return (
        hotel_count_normalized,
        country_hotel_count_normalized,
        0,  # agoda_score_normalized (not applicable for cities/areas)
        0,  # google_score_normalized (not applicable for cities/areas)
        expenditure_score_normalized,
        departure_score_normalized,
        total_score
    )


def calculate_hotel_score(cursor, hotel_id, city_id, country_id):
    """Calculate score for hotel destination using city normalization + hotel review scores"""
    _, max_agoda, max_google = get_max_values(cursor)
    
    # Get hotel's own review scores
    cursor.execute('SELECT agoda_score, google_score FROM hotel_scores WHERE hotel_id = ?', (hotel_id,))
    result = cursor.fetchone()
    agoda_score, google_score = result if result else (0, 0)
    
    # Normalize hotel review scores
    agoda_score_normalized = int((agoda_score / max_agoda) * 100) if agoda_score else 0
    google_score_normalized = int((google_score / max_google) * 100) if google_score else 0
    
    # Get city's normalization scores (inherit from parent city)
    city_global_normalized, city_country_normalized = get_city_normalization_scores(cursor, city_id, country_id)
    
    # Get weights (4 factors for hotels: city normalization + hotel review scores)
    weights = get_weights(cursor, 'hotel')
    
    # Calculate total score with four factors
    factors = [city_global_normalized, city_country_normalized, agoda_score_normalized, google_score_normalized]
    total_score = calculate_weighted_score(factors, weights)
    
    return (
        city_global_normalized,  # Inherited from city
        city_country_normalized,  # Inherited from city
        agoda_score_normalized,
        google_score_normalized,
        0,  # expenditure_score_normalized (not used for hotels)
        0,  # departure_score_normalized (not used for hotels)
        total_score
    )