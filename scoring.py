from database import get_connection
from score_calculator import is_small_country


def calculate_location_score_on_demand(city_id, area_id, factor_weights, small_city_threshold):
    """
    Calculate city and area scores on-demand for hotel scoring.
    Returns tuple: (city_score, area_score)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get city data and calculate city score
    cursor.execute('''
        SELECT d.type, d.country_id, d.city_id, d.area_id,
               s.hotel_count_normalized, s.country_hotel_count_normalized,
               s.expenditure_score_normalized, s.departure_score_normalized,
               c.total_hotels as city_hotel_count
        FROM destination d
        LEFT JOIN destination_score s ON d.id = s.destination_id
        LEFT JOIN city c ON d.city_id = c.id
        WHERE d.city_id = ? AND d.type = 'city'
    ''', (city_id,))
    
    city_result = cursor.fetchone()
    city_score = 0
    
    if city_result:
        # Determine if this is a small city based on country classification
        country_id = city_result[1]
        dest_type = 'small_city' if is_small_country(country_id, small_city_threshold) else 'city'
        
        # Get appropriate weights
        location_weights = factor_weights[dest_type]
        
        # Calculate city score using 4 factors
        city_factors = [
            city_result[4] or 0,  # hotel_count_normalized
            city_result[5] or 0,  # country_hotel_count_normalized
            city_result[6] or 0,  # expenditure_score_normalized
            city_result[7] or 0   # departure_score_normalized
        ]
        
        city_weight_list = [
            location_weights['hotel_count_weight'],
            location_weights['country_hotel_count_weight'],
            location_weights['expenditure_score_weight'],
            location_weights['departure_score_weight']
        ]
        
        # Calculate city score: Σ(factor × coefficient) / 4
        weighted_sum = sum(factor * coeff for factor, coeff in zip(city_factors, city_weight_list))
        city_score = weighted_sum / 4
    
    # Get area data and calculate area score
    area_score = 0
    if area_id:
        cursor.execute('''
            SELECT d.type, d.country_id, d.city_id, d.area_id,
                   s.hotel_count_normalized, s.country_hotel_count_normalized,
                   s.expenditure_score_normalized, s.departure_score_normalized,
                   c.total_hotels as parent_city_hotel_count
            FROM destination d
            LEFT JOIN destination_score s ON d.id = s.destination_id
            LEFT JOIN city c ON d.city_id = c.id
            WHERE d.area_id = ? AND d.type = 'area'
        ''', (area_id,))
        
        area_result = cursor.fetchone()
        
        if area_result:
            # Determine if this is a small area based on country classification
            country_id = area_result[1]
            dest_type = 'small_area' if is_small_country(country_id, small_city_threshold) else 'area'
            
            # Get appropriate weights
            location_weights = factor_weights[dest_type]
            
            # Calculate area score using 4 factors
            area_factors = [
                area_result[4] or 0,  # hotel_count_normalized
                area_result[5] or 0,  # country_hotel_count_normalized
                area_result[6] or 0,  # expenditure_score_normalized
                area_result[7] or 0   # departure_score_normalized
            ]
            
            area_weight_list = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
            
            # Calculate area score: Σ(factor × coefficient) / 4
            weighted_sum = sum(factor * coeff for factor, coeff in zip(area_factors, area_weight_list))
            area_score = weighted_sum / 4
    
    conn.close()
    return city_score, area_score


def calculate_scores_in_memory(fts_results, factor_weights):
    """
    SIMPLIFIED: Calculate final scores for search results that come pre-scored.
    This function is now mainly for backward compatibility and UI formatting.
    The heavy lifting of scoring is done earlier in the search process.
    """
    if not fts_results:
        return []
    
    # Load small city threshold for any remaining classification needed
    small_city_threshold = load_small_city_threshold()
    
    scored_results = []
    
    for result in fts_results:
        dest_type = result['type']
        
        # Use pre-calculated final_score if available, otherwise calculate
        if 'final_score' in result:
            final_score = result['final_score']
        else:
            # Fallback: calculate score if not pre-calculated
            final_score = calculate_fallback_score(result, factor_weights, small_city_threshold)
        
        # Dynamic classification for UI display based on country
        country_id = result.get('country_id')
        if dest_type == 'city' and is_small_country(country_id, small_city_threshold):
            dest_type = 'small_city'
        elif dest_type == 'area' and is_small_country(country_id, small_city_threshold):
            dest_type = 'small_area'
        
        # Prepare weights for UI display (6-position array format)
        if dest_type == 'hotel':
            hotel_weights = factor_weights['hotel']
            padded_weights = [
                hotel_weights['city_score_weight'],
                hotel_weights['area_score_weight'],
                hotel_weights['agoda_score_weight'],
                hotel_weights['google_score_weight'],
                hotel_weights['expenditure_score_weight'],
                hotel_weights['departure_score_weight']
            ]
        else:
            # Location types - map 4 weights to 6-position array
            location_weights = factor_weights[dest_type]
            padded_weights = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                0,  # agoda_score_weight (not applicable)
                0,  # google_score_weight (not applicable)
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
        
        # Create result tuple in the format expected by UI
        scored_result = (
            dest_type,
            result['name'],
            result['country_name'],
            result['city_name'],
            result.get('area_name', ''),
            result.get('hotel_count', 0),
            result.get('hotel_count_normalized', 0),
            result.get('country_hotel_count_normalized', 0),
            result.get('agoda_score_normalized', 0),
            result.get('google_score_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0),
            final_score,  # Final score
            padded_weights[0],  # Weight 1
            padded_weights[1],  # Weight 2
            padded_weights[2],  # Weight 3 (agoda)
            padded_weights[3],  # Weight 4 (google)
            padded_weights[4],  # Weight 5 (expenditure)
            padded_weights[5],  # Weight 6 (departure)
            result.get('country_total_hotels', 0),
            final_score,  # Base score same as final score
            0,  # Category weight (legacy, set to 0)
            1   # Category multiplier (legacy, set to 1)
        )
        
        scored_results.append(scored_result)
    
    # Results should already be sorted, but ensure they are
    scored_results.sort(key=lambda x: x[12], reverse=True)  # x[12] is final_score
    return scored_results


def calculate_fallback_score(result, factor_weights, small_city_threshold):
    """
    Fallback score calculation for results that don't have pre-calculated scores.
    """
    dest_type = result['type']
    
    # Dynamic classification based on country
    country_id = result.get('country_id')
    if dest_type == 'city' and is_small_country(country_id, small_city_threshold):
        dest_type = 'small_city'
    elif dest_type == 'area' and is_small_country(country_id, small_city_threshold):
        dest_type = 'small_area'
    
    if dest_type == 'hotel':
        # Hotels: 6 factors - need to calculate city/area scores
        city_score = result.get('city_score', 0)
        area_score = result.get('area_score', 0)
        
        # If city/area scores not available, calculate them
        if city_score == 0 and area_score == 0:
            city_score, area_score = calculate_location_score_on_demand(
                result['city_id'], 
                result.get('area_id'), 
                factor_weights, 
                small_city_threshold
            )
        
        factors = [
            city_score,
            area_score,
            result.get('agoda_score_normalized', 0),
            result.get('google_score_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0)
        ]
        
        hotel_weights = factor_weights['hotel']
        factor_weight_list = [
            hotel_weights['city_score_weight'],
            hotel_weights['area_score_weight'],
            hotel_weights['agoda_score_weight'],
            hotel_weights['google_score_weight'],
            hotel_weights['expenditure_score_weight'],
            hotel_weights['departure_score_weight']
        ]
        
        # Calculate score: Σ(factor × coefficient) / 6
        weighted_sum = sum(factor * coeff for factor, coeff in zip(factors, factor_weight_list))
        final_score = weighted_sum / 6
        
    else:
        # Locations: 4 factors
        factors = [
            result.get('hotel_count_normalized', 0),
            result.get('country_hotel_count_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0)
        ]
        
        location_weights = factor_weights[dest_type]
        factor_weight_list = [
            location_weights['hotel_count_weight'],
            location_weights['country_hotel_count_weight'],
            location_weights['expenditure_score_weight'],
            location_weights['departure_score_weight']
        ]
        
        # Calculate score: Σ(factor × coefficient) / 4
        weighted_sum = sum(factor * coeff for factor, coeff in zip(factors, factor_weight_list))
        final_score = weighted_sum / 4
    
    return final_score


def calculate_scores_for_hierarchical_search(fts_results, factor_weights):
    """
    Alternative scoring function specifically designed for hierarchical search.
    Now mainly just calls the main function since scoring happens earlier.
    """
    return calculate_scores_in_memory(fts_results, factor_weights)


def load_location_weights_from_database():
    """Load 4-factor weights for cities, areas, small_cities, small_areas from location_weights table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type, hotel_count_weight, country_hotel_count_weight, 
               expenditure_score_weight, departure_score_weight 
        FROM location_weights
    ''')
    
    weights_data = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary structure
    location_weights = {}
    for row in weights_data:
        dest_type = row[0]
        location_weights[dest_type] = {
            'hotel_count_weight': row[1],
            'country_hotel_count_weight': row[2],
            'expenditure_score_weight': row[3],
            'departure_score_weight': row[4]
        }
    
    return location_weights


def load_hotel_weights_from_database():
    """
    Load 6-factor weights for hotels from hotel_weights table.
    Uses new column names (city_score_weight, area_score_weight).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if new columns exist, otherwise fall back to old columns for migration
    cursor.execute("PRAGMA table_info(hotel_weights)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'city_score_weight' in columns and 'area_score_weight' in columns:
        # Use new column names
        cursor.execute('''
            SELECT type, city_score_weight, area_score_weight, 
                   agoda_score_weight, google_score_weight, 
                   expenditure_score_weight, departure_score_weight 
            FROM hotel_weights
        ''')
    else:
        # Fall back to old column names for migration
        cursor.execute('''
            SELECT type, hotel_count_weight, country_hotel_count_weight, 
                   agoda_score_weight, google_score_weight, 
                   expenditure_score_weight, departure_score_weight 
            FROM hotel_weights
        ''')
    
    weights_data = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary structure
    hotel_weights = {}
    for row in weights_data:
        dest_type = row[0]  # Should be 'hotel'
        hotel_weights[dest_type] = {
            'city_score_weight': row[1],  # Maps to first weight column
            'area_score_weight': row[2],  # Maps to second weight column
            'agoda_score_weight': row[3],
            'google_score_weight': row[4],
            'expenditure_score_weight': row[5],
            'departure_score_weight': row[6]
        }
    
    return hotel_weights


def load_weights_from_database():
    """Load current factor weights from both location_weights and hotel_weights tables"""
    # Load location weights (4 factors)
    location_weights = load_location_weights_from_database()
    
    # Load hotel weights (6 factors)
    hotel_weights = load_hotel_weights_from_database()
    
    # Merge into single dictionary
    all_weights = {**location_weights, **hotel_weights}
    
    # Set defaults if missing using config
    from config import get_default_weights
    defaults = get_default_weights()
    
    if 'city' not in all_weights:
        all_weights['city'] = defaults['city']
    
    if 'area' not in all_weights:
        all_weights['area'] = defaults['area']
    
    if 'small_city' not in all_weights:
        all_weights['small_city'] = defaults['small_city']
    
    if 'small_area' not in all_weights:
        all_weights['small_area'] = defaults['small_area']
    
    if 'hotel' not in all_weights:
        all_weights['hotel'] = defaults['hotel']
    
    return all_weights


def save_location_weights_to_database(location_weights):
    """Save 4-factor weights to location_weights table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for dest_type in ['city', 'area', 'small_city', 'small_area']:
        if dest_type in location_weights:
            weight_dict = location_weights[dest_type]
            cursor.execute('''
                INSERT OR REPLACE INTO location_weights 
                (type, hotel_count_weight, country_hotel_count_weight, 
                 expenditure_score_weight, departure_score_weight)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dest_type,
                weight_dict['hotel_count_weight'],
                weight_dict['country_hotel_count_weight'],
                weight_dict['expenditure_score_weight'],
                weight_dict['departure_score_weight']
            ))
    
    conn.commit()
    conn.close()


def save_hotel_weights_to_database(hotel_weights):
    """
    Save 6-factor weights to hotel_weights table.
    Uses new column names (city_score_weight, area_score_weight).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if 'hotel' in hotel_weights:
        weight_dict = hotel_weights['hotel']
        cursor.execute('''
            INSERT OR REPLACE INTO hotel_weights 
            (type, city_score_weight, area_score_weight, 
             agoda_score_weight, google_score_weight, 
             expenditure_score_weight, departure_score_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'hotel',
            weight_dict['city_score_weight'],
            weight_dict['area_score_weight'],
            weight_dict['agoda_score_weight'],
            weight_dict['google_score_weight'],
            weight_dict['expenditure_score_weight'],
            weight_dict['departure_score_weight']
        ))
    
    conn.commit()
    conn.close()


def save_weights_to_database(factor_weights):
    """Save current in-memory factor weights back to appropriate database tables"""
    # Split weights by type
    location_weights = {}
    hotel_weights = {}
    
    for dest_type, weight_dict in factor_weights.items():
        if dest_type in ['city', 'area', 'small_city', 'small_area']:
            location_weights[dest_type] = weight_dict
        elif dest_type == 'hotel':
            hotel_weights[dest_type] = weight_dict
    
    # Save to appropriate tables
    if location_weights:
        save_location_weights_to_database(location_weights)
    
    if hotel_weights:
        save_hotel_weights_to_database(hotel_weights)


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
        if result.get('country_id'):
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


# Legacy function for backward compatibility
def calculate_weighted_score(factors, weights):
    """
    Legacy function - now just calls simple weighted average
    Kept for backward compatibility if needed elsewhere.
    """
    if not factors or not weights or len(factors) != len(weights):
        return 0
    
    weighted_sum = sum(factor * weight for factor, weight in zip(factors, weights))
    return weighted_sum / len(factors)