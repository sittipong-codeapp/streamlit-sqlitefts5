import streamlit as st
from database import init_database
from search_destinations import search_destinations
from ui_components import render_sidebar, render_search_results


# Streamlit app
def main():
    # Set sidebar to collapsed by default
    st.set_page_config(
        page_title="Search Suggestion Sandbox", initial_sidebar_state="collapsed"
    )

    # Initialize the database
    init_database()

    # Web interface
    st.title("🔍 Search Suggestion Sandbox")

    # Render sidebar with weight configuration
    render_sidebar()

    # Search section
    query = st.text_input("Search for a destination:")
    if query:
        results = search_destinations(query)
        render_search_results(results)


if __name__ == "__main__":
    main()