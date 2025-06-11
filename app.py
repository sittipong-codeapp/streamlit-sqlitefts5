import streamlit as st
import atexit
from database import init_database
from search_destinations import search_destinations
from ui_components import render_sidebar, render_search_results
from scoring import load_weights_from_database, save_weights_to_database, load_category_weights_from_database, save_category_weights_to_database, load_small_city_threshold


# Global in-memory configuration
if 'app_config' not in st.session_state:
    st.session_state.app_config = {
        'weights': None,
        'category_weights': None,
        'small_city_threshold': None,
        'weights_loaded': False,
        'category_weights_loaded': False,
        'threshold_loaded': False,
        'weights_changed': False,
        'category_weights_changed': False,
        'threshold_changed': False,
        'last_query': '',
        'last_fts_results': None
    }


def initialize_app():
    """Initialize the application - load weights, category weights and threshold into memory"""
    if not st.session_state.app_config['weights_loaded']:
        try:
            # Load factor weights from database into memory
            st.session_state.app_config['weights'] = load_weights_from_database()
            st.session_state.app_config['weights_loaded'] = True
            
        except Exception as e:
            st.error(f"Failed to load factor weights from database: {e}")
            # Set default factor weights if database load fails
            st.session_state.app_config['weights'] = {
                'city': {
                    'hotel_count_weight': 1.0,
                    'country_hotel_count_weight': 0.625,
                    'agoda_score_weight': 0,
                    'google_score_weight': 0,
                    'expenditure_score_weight': 0.025,
                    'departure_score_weight': 0.025
                },
                'area': {
                    'hotel_count_weight': 1.0,
                    'country_hotel_count_weight': 0.625,
                    'agoda_score_weight': 0,
                    'google_score_weight': 0,
                    'expenditure_score_weight': 0.025,
                    'departure_score_weight': 0.025
                },
                'hotel': {
                    'hotel_count_weight': 0.001,
                    'country_hotel_count_weight': 0.001,
                    'agoda_score_weight': 0.001,
                    'google_score_weight': 0.001,
                    'expenditure_score_weight': 0.001,
                    'departure_score_weight': 0.001
                },
                'small_city': {
                    'hotel_count_weight': 1.0,
                    'country_hotel_count_weight': 0.625,
                    'agoda_score_weight': 0,
                    'google_score_weight': 0,
                    'expenditure_score_weight': 0.025,
                    'departure_score_weight': 0.025
                }
            }
            st.session_state.app_config['weights_loaded'] = True

    if not st.session_state.app_config['category_weights_loaded']:
        try:
            # Load category weights from database into memory
            st.session_state.app_config['category_weights'] = load_category_weights_from_database()
            st.session_state.app_config['category_weights_loaded'] = True
            
        except Exception as e:
            st.error(f"Failed to load category weights from database: {e}")
            # Set default category weights if database load fails
            st.session_state.app_config['category_weights'] = {
                'city': 10.0,
                'area': 1.0,
                'hotel': 0.1,
                'small_city': 5.0
            }
            st.session_state.app_config['category_weights_loaded'] = True

    if not st.session_state.app_config['threshold_loaded']:
        try:
            # Load small city threshold from database into memory
            st.session_state.app_config['small_city_threshold'] = load_small_city_threshold()
            st.session_state.app_config['threshold_loaded'] = True
            
        except Exception as e:
            st.error(f"Failed to load small city threshold from database: {e}")
            # Set default threshold if database load fails
            st.session_state.app_config['small_city_threshold'] = 50
            st.session_state.app_config['threshold_loaded'] = True

    # Register cleanup function to save weights on exit (only once)
    if not hasattr(st.session_state, 'cleanup_registered'):
        def save_weights_on_exit():
            if st.session_state.app_config.get('weights_changed', False):
                save_weights_to_database(st.session_state.app_config['weights'])
            if st.session_state.app_config.get('category_weights_changed', False):
                save_category_weights_to_database(st.session_state.app_config['category_weights'])
            # Note: threshold is saved immediately when changed, so no need to save on exit
        
        atexit.register(save_weights_on_exit)
        st.session_state.cleanup_registered = True


def save_weights_periodically():
    """Save factor weights and category weights to database if they have changed"""
    success = True
    
    # Save factor weights if changed
    if st.session_state.app_config.get('weights_changed', False):
        try:
            save_weights_to_database(st.session_state.app_config['weights'])
            st.session_state.app_config['weights_changed'] = False
        except Exception as e:
            st.error(f"Failed to save factor weights to database: {e}")
            success = False
    
    # Save category weights if changed
    if st.session_state.app_config.get('category_weights_changed', False):
        try:
            save_category_weights_to_database(st.session_state.app_config['category_weights'])
            st.session_state.app_config['category_weights_changed'] = False
        except Exception as e:
            st.error(f"Failed to save category weights to database: {e}")
            success = False
    
    # Note: threshold is saved immediately when changed, so no periodic save needed
    
    return success


def handle_search(query):
    """Handle search with caching and auto-recalculation"""
    current_factor_weights = st.session_state.app_config['weights']
    current_category_weights = st.session_state.app_config['category_weights']
    
    # Check if we need to perform a new FTS search or can reuse cached results
    if (query != st.session_state.app_config['last_query'] or 
        st.session_state.app_config['last_fts_results'] is None):
        
        # Perform new FTS search
        fts_results = search_destinations(query)
        st.session_state.app_config['last_query'] = query
        st.session_state.app_config['last_fts_results'] = fts_results
        # Reset weights changed flags when new search is performed
        st.session_state.app_config['weights_changed'] = False
        st.session_state.app_config['category_weights_changed'] = False
        
    else:
        # Reuse cached FTS results
        fts_results = st.session_state.app_config['last_fts_results']
    
    # Always render with current weights (this will recalculate scores if weights changed)
    render_search_results(fts_results, current_factor_weights, current_category_weights)
    
    # If weights were changed during this render, mark them as changed
    if hasattr(st.session_state, 'weights_changed') and st.session_state.weights_changed:
        st.session_state.app_config['weights_changed'] = True
        # Clear the session state flag
        del st.session_state.weights_changed
    
    if hasattr(st.session_state, 'category_weights_changed') and st.session_state.category_weights_changed:
        st.session_state.app_config['category_weights_changed'] = True
        # Clear the session state flag
        del st.session_state.category_weights_changed


# Streamlit app
def main():
    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Search Suggestion Sandbox", 
        initial_sidebar_state="collapsed"
    )

    # Initialize the database
    init_database()
    
    # Initialize the application (load weights and threshold)
    initialize_app()

    # Web interface
    st.title("Search Suggestion Sandbox")

    # Add save weights button in sidebar header
    with st.sidebar:
        st.header("Weight Configuration")
        
        # Check if any weights have changed
        weights_changed = st.session_state.app_config.get('weights_changed', False)
        category_weights_changed = st.session_state.app_config.get('category_weights_changed', False)
        any_weights_changed = weights_changed or category_weights_changed
        
        # Show save button if weights have changed
        if any_weights_changed:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save All Weights", help="Save factor weights and category weights to database"):
                    if save_weights_periodically():
                        st.success("All weights saved successfully!")
                    else:
                        st.error("Failed to save some weights!")
            with col2:
                change_details = []
                if weights_changed:
                    change_details.append("factor weights")
                if category_weights_changed:
                    change_details.append("category weights")
                st.write(f"⚠️ *Unsaved: {', '.join(change_details)}*")
        else:
            st.write("✅ *All weights saved*")
        
        st.divider()

    # Render sidebar with weight configuration
    current_factor_weights = st.session_state.app_config['weights']
    current_category_weights = st.session_state.app_config['category_weights']
    
    factor_weights_updated, category_weights_updated = render_sidebar(
        current_factor_weights, 
        current_category_weights
    )
    
    # Mark weights as changed if they were updated
    if factor_weights_updated:
        st.session_state.app_config['weights_changed'] = True
    
    if category_weights_updated:
        st.session_state.app_config['category_weights_changed'] = True
    
    query = st.text_input("Enter your search query:")
    
    if query and len(query.strip()) >= 2:
        with st.spinner("Searching destinations..."):
            handle_search(query.strip())
    elif query and len(query.strip()) < 2:
        st.info("Please enter at least 2 characters to search.")

if __name__ == "__main__":
    main()