import streamlit as st
import atexit
from database import init_database
from search_destinations import search_destinations
from ui_components import render_sidebar, render_search_results
from scoring import (
    load_weights_from_database, 
    save_weights_to_database, 
    load_thresholds
)
from score_calculator import create_default_weights_by_type


# Global in-memory configuration
if 'app_config' not in st.session_state:
    st.session_state.app_config = {
        'weights': None,
        'thresholds': None,
        'weights_loaded': False,
        'thresholds_loaded': False,
        'weights_changed': False,
        'thresholds_changed': False,
        'last_query': '',
        'last_fts_results': None
    }


def initialize_app():
    """Initialize the application - load weights and thresholds into memory"""
    if not st.session_state.app_config['weights_loaded']:
        try:
            # Load factor weights from database into memory (now from separate tables)
            st.session_state.app_config['weights'] = load_weights_from_database()
            st.session_state.app_config['weights_loaded'] = True
            
        except Exception as e:
            st.error(f"Failed to load factor weights from database: {e}")
            # Set default factor weights from config if database load fails
            from config import get_default_weights
            st.session_state.app_config['weights'] = get_default_weights()
            st.session_state.app_config['weights_loaded'] = True

    if not st.session_state.app_config['thresholds_loaded']:
        try:
            # Load dual thresholds from database into memory
            st.session_state.app_config['thresholds'] = load_thresholds()
            st.session_state.app_config['thresholds_loaded'] = True
            
        except Exception as e:
            st.error(f"Failed to load thresholds from database: {e}")
            # Set default thresholds from config if database load fails
            from config import get_default_thresholds
            st.session_state.app_config['thresholds'] = get_default_thresholds()
            st.session_state.app_config['thresholds_loaded'] = True

    # Register cleanup function to save weights on exit (only once)
    if not hasattr(st.session_state, 'cleanup_registered'):
        def save_weights_on_exit():
            if st.session_state.app_config.get('weights_changed', False):
                save_weights_to_database(st.session_state.app_config['weights'])
            # Note: thresholds are saved immediately when changed, so no need to save on exit
        
        atexit.register(save_weights_on_exit)
        st.session_state.cleanup_registered = True


def save_weights_periodically():
    """Save factor weights to database if they have changed"""
    success = True
    
    # Save factor weights if changed (now goes to separate tables)
    if st.session_state.app_config.get('weights_changed', False):
        try:
            save_weights_to_database(st.session_state.app_config['weights'])
            st.session_state.app_config['weights_changed'] = False
        except Exception as e:
            st.error(f"Failed to save factor weights to database: {e}")
            success = False
    
    # Note: thresholds are saved immediately when changed, so no periodic save needed
    
    return success


def handle_search(query):
    """Handle search with caching and auto-recalculation"""
    current_factor_weights = st.session_state.app_config['weights']
    
    # Check if we need to perform a new FTS search or can reuse cached results
    if (query != st.session_state.app_config['last_query'] or 
        st.session_state.app_config['last_fts_results'] is None):
        
        # Perform new FTS search (now returns clean factor structure)
        fts_results = search_destinations(query)
        st.session_state.app_config['last_query'] = query
        st.session_state.app_config['last_fts_results'] = fts_results
        # Reset weights changed flags when new search is performed
        st.session_state.app_config['weights_changed'] = False
        
    else:
        # Reuse cached FTS results
        fts_results = st.session_state.app_config['last_fts_results']
    
    # Always render with current weights (this will recalculate scores if weights changed)
    render_search_results(fts_results, current_factor_weights)
    
    # If weights were changed during this render, mark them as changed
    if hasattr(st.session_state, 'weights_changed') and st.session_state.weights_changed:
        st.session_state.app_config['weights_changed'] = True
        # Clear the session state flag
        del st.session_state.weights_changed


def validate_app_config():
    """Validate that app configuration has proper factor structure and thresholds"""
    weights = st.session_state.app_config.get('weights', {})
    thresholds = st.session_state.app_config.get('thresholds', {})
    
    # Validate that all destination types have proper factor structure
    from score_calculator import validate_weights_by_type, get_factor_count
    
    validation_issues = []
    
    # Validate weights for all 5 destination types
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
    
    # Validate dual thresholds
    if not thresholds:
        validation_issues.append("Missing threshold configuration")
    else:
        if 'city' not in thresholds:
            validation_issues.append("Missing city threshold")
        elif not isinstance(thresholds['city'], int) or thresholds['city'] < 0:
            validation_issues.append("Invalid city threshold (must be non-negative integer)")
            
        if 'area' not in thresholds:
            validation_issues.append("Missing area threshold")
        elif not isinstance(thresholds['area'], int) or thresholds['area'] < 0:
            validation_issues.append("Invalid area threshold (must be non-negative integer)")
    
    if validation_issues:
        st.error("App configuration validation failed:")
        for issue in validation_issues:
            st.error(f"- {issue}")
        
        # Reset to defaults from config
        st.warning("Resetting to default configuration...")
        from config import get_default_weights, get_default_thresholds
        st.session_state.app_config['weights'] = get_default_weights()
        st.session_state.app_config['thresholds'] = get_default_thresholds()
        st.session_state.app_config['weights_changed'] = True
        st.session_state.app_config['thresholds_changed'] = True
        
        return False
    
    return True


# Streamlit app
def main():
    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Search Suggestion Sandbox", 
        initial_sidebar_state="collapsed"
    )

    # Initialize the database
    init_database()
    
    # Initialize the application (load weights and thresholds)
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
        
        # Check if weights have changed
        weights_changed = st.session_state.app_config.get('weights_changed', False)
        
        # Show save button if weights have changed
        if weights_changed:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Weights", help="Save factor weights to database"):
                    if save_weights_periodically():
                        st.success("Weights saved successfully!")
                    else:
                        st.error("Failed to save weights!")
            with col2:
                st.write(f"⚠️ *Unsaved: factor weights*")
        else:
            st.write("✅ *All weights saved*")
        
        st.divider()

    # Render sidebar with weight configuration
    current_factor_weights = st.session_state.app_config['weights']
    
    factor_weights_updated = render_sidebar(current_factor_weights)
    
    # Mark weights as changed if they were updated
    if factor_weights_updated:
        st.session_state.app_config['weights_changed'] = True
    
    query = st.text_input("Enter your search query:")
    
    if query and len(query.strip()) >= 2:
        with st.spinner("Searching destinations..."):
            handle_search(query.strip())
    elif query and len(query.strip()) < 2:
        st.info("Please enter at least 2 characters to search.")


if __name__ == "__main__":
    main()