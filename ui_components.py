import streamlit as st
import pandas as pd
from scoring import calculate_scores_in_memory, load_small_city_threshold, save_small_city_threshold


def render_sidebar(current_factor_weights, current_category_weights):
    """Render the sidebar with threshold, category weights and factor weight configuration forms"""
    st.sidebar.header("Weight Configuration")

    # Track if any weights were updated
    category_weights_updated = False
    factor_weights_updated = False
    threshold_updated = False

    # === SMALL CITY THRESHOLD SECTION (TOP PRIORITY) ===
    st.sidebar.subheader("🏘️ Small City Threshold")
    st.sidebar.markdown(
        """
        *Set the hotel count threshold that determines which cities are classified as "small cities":*
        - Cities with **≤ threshold hotels** = Small City
        - Cities with **> threshold hotels** = Regular City
        """
    )

    with st.sidebar.form("threshold_form"):
        current_threshold = load_small_city_threshold()
        threshold_input = st.text_input(
            "Hotel Count Threshold:", 
            value=str(current_threshold),
            help="Cities with this many hotels or fewer will be classified as 'small cities'"
        )
        
        submit_threshold = st.form_submit_button("Update Threshold")
        
        if submit_threshold:
            try:
                threshold_value = int(threshold_input)
                if threshold_value >= 0:
                    save_small_city_threshold(threshold_value)
                    st.sidebar.success(f"Threshold updated to {threshold_value} hotels!")
                    threshold_updated = True
                else:
                    st.sidebar.error("Threshold must be 0 or greater.")
            except ValueError:
                st.sidebar.error("Please enter a valid integer for the threshold.")

    st.sidebar.divider()

    # === CATEGORY WEIGHTS SECTION ===
    st.sidebar.subheader("🎯 Category Priority Weights")
    st.sidebar.markdown(
        """
        *Control the relative importance of destination types:*
        - **Higher values** = destination type appears higher in results
        - **Lower values** = destination type appears lower in results
        """
    )

    with st.sidebar.form("category_weight_form"):
        city_weight = st.text_input(
            "City Weight:", 
            value=str(current_category_weights['city']),
            help="Priority weight for cities (default: 10.0 = highest priority)"
        )
        small_city_weight = st.text_input(
            "Small City Weight:", 
            value=str(current_category_weights['small_city']),
            help="Priority weight for small cities (default: 5.0 = medium-high priority)"
        )
        area_weight = st.text_input(
            "Area Weight:", 
            value=str(current_category_weights['area']),
            help="Priority weight for areas (default: 1.0 = medium priority)"
        )
        hotel_weight = st.text_input(
            "Hotel Weight:", 
            value=str(current_category_weights['hotel']),
            help="Priority weight for hotels (default: 0.1 = lowest priority)"
        )
        
        # Show category weight sum
        try:
            city_weight_float = float(city_weight)
            small_city_weight_float = float(small_city_weight)
            area_weight_float = float(area_weight)
            hotel_weight_float = float(hotel_weight)
            total = city_weight_float + small_city_weight_float + area_weight_float + hotel_weight_float
            
            st.write(f"Category Weight Sum: {total:.4f}")
        except ValueError:
            st.write("Invalid weight values entered")
        
        submit_category = st.form_submit_button("Update Category Weights")
        
        if submit_category:
            try:
                # Convert string inputs to float
                city_weight_float = float(city_weight)
                small_city_weight_float = float(small_city_weight)
                area_weight_float = float(area_weight)
                hotel_weight_float = float(hotel_weight)
                
                # Validate weights (should be >= 0)
                if all(w >= 0 for w in [city_weight_float, small_city_weight_float, area_weight_float, hotel_weight_float]):
                    # Update in-memory category weights
                    current_category_weights.update({
                        'city': city_weight_float,
                        'small_city': small_city_weight_float,
                        'area': area_weight_float,
                        'hotel': hotel_weight_float
                    })
                    st.sidebar.success("Category weights updated successfully!")
                    category_weights_updated = True
                    
                    # Mark that category weights have changed for potential auto-recalculation
                    st.session_state.category_weights_changed = True
                else:
                    st.sidebar.error("All weights must be 0 or greater.")
                    
            except ValueError:
                st.sidebar.error("Please enter valid numeric values for all weights.")

    st.sidebar.divider()

    # === FACTOR WEIGHTS SECTION ===
    st.sidebar.subheader("⚙️ Factor Weight Configuration")
    st.sidebar.markdown(
        """
        *Fine-tune the importance of each scoring factor within destination types:*
        - **Cities, Small Cities & Areas**: Hotel count normalization + outbound tourism factors
        - **Hotels**: City hotel normalization + individual review scores + outbound tourism factors
        
        *Adjust weights below to fine-tune your search experience.*
        """
    )

    dest_types = ["city", "small_city", "area", "hotel"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.replace('_', ' ').title()} Factor Weights")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (6 factors: city normalization + hotel review scores + outbound scores)
                hotel_count_weight = st.text_input(
                    f"Global Hotel Normalization:",
                    value=str(current_factor_weights[dest_type]["hotel_count_weight"]),
                    help="Inherits the global hotel count normalization from the hotel's city"
                )

                country_hotel_count_weight = st.text_input(
                    f"Country Hotel Normalization:",
                    value=str(current_factor_weights[dest_type]["country_hotel_count_weight"]),
                    help="Inherits the country hotel count normalization from the hotel's city"
                )

                agoda_score_weight = st.text_input(
                    f"Agoda Score Weight:",
                    value=str(current_factor_weights[dest_type]["agoda_score_weight"]),
                    help="Hotel's individual Agoda review score"
                )

                google_score_weight = st.text_input(
                    f"Google Score Weight:",
                    value=str(current_factor_weights[dest_type]["google_score_weight"]),
                    help="Hotel's individual Google review score"
                )

                expenditure_score_weight = st.text_input(
                    f"Expenditure Score Weight:",
                    value=str(current_factor_weights[dest_type]["expenditure_score_weight"]),
                    help="Inherits the outbound tourism expenditure score from the hotel's country"
                )

                departure_score_weight = st.text_input(
                    f"Departure Score Weight:",
                    value=str(current_factor_weights[dest_type]["departure_score_weight"]),
                    help="Inherits the outbound tourism departure score from the hotel's country"
                )

                # Convert string inputs to float and show weight sum for validation
                try:
                    weight_sum = (
                        float(hotel_count_weight) + 
                        float(country_hotel_count_weight) + 
                        float(agoda_score_weight) + 
                        float(google_score_weight) + 
                        float(expenditure_score_weight) + 
                        float(departure_score_weight)
                    )
                    st.write(f"Factor Weight Sum: {weight_sum:.4f}")
                except ValueError:
                    st.write("Invalid weight values entered")
                    weight_sum = 0

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.replace('_', ' ').title()} Weights"
                )

                if submit_weights:
                    try:
                        # Convert string inputs to float
                        hotel_count_weight_float = float(hotel_count_weight)
                        country_hotel_count_weight_float = float(country_hotel_count_weight)
                        agoda_score_weight_float = float(agoda_score_weight)
                        google_score_weight_float = float(google_score_weight)
                        expenditure_score_weight_float = float(expenditure_score_weight)
                        departure_score_weight_float = float(departure_score_weight)

                        # Validate weights (should be between 0 and 1)
                        if all(0 <= w <= 1 for w in [hotel_count_weight_float, country_hotel_count_weight_float, 
                                                   agoda_score_weight_float, google_score_weight_float,
                                                   expenditure_score_weight_float, departure_score_weight_float]):
                            
                            # Update in-memory weights - NO DATABASE CALL
                            current_factor_weights[dest_type].update({
                                "hotel_count_weight": hotel_count_weight_float,
                                "country_hotel_count_weight": country_hotel_count_weight_float,
                                "agoda_score_weight": agoda_score_weight_float,
                                "google_score_weight": google_score_weight_float,
                                "expenditure_score_weight": expenditure_score_weight_float,
                                "departure_score_weight": departure_score_weight_float
                            })
                            
                            st.sidebar.success(f"{dest_type.replace('_', ' ').title()} weights updated successfully!")
                            factor_weights_updated = True
                            
                            # Mark that weights have changed for potential auto-recalculation
                            st.session_state.weights_changed = True
                        else:
                            st.sidebar.error("All weights must be between 0 and 1.")
                            
                    except ValueError:
                        st.sidebar.error("Please enter valid numeric values for all weights.")

            else:
                # City/Small City/Area weights (4 factors: hotel count normalization + outbound scores)
                hotel_count_weight = st.text_input(
                    f"Global Hotel Normalization:",
                    value=str(current_factor_weights[dest_type]["hotel_count_weight"]),
                )

                country_hotel_count_weight = st.text_input(
                    f"Country Hotel Normalization:",
                    value=str(current_factor_weights[dest_type]["country_hotel_count_weight"]),
                )

                expenditure_score_weight = st.text_input(
                    f"Expenditure Score Weight:",
                    value=str(current_factor_weights[dest_type]["expenditure_score_weight"]),
                )

                departure_score_weight = st.text_input(
                    f"Departure Score Weight:",
                    value=str(current_factor_weights[dest_type]["departure_score_weight"]),
                )

                # Convert string inputs to float and show weight sum for validation
                try:
                    weight_sum = (
                        float(hotel_count_weight) + 
                        float(country_hotel_count_weight) + 
                        float(expenditure_score_weight) + 
                        float(departure_score_weight)
                    )
                    st.write(f"Factor Weight Sum: {weight_sum:.4f}")
                except ValueError:
                    st.write("Invalid weight values entered")
                    weight_sum = 0

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.replace('_', ' ').title()} Weights"
                )

                if submit_weights:
                    try:
                        # Convert string inputs to float
                        hotel_count_weight_float = float(hotel_count_weight)
                        country_hotel_count_weight_float = float(country_hotel_count_weight)
                        expenditure_score_weight_float = float(expenditure_score_weight)
                        departure_score_weight_float = float(departure_score_weight)

                        # Validate weights (should be between 0 and 1)
                        if all(0 <= w <= 1 for w in [hotel_count_weight_float, country_hotel_count_weight_float,
                                                   expenditure_score_weight_float, departure_score_weight_float]):
                            
                            # Update in-memory weights - NO DATABASE CALL
                            current_factor_weights[dest_type].update({
                                "hotel_count_weight": hotel_count_weight_float,
                                "country_hotel_count_weight": country_hotel_count_weight_float,
                                "expenditure_score_weight": expenditure_score_weight_float,
                                "departure_score_weight": departure_score_weight_float
                            })
                            
                            st.sidebar.success(f"{dest_type.replace('_', ' ').title()} weights updated successfully!")
                            factor_weights_updated = True
                            
                            # Mark that weights have changed for potential auto-recalculation
                            st.session_state.weights_changed = True
                        else:
                            st.sidebar.error("All weights must be between 0 and 1.")
                            
                    except ValueError:
                        st.sidebar.error("Please enter valid numeric values for all weights.")

    return factor_weights_updated, category_weights_updated


def render_search_results(fts_results, current_factor_weights, current_category_weights):
    """
    Render search results with in-memory score calculation using both factor weights and category weights.
    Takes raw FTS results and current weights, calculates scores in Python.
    Now supports small city classification.
    """
    if not fts_results:
        st.write("No matching destinations found.")
        return

    # Calculate scores in memory using current factor weights and category weights
    scored_results = calculate_scores_in_memory(fts_results, current_factor_weights, current_category_weights)
    
    if not scored_results:
        st.write("No matching destinations found.")
        return

    # Create main results dataframe (enhanced with category weight info)
    df = pd.DataFrame(
        scored_results,
        columns=[
            "Type",
            "Name",
            "Country",
            "City",
            "Area",
            "Hotel Count",
            "Normalized: Hotel Count",
            "Normalized: Country Hotel Count",
            "Normalized: Agoda Score",
            "Normalized: Google Score",
            "Normalized: Expenditure Score",
            "Normalized: Departure Score",
            "Final Score",  # This is now the category-weighted score
            "Weight: Hotel Count",
            "Weight: Country Hotel Count",
            "Weight: Agoda Score",
            "Weight: Google Score",
            "Weight: Expenditure Score",
            "Weight: Departure Score",
            "Country Total Hotels",
            "Base Score",           # Score before category weight
            "Category Weight",      # Raw category weight
            "Category Multiplier"   # Normalized category multiplier
        ],
    )

    # Create a display name column that formats differently based on type
    df["Display Name"] = df.apply(
        lambda row: (
            f"{row['Name']}, {row['City']}"
            if row["Type"] == "area"
            else row["Name"]
        ),
        axis=1,
    )

    st.write(f"Found {len(scored_results)} matching destinations:")

    # Show current threshold info
    current_threshold = load_small_city_threshold()
    st.info(f"ℹ️ Current small city threshold: {current_threshold} hotels (cities with ≤{current_threshold} hotels are classified as small cities)")

    # Show results with 7 columns as requested
    display_df = df[
        [
            "Display Name",
            "Type",
            "Area",
            "City",
            "Country",
            "Final Score",
            "Base Score"
        ]
    ]
    
    st.dataframe(
        display_df,
        column_config={
            "Display Name": st.column_config.TextColumn(width="medium"),
            "Final Score": st.column_config.NumberColumn(format="%.4f"),
            "Base Score": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    # Show current weight configuration
    with st.expander("View Current Weight Configuration"):
        
        # === SMALL CITY THRESHOLD SECTION ===
        st.subheader("🏘️ Small City Threshold")
        st.markdown(f"**Current Threshold:** {current_threshold} hotels")
        st.markdown("Cities with this many hotels or fewer are classified as 'small cities'")
        
        st.divider()
        
        # === CATEGORY WEIGHTS SECTION ===
        st.subheader("🎯 Category Priority Weights")
        
        category_weights_display = []
        
        for dest_type, weight in current_category_weights.items():
            display_name = dest_type.replace('_', ' ').title()
                
            category_weights_display.append({
                "Destination Type": display_name,
                "Weight": f"{weight:.1f}"
            })
        
        category_df = pd.DataFrame(category_weights_display)
        st.dataframe(category_df, hide_index=True)
        
        st.divider()
        
        # === FACTOR WEIGHTS SECTION ===
        st.subheader("⚙️ Factor Weights by Destination Type")
        
        # Group by type and show weights with appropriate labels
        factor_weights_df = df[
            ["Type", "Weight: Hotel Count", "Weight: Country Hotel Count", 
             "Weight: Agoda Score", "Weight: Google Score", 
             "Weight: Expenditure Score", "Weight: Departure Score"]
        ].drop_duplicates()
        
        # Add meaningful column names based on type
        factor_weights_display = []
        for _, row in factor_weights_df.iterrows():
            display_type = row["Type"].replace('_', ' ').title()
            
            if row["Type"] == "hotel":
                # Hotels show all 6 factors
                factor_weights_display.append({
                    "Type": display_type,
                    "Global Hotel Count": f"{row['Weight: Hotel Count']:.4f}",
                    "Country Hotel Count": f"{row['Weight: Country Hotel Count']:.4f}",
                    "Agoda Score": f"{row['Weight: Agoda Score']:.4f}",
                    "Google Score": f"{row['Weight: Google Score']:.4f}",
                    "Expenditure Score": f"{row['Weight: Expenditure Score']:.4f}",
                    "Departure Score": f"{row['Weight: Departure Score']:.4f}"
                })
            else:
                # Cities, small cities and areas show 4 factors
                factor_weights_display.append({
                    "Type": display_type,
                    "Global Hotel Count": f"{row['Weight: Hotel Count']:.4f}",
                    "Country Hotel Count": f"{row['Weight: Country Hotel Count']:.4f}",
                    "Expenditure Score": f"{row['Weight: Expenditure Score']:.4f}",
                    "Departure Score": f"{row['Weight: Departure Score']:.4f}",
                    "Agoda Score": "N/A",
                    "Google Score": "N/A"
                })
        
        factor_weights_display_df = pd.DataFrame(factor_weights_display)
        st.dataframe(factor_weights_display_df, hide_index=True)
        
        # === SCORING EXPLANATION ===
        st.subheader("📊 Scoring Explanation")
        st.markdown("""
        **Two-Tier Scoring System:**
        1. **Base Score** = Weighted average of normalized factors (0-100)
        2. **Final Score** = Base Score × Category Multiplier
        
        **Category Multiplier** = Category Weight ÷ Total Category Weight
        
        **Dynamic Classification:** Cities are automatically classified as "Small City" if their hotel count ≤ threshold.
        
        *This ensures destination types with higher category weights rank higher, even with lower base scores.*
        """)

    # Show scoring breakdown for top 10 results
    with st.expander("View Detailed Scoring for Top 10 Results"):
        top_10 = df.head(10)
        
        for i, (_, row) in enumerate(top_10.iterrows(), 1):
            display_type = row['Type'].replace('_', ' ').title()
            st.markdown(f"**#{i}: {row['Display Name']} ({display_type})**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Final Score", f"{row['Final Score']:.4f}")
            
            with col2:
                st.metric("Base Score", f"{row['Base Score']:.4f}")
            
            with col3:
                st.metric("Category Multiplier", f"{row['Category Multiplier']:.4f}")
            
            # Show factor breakdown
            if row['Type'] == 'hotel':
                factors = [
                    ("Global Hotel Count", row['Normalized: Hotel Count'], row['Weight: Hotel Count']),
                    ("Country Hotel Count", row['Normalized: Country Hotel Count'], row['Weight: Country Hotel Count']),
                    ("Agoda Score", row['Normalized: Agoda Score'], row['Weight: Agoda Score']),
                    ("Google Score", row['Normalized: Google Score'], row['Weight: Google Score']),
                    ("Expenditure Score", row['Normalized: Expenditure Score'], row['Weight: Expenditure Score']),
                    ("Departure Score", row['Normalized: Departure Score'], row['Weight: Departure Score'])
                ]
            else:
                factors = [
                    ("Global Hotel Count", row['Normalized: Hotel Count'], row['Weight: Hotel Count']),
                    ("Country Hotel Count", row['Normalized: Country Hotel Count'], row['Weight: Country Hotel Count']),
                    ("Expenditure Score", row['Normalized: Expenditure Score'], row['Weight: Expenditure Score']),
                    ("Departure Score", row['Normalized: Departure Score'], row['Weight: Departure Score'])
                ]
            
            factor_breakdown = []
            for factor_name, normalized_value, weight in factors:
                if weight > 0:  # Only show factors with non-zero weights
                    weighted_contribution = normalized_value * weight
                    factor_breakdown.append({
                        "Factor": factor_name,
                        "Normalized Value": f"{normalized_value:.0f}",
                        "Weight": f"{weight:.4f}",
                        "Contribution": f"{weighted_contribution:.2f}"
                    })
            
            if factor_breakdown:
                factor_df = pd.DataFrame(factor_breakdown)
                st.dataframe(factor_df, hide_index=True)
            
            st.markdown("---")