"""
Default configuration values for the destination search application.
Each destination type has its own separate weight configuration for maximum flexibility.
"""

# Default factor weights for cities - 4 factors
# Corresponds to CITY_COEFFICIENTS: [1.0, 0.1, 0.1, 0.1]
DEFAULT_CITY_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.1,
    "expenditure_score_weight": 0.1,
    "departure_score_weight": 0.1
}

# Default factor weights for small cities - 4 factors
# Corresponds to SMALL_CITY_COEFFICIENTS: [1.0, 0.0, 0.1, 0.1]
DEFAULT_SMALL_CITY_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.0,
    "expenditure_score_weight": 0.1,
    "departure_score_weight": 0.1
}

# Default factor weights for areas - 4 factors
# Corresponds to AREA_COEFFICIENTS: [1.0, 0.1, 0.1, 0.1]
DEFAULT_AREA_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.1,
    "expenditure_score_weight": 0.1,
    "departure_score_weight": 0.1
}

# Default factor weights for small areas - 4 factors
# Corresponds to SMALL_AREA_COEFFICIENTS: [1.0, 0.0, 0.0, 0.0]
DEFAULT_SMALL_AREA_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.0,
    "expenditure_score_weight": 0.0,
    "departure_score_weight": 0.0
}

# Default factor weights for hotels - 6 factors
# Corresponds to HOTEL_COEFFICIENTS: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
DEFAULT_HOTEL_WEIGHTS = {
    "hotel_count_weight": 0.0,
    "country_hotel_count_weight": 0.0,
    "agoda_score_weight": 0.0,
    "google_score_weight": 0.0,
    "expenditure_score_weight": 0.0,
    "departure_score_weight": 0.0
}

# Small city classification threshold
DEFAULT_SMALL_CITY_THRESHOLD = 300


def get_default_weights():
    """
    Get complete default weights dictionary for all destination types.
    Returns a deep copy to prevent accidental modification.
    
    Returns:
        dict: Dictionary with keys 'city', 'small_city', 'area', 'small_area', 'hotel'
              each containing their respective default weight configurations
    """
    return {
        "city": DEFAULT_CITY_WEIGHTS.copy(),
        "small_city": DEFAULT_SMALL_CITY_WEIGHTS.copy(),
        "area": DEFAULT_AREA_WEIGHTS.copy(),
        "small_area": DEFAULT_SMALL_AREA_WEIGHTS.copy(),
        "hotel": DEFAULT_HOTEL_WEIGHTS.copy()
    }


def get_default_city_weights():
    """
    Get default weights for cities.
    
    Returns:
        dict: Default city weights (4 factors)
    """
    return DEFAULT_CITY_WEIGHTS.copy()


def get_default_small_city_weights():
    """
    Get default weights for small cities.
    
    Returns:
        dict: Default small city weights (4 factors)
    """
    return DEFAULT_SMALL_CITY_WEIGHTS.copy()


def get_default_area_weights():
    """
    Get default weights for areas.
    
    Returns:
        dict: Default area weights (4 factors)
    """
    return DEFAULT_AREA_WEIGHTS.copy()


def get_default_small_area_weights():
    """
    Get default weights for small areas.
    
    Returns:
        dict: Default small area weights (4 factors)
    """
    return DEFAULT_SMALL_AREA_WEIGHTS.copy()


def get_default_hotel_weights():
    """
    Get default weights for hotels.
    
    Returns:
        dict: Default hotel weights (6 factors)
    """
    return DEFAULT_HOTEL_WEIGHTS.copy()


def get_default_threshold():
    """
    Get default small city threshold.
    
    Returns:
        int: Default threshold for small city classification
    """
    return DEFAULT_SMALL_CITY_THRESHOLD