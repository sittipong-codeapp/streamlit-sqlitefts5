import streamlit as st
import atexit
from database import init_database
from search_destinations import search_destinations
from ui_components import render_sidebar, render_search_results
from scoring import load_weights_from_database, save_weights_to_database


# Global in-memory configuration
if 'app_config' not in st.session_state:
    st.session_state.app_config = {
        'weights': None,
        'weights_loaded': False,
        'weights_changed': False,
        'last_query': '',
        'last_fts_results': None
    }


def initialize_app():
    """Initialize the application - load weights into memory"""
    if not st.session_state.app_config['weights_loaded']:
        try:
            # Load weights from database into memory
            st.session_state.app_config['weights'] = load_weights_from_database()
            st.session_state.app_config['weights_loaded'] = True
            
            # Register cleanup function to save weights on exit
            def save_weights_on_exit():
                if st.session_state.app_config.get('weights_changed', False):
                    save_weights_to_database(st.session_state.app_config['weights'])
            
            atexit.register(save_weights_on_exit)
            
        except Exception as e:
            st.error(f"Failed to load weights from database: {e}")
            # Set default weights if database load fails
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
                }
            }
            st.session_state.app_config['weights_loaded'] = True


def save_weights_periodically():
    """Save weights to database if they have changed"""
    if st.session_state.app_config.get('weights_changed', False):
        try:
            save_weights_to_database(st.session_state.app_config['weights'])
            st.session_state.app_config['weights_changed'] = False
            return True
        except Exception as e:
            st.error(f"Failed to save weights to database: {e}")
            return False
    return True


def handle_search(query):
    """Handle search with caching and auto-recalculation"""
    current_weights = st.session_state.app_config['weights']
    
    # Check if we need to perform a new FTS search or can reuse cached results
    if (query != st.session_state.app_config['last_query'] or 
        st.session_state.app_config['last_fts_results'] is None):
        
        # Perform new FTS search
        fts_results = search_destinations(query)
        st.session_state.app_config['last_query'] = query
        st.session_state.app_config['last_fts_results'] = fts_results
        st.session_state.app_config['weights_changed'] = False  # Reset weights changed flag
        
    else:
        # Reuse cached FTS results
        fts_results = st.session_state.app_config['last_fts_results']
    
    # Always render with current weights (this will recalculate scores if weights changed)
    render_search_results(fts_results, current_weights)
    
    # If weights were changed during this render, mark them as changed
    if hasattr(st.session_state, 'weights_changed') and st.session_state.weights_changed:
        st.session_state.app_config['weights_changed'] = True
        # Clear the session state flag
        del st.session_state.weights_changed


# Streamlit app
def main():
    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Search Suggestion Sandbox", 
        initial_sidebar_state="collapsed"
    )

    # Initialize the database
    init_database()
    
    # Initialize the application (load weights)
    initialize_app()

    # Web interface
    st.title("Search Suggestion Sandbox")

    # Add save weights button in sidebar header
    with st.sidebar:
        st.header("Factor Weight Configuration")
        
        # Show save button if weights have changed
        if st.session_state.app_config.get('weights_changed', False):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Weights", help="Save current weights to database"):
                    if save_weights_periodically():
                        st.success("Weights saved successfully!")
                    else:
                        st.error("Failed to save weights!")
            with col2:
                st.write("⚠️ *Unsaved changes*")
        else:
            st.write("✅ *Weights saved*")
        
        st.divider()

    # Render sidebar with weight configuration
    current_weights = st.session_state.app_config['weights']
    weights_updated = render_sidebar(current_weights)
    
    # Mark weights as changed if they were updated
    if weights_updated:
        st.session_state.app_config['weights_changed'] = True
    
    query = st.text_input("Enter your search query:")
    
    if query and len(query.strip()) >= 2:
        with st.spinner("Searching destinations..."):
            handle_search(query.strip())
    elif query and len(query.strip()) < 2:
        st.info("Please enter at least 2 characters to search.")

if __name__ == "__main__":
    main()