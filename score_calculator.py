from database import get_connection


def get_global_max_values():
    """Get global max values for normalization - called once at startup"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get max city hotel count (global normalization)
    cursor.execute('SELECT MAX(total_hotels) FROM city')
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1
    
    # Get max hotel scores (global normalization)
    cursor.execute('SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores')
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100
    
    conn.close()
    
    return {
        'max_city_hotels': max_city_hotels,
        'max_agoda_score': max_agoda_score,
        'max_google_score': max_google_score
    }


def get_country_max_hotels(country_ids):
    """
    Get max hotel counts for specific countries.
    Used for dynamic country normalization in search results.
    """
    if not country_ids:
        return {}
    
    conn = get_connection()
    cursor = conn.cursor()
    
    country_maxes = {}
    
    # Convert to list if it's a set
    if isinstance(country_ids, set):
        country_ids = list(country_ids)
    
    # Create placeholders for SQL IN clause
    placeholders = ','.join('?' * len(country_ids))
    
    # Get max hotel count for each country in one query
    cursor.execute(f'''
        SELECT country_id, MAX(total_hotels) as max_hotels
        FROM city 
        WHERE country_id IN ({placeholders})
        GROUP BY country_id
    ''', country_ids)
    
    results = cursor.fetchall()
    
    for country_id, max_hotels in results:
        country_maxes[country_id] = max_hotels if max_hotels else 1
    
    # Fill in missing countries with default value 1
    for country_id in country_ids:
        if country_id not in country_maxes:
            country_maxes[country_id] = 1
    
    conn.close()
    return country_maxes


def normalize_value(value, max_value, scale=100):
    """Simple normalization utility function"""
    if not value or not max_value or max_value <= 0:
        return 0
    return int((value / max_value) * scale)


def calculate_country_normalization(hotel_count, max_country_hotels, threshold=200):
    """
    Calculate country-relative normalization.
    Returns 0 if max_country_hotels <= threshold, otherwise normalizes to 0-100.
    """
    if max_country_hotels <= threshold:
        return 0
    return normalize_value(hotel_count, max_country_hotels)


def validate_location_weights(weights_dict):
    """
    Validate that all 4 location weights are between 0 and 1.
    Returns True if valid, False otherwise.
    """
    if not weights_dict:
        return False
    
    expected_keys = {'hotel_count_weight', 'country_hotel_count_weight', 
                    'expenditure_score_weight', 'departure_score_weight'}
    
    if set(weights_dict.keys()) != expected_keys:
        return False
    
    for weight_name, weight_value in weights_dict.items():
        try:
            weight_float = float(weight_value)
            if not (0 <= weight_float <= 1):
                return False
        except (ValueError, TypeError):
            return False
    
    return True


def validate_hotel_weights(weights_dict):
    """
    Validate that all 6 hotel weights are between 0 and 1.
    Returns True if valid, False otherwise.
    """
    if not weights_dict:
        return False
    
    expected_keys = {'hotel_count_weight', 'country_hotel_count_weight',
                    'agoda_score_weight', 'google_score_weight',
                    'expenditure_score_weight', 'departure_score_weight'}
    
    if set(weights_dict.keys()) != expected_keys:
        return False
    
    for weight_name, weight_value in weights_dict.items():
        try:
            weight_float = float(weight_value)
            if not (0 <= weight_float <= 1):
                return False
        except (ValueError, TypeError):
            return False
    
    return True


def validate_weights_by_type(dest_type, weights_dict):
    """
    Validate weights based on destination type.
    Returns True if valid, False otherwise.
    """
    if dest_type == 'hotel':
        return validate_hotel_weights(weights_dict)
    elif dest_type in ['city', 'area', 'small_city']:
        return validate_location_weights(weights_dict)
    else:
        return False


def get_factor_count(dest_type):
    """
    Get the expected number of factors for a destination type.
    Returns 4 for locations, 6 for hotels.
    """
    if dest_type == 'hotel':
        return 6
    elif dest_type in ['city', 'area', 'small_city']:
        return 4
    else:
        return 0


def get_factor_names(dest_type):
    """
    Get the factor names for a destination type.
    Returns list of factor names in correct order.
    """
    if dest_type == 'hotel':
        return [
            'hotel_count_weight',
            'country_hotel_count_weight', 
            'agoda_score_weight',
            'google_score_weight',
            'expenditure_score_weight',
            'departure_score_weight'
        ]
    elif dest_type in ['city', 'area', 'small_city']:
        return [
            'hotel_count_weight',
            'country_hotel_count_weight',
            'expenditure_score_weight', 
            'departure_score_weight'
        ]
    else:
        return []


def get_weight_sum(weights_list):
    """Calculate sum of weights for validation"""
    try:
        return sum(float(w) for w in weights_list)
    except (ValueError, TypeError):
        return 0


def get_weight_sum_by_type(dest_type, weights_dict):
    """Calculate sum of weights for a specific destination type"""
    factor_names = get_factor_names(dest_type)
    if not factor_names:
        return 0
    
    try:
        return sum(float(weights_dict[factor_name]) for factor_name in factor_names)
    except (KeyError, ValueError, TypeError):
        return 0


def create_default_weights_by_type(dest_type):
    """Create default weights for a specific destination type"""
    from config import get_default_city_weights, get_default_small_city_weights, get_default_area_weights, get_default_hotel_weights
    
    if dest_type == 'hotel':
        return get_default_hotel_weights()
    elif dest_type == 'city':
        return get_default_city_weights()
    elif dest_type == 'small_city':
        return get_default_small_city_weights()
    elif dest_type == 'area':
        return get_default_area_weights()
    else:
        return {}


def extract_factor_values_from_result(result, dest_type):
    """
    Extract factor values from a search result based on destination type.
    Returns list of factor values in correct order.
    """
    if dest_type == 'hotel':
        # Hotels: 6 factors
        return [
            result.get('hotel_count_normalized', 0),
            result.get('country_hotel_count_normalized', 0),
            result.get('agoda_score_normalized', 0),
            result.get('google_score_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0)
        ]
    elif dest_type in ['city', 'area', 'small_city']:
        # Locations: 4 factors (no agoda/google)
        return [
            result.get('hotel_count_normalized', 0),
            result.get('country_hotel_count_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0)
        ]
    else:
        return []


def extract_weight_values_from_dict(weights_dict, dest_type):
    """
    Extract weight values from a weights dictionary based on destination type.
    Returns list of weight values in correct order.
    """
    factor_names = get_factor_names(dest_type)
    if not factor_names:
        return []
    
    try:
        return [weights_dict[factor_name] for factor_name in factor_names]
    except KeyError:
        return []


# Backward compatibility function
def calculate_weighted_score(factors, weights):
    """
    Legacy function - now just calls the same function from scoring.py
    Kept for backward compatibility if needed elsewhere.
    """
    from scoring import calculate_weighted_score as new_calculate_weighted_score
    return new_calculate_weighted_score(factors, weights)
