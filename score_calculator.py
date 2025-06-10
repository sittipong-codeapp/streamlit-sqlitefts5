# score_calculator.py - Simplified utility functions for normalization and scoring
# Most functionality moved to scoring.py for in-memory calculations

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


def validate_weights(weights_dict):
    """
    Validate that all weights are between 0 and 1.
    Returns True if valid, False otherwise.
    """
    if not weights_dict:
        return False
    
    for weight_name, weight_value in weights_dict.items():
        try:
            weight_float = float(weight_value)
            if not (0 <= weight_float <= 1):
                return False
        except (ValueError, TypeError):
            return False
    
    return True


def get_weight_sum(weights_list):
    """Calculate sum of weights for validation"""
    try:
        return sum(float(w) for w in weights_list)
    except (ValueError, TypeError):
        return 0


# Legacy functions kept for potential compatibility (but simplified)
def calculate_weighted_score(factors, weights):
    """
    Legacy function - now just calls the same function from scoring.py
    Kept for backward compatibility if needed elsewhere.
    """
    from scoring import calculate_weighted_score as new_calculate_weighted_score
    return new_calculate_weighted_score(factors, weights)


# The following functions are REMOVED as they're no longer needed:
# - get_max_values(cursor) -> replaced by get_global_max_values()
# - normalize_hotel_count() -> replaced by normalize_value()
# - normalize_country_hotel_count() -> replaced by calculate_country_normalization()
# - get_outbound_scores() -> this logic moved to scoring.py
# - get_weights() -> this logic moved to scoring.py  
# - get_city_normalization_scores() -> this logic moved to scoring.py
# - calculate_location_score() -> this logic moved to scoring.py
# - calculate_hotel_score() -> this logic moved to scoring.py