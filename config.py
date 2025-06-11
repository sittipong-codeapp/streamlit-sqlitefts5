"""
Default configuration values for the destination search application.
Each destination type has its own separate weight configuration for maximum flexibility.
"""

# Default factor weights for cities - 4 factors
DEFAULT_CITY_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.625,
    "expenditure_score_weight": 0.025,
    "departure_score_weight": 0.025
}

# Default factor weights for small cities - 4 factors
DEFAULT_SMALL_CITY_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.625,
    "expenditure_score_weight": 0.025,
    "departure_score_weight": 0.025
}

# Default factor weights for areas - 4 factors
DEFAULT_AREA_WEIGHTS = {
    "hotel_count_weight": 1.0,
    "country_hotel_count_weight": 0.625,
    "expenditure_score_weight": 0.025,
    "departure_score_weight": 0.025
}

# Default factor weights for hotels - 6 factors
DEFAULT_HOTEL_WEIGHTS = {
    "hotel_count_weight": 0.001,
    "country_hotel_count_weight": 0.001,
    "agoda_score_weight": 0.001,
    "google_score_weight": 0.001,
    "expenditure_score_weight": 0.001,
    "departure_score_weight": 0.001
}

# Small city classification threshold
DEFAULT_SMALL_CITY_THRESHOLD = 50


def get_default_weights():
    """
    Get complete default weights dictionary for all destination types.
    Returns a deep copy to prevent accidental modification.
    
    Returns:
        dict: Dictionary with keys 'city', 'small_city', 'area', 'hotel'
              each containing their respective default weight configurations
    """
    return {
        "city": DEFAULT_CITY_WEIGHTS.copy(),
        "small_city": DEFAULT_SMALL_CITY_WEIGHTS.copy(),
        "area": DEFAULT_AREA_WEIGHTS.copy(),
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