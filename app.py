import streamlit as st
import atexit
import json
from datetime import datetime
from database import init_database
from search_destinations import search_destinations
from ui_components import render_sidebar, render_search_results
from scoring import (
    load_weights_from_database, 
    save_weights_to_database, 
    load_small_city_threshold
)
from score_calculator import create_default_weights_by_type


# Global in-memory configuration
if 'app_config' not in st.session_state:
    st.session_state.app_config = {
        'weights': None,
        'small_city_threshold': None,
        'weights_loaded': False,
        'threshold_loaded': False,
        'weights_changed': False,
        'threshold_changed': False,
        'last_query': '',
        'last_search_results': None  # Changed from last_fts_results to last_search_results
    }


def load_weights_from_file():
    """Load weights from last_weights.json file"""
    try:
        with open('last_weights.json', 'r') as f:
            file_data = json.load(f)
        
        # Extract weights and threshold from file
        weights = file_data.get('weights')
        threshold = file_data.get('threshold')
        
        if weights and threshold is not None:
            # Update threshold in session state
            st.session_state.app_config['small_city_threshold'] = threshold
            st.session_state.app_config['threshold_loaded'] = True
            return weights
        else:
            return None
            
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        return None


def save_weights_to_file():
    """Save current weights and threshold to last_weights.json"""
    try:
        weights_data = {
            'weights': st.session_state.app_config['weights'],
            'threshold': st.session_state.app_config['small_city_threshold'],
            'timestamp': datetime.now().isoformat()
        }
        with open('last_weights.json', 'w') as f:
            json.dump(weights_data, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save weights to file: {e}")
        return False


def log_search_session(query, search_results):
    """Log search session with coefficients and results to search_log.json"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'search_query': query,
        'coefficients': st.session_state.app_config['weights'],
        'threshold': st.session_state.app_config['small_city_threshold'],
        'results': [
            {
                'name': result['name'],
                'type': result['type'],
                'country': result['country_name'],
                'city': result['city_name'],
                'area': result.get('area_name', ''),
                'final_score': result.get('final_score', 0)
            }
            for result in search_results[:10]  # Log top 10 results
        ],
        'total_results': len(search_results)
    }
    
    try:
        # Append to existing log or create new
        try:
            with open('search_log.json', 'r') as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []
        
        logs.append(log_entry)
        
        with open('search_log.json', 'w') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        st.error(f"Failed to log search session: {e}")


def save_weights_to_file_and_log():
    """Save weights to file and mark as saved"""
    success = save_weights_to_file()
    if success:
        st.session_state.app_config['weights_changed'] = False
    return success


def initialize_app():
    """Initialize the application - load weights and threshold into memory"""
    if not st.session_state.app_config['weights_loaded']:
        try:
            # NEW: Try to load from file first (PRIORITY)
            file_weights = load_weights_from_file()
            if file_weights:
                st.session_state.app_config['weights'] = file_weights
                st.session_state.app_config['weights_loaded'] = True
                st.success("✅ Loaded weights from last_weights.json")
            else:
                # Fallback to database if file doesn't exist
                st.session_state.app_config['weights'] = load_weights_from_database()
                st.session_state.app_config['weights_loaded'] = True
                st.info("📁 Loaded default weights from database (no saved file found)")
            
        except Exception as e:
            st.error(f"Failed to load weights: {e}")
            # Final fallback to config defaults
            from config import get_default_weights
            st.session_state.app_config['weights'] = get_default_weights()
            st.session_state.app_config['weights_loaded'] = True

    if not st.session_state.app_config['threshold_loaded']:
        # Only load threshold from database if not already loaded from file
        if st.session_state.app_config['small_city_threshold'] is None:
            try:
                # Load small city threshold from database into memory
                st.session_state.app_config['small_city_threshold'] = load_small_city_threshold()
                st.session_state.app_config['threshold_loaded'] = True
                
            except Exception as e:
                st.error(f"Failed to load small city threshold from database: {e}")
                # Set default threshold from config if database load fails
                from config import get_default_threshold
                st.session_state.app_config['small_city_threshold'] = get_default_threshold()
                st.session_state.app_config['threshold_loaded'] = True

    # Register cleanup function to save weights on exit (only once)
    if not hasattr(st.session_state, 'cleanup_registered'):
        def save_weights_on_exit():
            if st.session_state.app_config.get('weights_changed', False):
                save_weights_to_file()
        
        atexit.register(save_weights_on_exit)
        st.session_state.cleanup_registered = True


def save_weights_periodically():
    """DEPRECATED: This function now redirects to file-based saving"""
    return save_weights_to_file_and_log()


def handle_search(query):
    """
    SIMPLIFIED: Handle search with caching but no score recalculation.
    The enhanced search logic now returns pre-scored results, so we just cache and display them.
    """
    current_factor_weights = st.session_state.app_config['weights']
    
    # Check if we need to perform a new search or can reuse cached results
    # FIXED: Now properly detects weight changes and threshold changes
    if (query != st.session_state.app_config['last_query'] or 
        st.session_state.app_config['last_search_results'] is None or
        st.session_state.app_config.get('weights_changed', False) or
        st.session_state.app_config.get('threshold_changed', False)):
        
        # Perform new search - this now returns pre-scored results
        search_results = search_destinations(query)
        st.session_state.app_config['last_query'] = query
        st.session_state.app_config['last_search_results'] = search_results
        # Reset flags after new search
        st.session_state.app_config['weights_changed'] = False
        st.session_state.app_config['threshold_changed'] = False
        
        # NEW: Log the search session when results are displayed
        if search_results:
            log_search_session(query, search_results)
        
    else:
        # Reuse cached search results (they're already scored)
        search_results = st.session_state.app_config['last_search_results']
    
    # Render results - they come pre-scored from the enhanced search logic
    render_search_results(search_results, current_factor_weights)


def validate_app_config():
    """Validate that app configuration has proper factor structure"""
    weights = st.session_state.app_config.get('weights', {})
    
    # Validate that all destination types have proper factor structure
    from score_calculator import validate_weights_by_type, get_factor_count
    
    validation_issues = []
    
    for dest_type in ['city', 'area', 'small_city', 'small_area', 'hotel']:
        if dest_type not in weights:
            validation_issues.append(f"Missing weights for {dest_type}")
            continue
            
        type_weights = weights[dest_type]
        expected_factor_count = get_factor_count(dest_type)
        actual_factor_count = len(type_weights)
        
        if actual_factor_count != expected_factor_count:
            validation_issues.append(
                f"{dest_type} has {actual_factor_count} factors, expected {expected_factor_count}"
            )
            
        if not validate_weights_by_type(dest_type, type_weights):
            validation_issues.append(f"Invalid weight structure for {dest_type}")
    
    if validation_issues:
        st.error("App configuration validation failed:")
        for issue in validation_issues:
            st.error(f"- {issue}")
        
        # Reset to defaults from config
        st.warning("Resetting to default weights...")
        from config import get_default_weights
        st.session_state.app_config['weights'] = get_default_weights()
        st.session_state.app_config['weights_changed'] = True
        
        return False
    
    return True


# Streamlit app
def main():
    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Search Suggestion Sandbox", 
        initial_sidebar_state="collapsed",
        layout="wide"
    )

    # Initialize the database
    init_database()
    
    # Initialize the application (load weights and threshold)
    initialize_app()
    
    # Validate app configuration
    if not validate_app_config():
        st.warning("App configuration was reset. Please refresh the page.")
        return

    # Web interface
    st.title("Search Suggestion Sandbox")

    # Add save weights button in sidebar header
    with st.sidebar:
        st.header("Weight Configuration")
        
        # Always show save button
        if st.button("💾 Save to File", help="Save current coefficients to last_weights.json"):
            if save_weights_to_file_and_log():
                st.success("Weights saved to file!")
            else:
                st.error("Failed to save weights!")
        
        st.divider()

    # Render sidebar with weight configuration
    current_factor_weights = st.session_state.app_config['weights']
    
    factor_weights_updated = render_sidebar(current_factor_weights)
    
    # REMOVED: The old logic that manually set weights_changed flag
    # The flag is now set directly in ui_components.py when weights are updated
    
    query = st.text_input("Enter your search query:")
    
    if query and len(query.strip()) >= 2:
        with st.spinner("Searching destinations..."):
            handle_search(query.strip())
    elif query and len(query.strip()) < 2:
        st.info("Please enter at least 2 characters to search.")


if __name__ == "__main__":
    main()