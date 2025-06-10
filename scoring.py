from database import get_connection


# Function to update factor weights and recalculate total score
def update_weights(dest_type, hotel_count_weight=0, country_hotel_count_weight=0, agoda_score_weight=0, google_score_weight=0, expenditure_score_weight=0, departure_score_weight=0):
    conn = get_connection()
    cursor = conn.cursor()

    # Validate weights (should be between 0 and 1)
    if not all(0 <= w <= 1 for w in [hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight]):
        conn.close()
        return False

    # Validate destination type
    if dest_type not in ["city", "area", "hotel"]:
        conn.close()
        return False

    # Update the weights for the specified destination type
    # All destination types now use all 6 weights
    cursor.execute('''
        UPDATE factor_weights
        SET hotel_count_weight = ?,
            country_hotel_count_weight = ?,
            agoda_score_weight = ?,
            google_score_weight = ?,
            expenditure_score_weight = ?,
            departure_score_weight = ?
        WHERE type = ?
    ''', (hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight, dest_type))

    # Recalculate scores based on destination type
    if dest_type == "hotel":
        _recalculate_hotel_scores(cursor, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight)
    else:
        _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight)

    conn.commit()
    conn.close()
    return True


def _recalculate_hotel_scores(cursor, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight):
    """Recalculate scores for hotels based on 6 factors: city normalization + hotel review scores + country outbound scores"""
    
    # Get max scores for normalization
    cursor.execute("SELECT MAX(agoda_score), MAX(google_score) FROM hotel_scores")
    result = cursor.fetchone()
    max_agoda_score = result[0] if result and result[0] else 100
    max_google_score = result[1] if result and result[1] else 100

    # Get all hotel destinations using the offset
    cursor.execute('''
        SELECT d.id as destination_id, d.country_id, d.city_id
        FROM destination d
        WHERE d.type = 'hotel'
    ''')
    hotel_destinations = cursor.fetchall()

    for destination_id, country_id, city_id in hotel_destinations:
        # Get original hotel ID by removing offset
        hotel_id = destination_id - 20000
        
        # Get hotel's own review scores
        cursor.execute('SELECT agoda_score, google_score FROM hotel_scores WHERE hotel_id = ?', (hotel_id,))
        result = cursor.fetchone()
        if result:
            agoda_score, google_score = result
        else:
            agoda_score, google_score = 0, 0
        
        # Normalize hotel review scores (0-100 scale)
        agoda_normalized = int((agoda_score / max_agoda_score) * 100) if agoda_score else 0
        google_normalized = int((google_score / max_google_score) * 100) if google_score else 0
        
        # Get the city's hotel normalization scores (inherit from parent city)
        cursor.execute('''
            SELECT s.hotel_count_normalized, s.country_hotel_count_normalized
            FROM destination d
            JOIN destination_score s ON d.id = s.destination_id
            WHERE d.city_id = ? AND d.type = 'city'
        ''', (city_id,))
        city_result = cursor.fetchone()
        
        if city_result:
            city_hotel_count_normalized, city_country_hotel_count_normalized = city_result
        else:
            # Fallback: calculate city scores if not found
            cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
            city_hotel_result = cursor.fetchone()
            city_hotel_count = city_hotel_result[0] if city_hotel_result else 0
            
            # Get max city hotels for normalization
            cursor.execute('SELECT MAX(total_hotels) FROM city')
            max_city_result = cursor.fetchone()
            max_city_hotels = max_city_result[0] if max_city_result and max_city_result[0] else 1
            
            city_hotel_count_normalized = int((city_hotel_count / max_city_hotels) * 100)
            
            # Get country normalization
            cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
            max_country_result = cursor.fetchone()
            max_country_hotels = max_country_result[0] if max_country_result and max_country_result[0] else 1
            
            city_country_hotel_count_normalized = (
                int((city_hotel_count / max_country_hotels) * 100)
                if max_country_hotels > 200
                else 0
            )
        
        # Get outbound scores for this country (inherit from parent country)
        cursor.execute(
            'SELECT expenditure_score, departure_score FROM country_outbound WHERE country_id = ?',
            (country_id,)
        )
        outbound_result = cursor.fetchone()
        if outbound_result:
            expenditure_score_normalized = int(outbound_result[0])
            departure_score_normalized = int(outbound_result[1])
        else:
            expenditure_score_normalized = 0
            departure_score_normalized = 0
        
        # Calculate weighted total score with six factors
        weighted_sum = (
            (city_hotel_count_normalized * hotel_count_weight) + 
            (city_country_hotel_count_normalized * country_hotel_count_weight) +
            (agoda_normalized * agoda_score_weight) + 
            (google_normalized * google_score_weight) +
            (expenditure_score_normalized * expenditure_score_weight) +
            (departure_score_normalized * departure_score_weight)
        )
        factor_sum = hotel_count_weight + country_hotel_count_weight + agoda_score_weight + google_score_weight + expenditure_score_weight + departure_score_weight
        
        total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

        # Update score for hotel using destination_id
        cursor.execute('''
            INSERT OR REPLACE INTO destination_score 
            (destination_id, hotel_count_normalized, country_hotel_count_normalized, 
             agoda_score_normalized, google_score_normalized, expenditure_score_normalized, 
             departure_score_normalized, total_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (destination_id, city_hotel_count_normalized, city_country_hotel_count_normalized, 
              agoda_normalized, google_normalized, expenditure_score_normalized, departure_score_normalized, total_score))


def _recalculate_location_scores(cursor, dest_type, hotel_count_weight, country_hotel_count_weight, expenditure_score_weight, departure_score_weight):
    """Recalculate scores for cities and areas with four factors (agoda and google scores are not applicable)"""
    
    # Get max city hotel count for normalization
    cursor.execute("SELECT MAX(total_hotels) FROM city")
    result = cursor.fetchone()
    max_city_hotels = result[0] if result and result[0] else 1

    # Get all destinations of the specified type with their relationships
    cursor.execute("SELECT id, city_id, area_id, country_id FROM destination WHERE type = ?", (dest_type,))
    destinations = cursor.fetchall()

    for dest_id, city_id, area_id, country_id in destinations:
        if not country_id:
            continue

        # Get hotel count from appropriate location table using direct queries
        if dest_type == "city":
            cursor.execute('SELECT total_hotels FROM city WHERE id = ?', (city_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1
        else:  # area
            # For areas, count actual hotels in this area
            cursor.execute('SELECT COUNT(*) FROM hotel WHERE area_id = ?', (area_id,))
            result = cursor.fetchone()
            hotel_count = result[0] if result else 0

            cursor.execute('SELECT MAX(total_hotels) FROM city WHERE country_id = ?', (country_id,))
            result = cursor.fetchone()
            max_country_city_hotels = result[0] if result and result[0] else 1

        # Normalize hotel counts
        hotel_count_normalized = int((hotel_count / max_city_hotels) * 100)
        country_hotel_count_normalized = (
            int((hotel_count / max_country_city_hotels) * 100)
            if max_country_city_hotels > 200
            else 0
        )

        # Get outbound scores for this country
        cursor.execute(
            'SELECT expenditure_score, departure_score FROM country_outbound WHERE country_id = ?',
            (country_id,)
        )
        outbound_result = cursor.fetchone()
        if outbound_result:
            expenditure_score_normalized = int(outbound_result[0])
            departure_score_normalized = int(outbound_result[1])
        else:
            expenditure_score_normalized = 0
            departure_score_normalized = 0

        # Calculate weighted total score with four factors (agoda and google scores are 0 for cities/areas)
        weighted_sum = (
            (hotel_count_normalized * hotel_count_weight) + 
            (country_hotel_count_normalized * country_hotel_count_weight) +
            (expenditure_score_normalized * expenditure_score_weight) +
            (departure_score_normalized * departure_score_weight)
        )
        factor_sum = hotel_count_weight + country_hotel_count_weight + expenditure_score_weight + departure_score_weight

        total_score = weighted_sum / factor_sum if factor_sum > 0 else 0

        # Update the score (agoda and google scores remain 0 for cities/areas)
        cursor.execute('''
            UPDATE destination_score
            SET hotel_count_normalized = ?, country_hotel_count_normalized = ?, 
                agoda_score_normalized = 0, google_score_normalized = 0,
                expenditure_score_normalized = ?, departure_score_normalized = ?, total_score = ?
            WHERE destination_id = ?
        ''', (hotel_count_normalized, country_hotel_count_normalized, expenditure_score_normalized, departure_score_normalized, total_score, dest_id))