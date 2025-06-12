from database import get_connection


def calculate_scores_in_memory(fts_results, factor_weights):
    """
    Calculate final scores for search results in memory using new coefficient-based scoring system.
    Updated to handle hierarchical search results (locations + conditional hotels).
    New formula: Final Score = (factor1×coeff1 + factor2×coeff2 + ... + factorN×coeffN) / N
    Where N = 4 for cities/areas/small_cities/small_areas, N = 6 for hotels
    
    UPDATED: Small area classification now based on parent city size, not area size.
    """
    if not fts_results:
        return []
    
    # Load small city threshold
    small_city_threshold = load_small_city_threshold()
    
    scored_results = []
    
    for result in fts_results:
        dest_type = result['type']
        
        # Dynamic classification using threshold
        # UPDATED: Area classification now uses parent city hotel count
        if dest_type == 'city' and result['hotel_count'] <= small_city_threshold:
            dest_type = 'small_city'
        elif dest_type == 'area' and result['parent_city_hotel_count'] <= small_city_threshold:
            dest_type = 'small_area'
        
        if dest_type == 'hotel':
            # Hotels use 6 factors - direct array, no extraction needed
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
            # Cities, small cities, areas, and small areas use 4 factors - direct array
            factors = [
                result['hotel_count_normalized'],
                result['country_hotel_count_normalized'],
                result['expenditure_score_normalized'],
                result['departure_score_normalized']
            ]
            
            location_weights = factor_weights[dest_type]  # 'city', 'small_city', 'area', or 'small_area'
            factor_weight_list = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
        
        # Calculate final score using new coefficient-based formula
        # Sum of (factor × coefficient) divided by factor count
        weighted_sum = sum(factor * coeff for factor, coeff in zip(factors, factor_weight_list))
        final_score = weighted_sum / len(factors)
        
        # Create result tuple in the format expected by UI
        # FIXED: Properly map location weights to the 6-position array for UI display
        if len(factor_weight_list) == 4:  # Location types
            # Map 4 location weights to 6-position array: [hotel, country, agoda, google, expenditure, departure]
            padded_weights = [
                factor_weight_list[0],  # hotel_count_weight
                factor_weight_list[1],  # country_hotel_count_weight  
                0,                      # agoda_score_weight (not applicable for locations)
                0,                      # google_score_weight (not applicable for locations)
                factor_weight_list[2],  # expenditure_score_weight
                factor_weight_list[3]   # departure_score_weight
            ]
        else:  # Hotel types (already 6 weights)
            padded_weights = factor_weight_list
        
        scored_result = (
            dest_type,  # This will now be 'small_city' or 'small_area' for small destinations
            result['name'],
            result['country_name'],
            result['city_name'],
            result['area_name'],
            result['hotel_count'],
            result['hotel_count_normalized'],
            result['country_hotel_count_normalized'],
            result.get('agoda_score_normalized', 0),  # 0 for cities/areas
            result.get('google_score_normalized', 0),  # 0 for cities/areas
            result['expenditure_score_normalized'],
            result['departure_score_normalized'],
            final_score,  # This is now the simple coefficient-based score
            padded_weights[0],  # hotel_count_weight
            padded_weights[1],  # country_hotel_count_weight
            padded_weights[2],  # agoda_score_weight (0 for cities/areas)
            padded_weights[3],  # google_score_weight (0 for cities/areas)
            padded_weights[4],  # expenditure_score_weight (NOW CORRECT!)
            padded_weights[5],  # departure_score_weight (NOW CORRECT!)
            result['country_total_hotels'],
            final_score,  # Base score same as final score (no category multiplier)
            0,  # Category weight removed (set to 0 for UI compatibility)
            1   # Category multiplier removed (set to 1 for UI compatibility)
        )
        
        scored_results.append(scored_result)
    
    # CRITICAL: Sort by final score (descending) and limit to top 20
    # This ensures proper ranking when locations + hotels are combined
    scored_results.sort(key=lambda x: x[12], reverse=True)  # x[12] is final_score
    return scored_results[:20]


def calculate_scores_for_hierarchical_search(fts_results, factor_weights):
    """
    Alternative scoring function specifically designed for hierarchical search.
    Provides more explicit handling of the two-phase result combination.
    """
    if not fts_results:
        return []
    
    # Separate results by type for analysis
    location_results = [r for r in fts_results if r['type'] in ['city', 'area']]
    hotel_results = [r for r in fts_results if r['type'] == 'hotel']
    
    # Calculate scores for all results using main function
    scored_results = calculate_scores_in_memory(fts_results, factor_weights)
    
    # Optional: Add debug info about search composition
    if hasattr(scored_results, '_debug_info'):
        scored_results._debug_info = {
            'location_count': len(location_results),
            'hotel_count': len(hotel_results),
            'total_count': len(fts_results),
            'hotel_search_triggered': len(hotel_results) > 0
        }
    
    return scored_results


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
    """Load 6-factor weights for hotels from hotel_weights table"""
    conn = get_connection()
    cursor = conn.cursor()
    
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
            'hotel_count_weight': row[1],
            'country_hotel_count_weight': row[2],
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
    """Save 6-factor weights to hotel_weights table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if 'hotel' in hotel_weights:
        weight_dict = hotel_weights['hotel']
        cursor.execute('''
            INSERT OR REPLACE INTO hotel_weights 
            (type, hotel_count_weight, country_hotel_count_weight, 
             agoda_score_weight, google_score_weight, 
             expenditure_score_weight, departure_score_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'hotel',
            weight_dict['hotel_count_weight'],
            weight_dict['country_hotel_count_weight'],
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