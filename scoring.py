from database import get_connection


def calculate_scores_in_memory(fts_results, factor_weights, category_weights):
    """
    Calculate final scores for search results in memory using current factor weights and category weights.
    Now includes dynamic small city classification based on threshold.
    No database updates - just scoring and ranking.
    """
    if not fts_results:
        return []
    
    # Load small city threshold
    small_city_threshold = load_small_city_threshold()
    
    scored_results = []
    
    # Calculate total category weight for normalization
    total_category_weight = sum(category_weights.values())
    
    for result in fts_results:
        dest_type = result['type']
        
        # Dynamic small city classification - convert city to small_city if below threshold
        if dest_type == 'city' and result['hotel_count'] <= small_city_threshold:
            dest_type = 'small_city'
        
        if dest_type == 'hotel':
            # Hotels use 6 factors
            factors = [
                result['hotel_count_normalized'],
                result['country_hotel_count_normalized'],
                result['agoda_score_normalized'],
                result['google_score_normalized'],
                result['expenditure_score_normalized'],
                result['departure_score_normalized']
            ]
            
            hotel_weights = factor_weights['hotel']
            factor_weight_list = [
                hotel_weights['hotel_count_weight'],
                hotel_weights['country_hotel_count_weight'],
                hotel_weights['agoda_score_weight'],
                hotel_weights['google_score_weight'],
                hotel_weights['expenditure_score_weight'],
                hotel_weights['departure_score_weight']
            ]
            
        else:
            # Cities, small cities and areas use 4 factors (agoda and google are 0)
            factors = [
                result['hotel_count_normalized'],
                result['country_hotel_count_normalized'],
                result['expenditure_score_normalized'],
                result['departure_score_normalized']
            ]
            
            location_weights = factor_weights[dest_type]  # 'city', 'small_city', or 'area'
            factor_weight_list = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
        
        # Calculate base weighted score (factor level)
        base_score = calculate_weighted_score(factors, factor_weight_list)
        
        # Apply category weight (destination type level)
        category_weight = category_weights.get(dest_type, 1.0)
        category_multiplier = category_weight / total_category_weight if total_category_weight > 0 else 0
        final_score = base_score * category_multiplier
        
        # Create result tuple in the format expected by UI
        scored_result = (
            dest_type,  # This will now be 'small_city' for small cities
            result['name'],
            result['country_name'],
            result['city_name'],
            result['area_name'],
            result['hotel_count'],
            result['hotel_count_normalized'],
            result['country_hotel_count_normalized'],
            result['agoda_score_normalized'],
            result['google_score_normalized'],
            result['expenditure_score_normalized'],
            result['departure_score_normalized'],
            final_score,  # This is the final score (base_score × category_multiplier)
            factor_weight_list[0] if len(factor_weight_list) > 0 else 0,  # hotel_count_weight
            factor_weight_list[1] if len(factor_weight_list) > 1 else 0,  # country_hotel_count_weight
            factor_weight_list[2] if len(factor_weight_list) > 2 else 0,  # agoda_score_weight (0 for cities/areas)
            factor_weight_list[3] if len(factor_weight_list) > 3 else 0,  # google_score_weight (0 for cities/areas)
            factor_weight_list[4] if len(factor_weight_list) > 4 else factor_weight_list[2] if dest_type != 'hotel' else factor_weight_list[4],  # expenditure_score_weight
            factor_weight_list[5] if len(factor_weight_list) > 5 else factor_weight_list[3] if dest_type != 'hotel' else factor_weight_list[5],  # departure_score_weight
            result['country_total_hotels'],
            base_score,  # Add base score for debugging/display
            category_weight,  # Add category weight for debugging/display
            category_multiplier  # Add category multiplier for debugging/display
        )
        
        scored_results.append(scored_result)
    
    # Sort by final score (descending) and limit to top 20
    scored_results.sort(key=lambda x: x[12], reverse=True)  # x[12] is final_score
    return scored_results[:20]


def calculate_weighted_score(factors, weights):
    """Calculate weighted average score from factors and weights"""
    if not factors or not weights or len(factors) != len(weights):
        return 0
    
    # Calculate weighted sum
    weighted_sum = sum(factor * weight for factor, weight in zip(factors, weights))
    
    # Calculate sum of weights
    weight_sum = sum(weights)
    
    # Return weighted average (avoid division by zero)
    return weighted_sum / weight_sum if weight_sum > 0 else 0


def load_weights_from_database():
    """Load current factor weights from database into memory structure"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type, hotel_count_weight, country_hotel_count_weight, 
               agoda_score_weight, google_score_weight, 
               expenditure_score_weight, departure_score_weight 
        FROM factor_weights
    ''')
    
    weights_data = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary structure
    weights = {}
    for row in weights_data:
        dest_type = row[0]
        weights[dest_type] = {
            'hotel_count_weight': row[1],
            'country_hotel_count_weight': row[2],
            'agoda_score_weight': row[3],
            'google_score_weight': row[4],
            'expenditure_score_weight': row[5],
            'departure_score_weight': row[6]
        }
    
    # Set defaults if missing
    if 'city' not in weights:
        weights['city'] = {
            'hotel_count_weight': 1.0,
            'country_hotel_count_weight': 0.625,
            'agoda_score_weight': 0,
            'google_score_weight': 0,
            'expenditure_score_weight': 0.025,
            'departure_score_weight': 0.025
        }
    
    if 'area' not in weights:
        weights['area'] = {
            'hotel_count_weight': 1.0,
            'country_hotel_count_weight': 0.625,
            'agoda_score_weight': 0,
            'google_score_weight': 0,
            'expenditure_score_weight': 0.025,
            'departure_score_weight': 0.025
        }
    
    if 'hotel' not in weights:
        weights['hotel'] = {
            'hotel_count_weight': 0.001,
            'country_hotel_count_weight': 0.001,
            'agoda_score_weight': 0.001,
            'google_score_weight': 0.001,
            'expenditure_score_weight': 0.001,
            'departure_score_weight': 0.001
        }
    
    if 'small_city' not in weights:
        weights['small_city'] = {
            'hotel_count_weight': 1.0,
            'country_hotel_count_weight': 0.625,
            'agoda_score_weight': 0,
            'google_score_weight': 0,
            'expenditure_score_weight': 0.025,
            'departure_score_weight': 0.025
        }
    
    return weights


def load_category_weights_from_database():
    """Load current category weights from database into memory structure"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type, weight FROM category_weights
    ''')
    
    weights_data = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary structure
    category_weights = {}
    for row in weights_data:
        dest_type = row[0]
        weight = row[1]
        category_weights[dest_type] = weight
    
    # Set defaults if missing
    if 'city' not in category_weights:
        category_weights['city'] = 10.0
    
    if 'area' not in category_weights:
        category_weights['area'] = 1.0
    
    if 'hotel' not in category_weights:
        category_weights['hotel'] = 0.1
    
    if 'small_city' not in category_weights:
        category_weights['small_city'] = 5.0
    
    return category_weights


def load_small_city_threshold():
    """Load small city threshold from database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT threshold FROM small_city_config WHERE id = 1')
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 50  # Default to 50 if not found


def save_small_city_threshold(threshold):
    """Save small city threshold to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO small_city_config (id, threshold) VALUES (1, ?)
    ''', (threshold,))
    
    conn.commit()
    conn.close()


def save_weights_to_database(factor_weights):
    """Save current in-memory factor weights back to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for dest_type, weight_dict in factor_weights.items():
        cursor.execute('''
            INSERT OR REPLACE INTO factor_weights 
            (type, hotel_count_weight, country_hotel_count_weight, 
             agoda_score_weight, google_score_weight, 
             expenditure_score_weight, departure_score_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            dest_type,
            weight_dict['hotel_count_weight'],
            weight_dict['country_hotel_count_weight'],
            weight_dict['agoda_score_weight'],
            weight_dict['google_score_weight'],
            weight_dict['expenditure_score_weight'],
            weight_dict['departure_score_weight']
        ))
    
    conn.commit()
    conn.close()


def save_category_weights_to_database(category_weights):
    """Save current in-memory category weights back to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for dest_type, weight in category_weights.items():
        cursor.execute('''
            INSERT OR REPLACE INTO category_weights (type, weight) VALUES (?, ?)
        ''', (dest_type, weight))
    
    conn.commit()
    conn.close()


def get_country_maxes_from_results(fts_results):
    """
    Calculate country max hotel counts for countries present in search results.
    This is much faster than pre-calculating for all countries.
    """
    if not fts_results:
        return {}
    
    # Get unique country IDs from results
    country_ids = set()
    for result in fts_results:
        if result['country_id']:
            country_ids.add(result['country_id'])
    
    if not country_ids:
        return {}
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get max hotel count for each country in results
    country_maxes = {}
    for country_id in country_ids:
        cursor.execute('''
            SELECT MAX(total_hotels) 
            FROM city 
            WHERE country_id = ?
        ''', (country_id,))
        
        result = cursor.fetchone()
        max_hotels = result[0] if result and result[0] else 1
        country_maxes[country_id] = max_hotels
    
    conn.close()
    return country_maxes


# Backward compatibility function - updates the signature to include category weights
def calculate_scores_in_memory_legacy(fts_results, weights):
    """
    Legacy function for backward compatibility.
    Loads category weights from database and calls the new function.
    """
    category_weights = load_category_weights_from_database()
    return calculate_scores_in_memory(fts_results, weights, category_weights)