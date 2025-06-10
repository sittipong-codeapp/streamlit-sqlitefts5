from database import get_connection


def calculate_scores_in_memory(fts_results, weights):
    """
    Calculate final scores for search results in memory using current weights.
    No database updates - just scoring and ranking.
    """
    if not fts_results:
        return []
    
    scored_results = []
    
    for result in fts_results:
        dest_type = result['type']
        
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
            
            hotel_weights = weights['hotel']
            factor_weights = [
                hotel_weights['hotel_count_weight'],
                hotel_weights['country_hotel_count_weight'],
                hotel_weights['agoda_score_weight'],
                hotel_weights['google_score_weight'],
                hotel_weights['expenditure_score_weight'],
                hotel_weights['departure_score_weight']
            ]
            
        else:
            # Cities and areas use 4 factors (agoda and google are 0)
            factors = [
                result['hotel_count_normalized'],
                result['country_hotel_count_normalized'],
                result['expenditure_score_normalized'],
                result['departure_score_normalized']
            ]
            
            location_weights = weights[dest_type]  # 'city' or 'area'
            factor_weights = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
        
        # Calculate weighted score
        total_score = calculate_weighted_score(factors, factor_weights)
        
        # Create result tuple in the format expected by UI
        scored_result = (
            result['type'],
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
            total_score,  # This is the calculated score
            factor_weights[0] if len(factor_weights) > 0 else 0,  # hotel_count_weight
            factor_weights[1] if len(factor_weights) > 1 else 0,  # country_hotel_count_weight
            factor_weights[2] if len(factor_weights) > 2 else 0,  # agoda_score_weight (0 for cities/areas)
            factor_weights[3] if len(factor_weights) > 3 else 0,  # google_score_weight (0 for cities/areas)
            factor_weights[4] if len(factor_weights) > 4 else factor_weights[2] if dest_type != 'hotel' else factor_weights[4],  # expenditure_score_weight
            factor_weights[5] if len(factor_weights) > 5 else factor_weights[3] if dest_type != 'hotel' else factor_weights[5],  # departure_score_weight
            result['country_total_hotels']
        )
        
        scored_results.append(scored_result)
    
    # Sort by total score (descending) and limit to top 20
    scored_results.sort(key=lambda x: x[12], reverse=True)  # x[12] is total_score
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
    """Load current weights from database into memory structure"""
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
            'hotel_count_weight': 0.4,
            'country_hotel_count_weight': 0.2,
            'agoda_score_weight': 0,
            'google_score_weight': 0,
            'expenditure_score_weight': 0.25,
            'departure_score_weight': 0.15
        }
    
    if 'area' not in weights:
        weights['area'] = {
            'hotel_count_weight': 0.3,
            'country_hotel_count_weight': 0.2,
            'agoda_score_weight': 0,
            'google_score_weight': 0,
            'expenditure_score_weight': 0.3,
            'departure_score_weight': 0.2
        }
    
    if 'hotel' not in weights:
        weights['hotel'] = {
            'hotel_count_weight': 0.167,
            'country_hotel_count_weight': 0.167,
            'agoda_score_weight': 0.167,
            'google_score_weight': 0.167,
            'expenditure_score_weight': 0.166,
            'departure_score_weight': 0.166
        }
    
    return weights


def save_weights_to_database(weights):
    """Save current in-memory weights back to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    for dest_type, weight_dict in weights.items():
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


# Remove the old functions that are no longer needed
# def update_weights() - REMOVED
# def _recalculate_hotel_scores() - REMOVED  
# def _recalculate_location_scores() - REMOVED