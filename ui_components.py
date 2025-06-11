import streamlit as st
import pandas as pd
from scoring import calculate_scores_in_memory, load_small_city_threshold, save_small_city_threshold


def render_sidebar(current_factor_weights):
    """Render the sidebar with threshold and factor weight configuration forms"""
    st.sidebar.header("Weight Configuration")

    # Track if weights were updated
    factor_weights_updated = False
    threshold_updated = False

    # === SMALL CITY THRESHOLD SECTION (TOP PRIORITY) ===
    st.sidebar.subheader("🏘️ Small City/Area Threshold")
    st.sidebar.markdown(
        """
        *Set the hotel count threshold that determines classification for both cities and areas:*
        - Cities with **≤ threshold hotels** = Small City
        - Cities with **> threshold hotels** = Regular City
        - Areas with **≤ threshold hotels** = Small Area
        - Areas with **> threshold hotels** = Regular Area
        """
    )

    with st.sidebar.form("threshold_form"):
        current_threshold = load_small_city_threshold()
        threshold_input = st.text_input(
            "Hotel Count Threshold:", 
            value=str(current_threshold),
            help="Cities and areas with this many hotels or fewer will be classified as 'small'"
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

    # === FACTOR WEIGHTS SECTION ===
    st.sidebar.subheader("⚙️ Factor Weight Configuration")
    st.sidebar.markdown(
        """
        *Configure the coefficients for the scoring formula:*
        
        **Scoring Formula:** `Σ(factorᵢ × coeffᵢ) / N`
        
        - **Cities, Small Cities, Areas & Small Areas**: 4 factors (divide by 4)
        - **Hotels**: 6 factors (divide by 6)
        
        *Use coefficient values to control destination type priority:*
        - **High coefficients (≈1.0)**: Destination type will rank higher
        - **Low coefficients (≈0.01)**: Destination type will rank lower
        """
    )

    dest_types = ["city", "small_city", "area", "small_area", "hotel"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.replace('_', ' ').title()} Coefficients")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (6 factors)
                factor_weights_updated = render_hotel_factor_form(dest_type, current_factor_weights)
            else:
                # Location weights (4 factors)
                factor_weights_updated = render_location_factor_form(dest_type, current_factor_weights)
                
            if factor_weights_updated:
                # Mark that factor weights have changed for potential auto-recalculation
                st.session_state.weights_changed = True

    return factor_weights_updated


def render_location_factor_form(dest_type, current_factor_weights):
    """Render factor weight form for cities, areas, small_cities, small_areas (4 factors only)"""
    
    # Location weights (4 factors: no agoda/google inputs)
    hotel_count_weight = st.text_input(
        f"Global Hotel Normalization:",
        value=str(current_factor_weights[dest_type]["hotel_count_weight"]),
        help="Coefficient for global hotel count normalization (0-1)"
    )

    country_hotel_count_weight = st.text_input(
        f"Country Hotel Normalization:",
        value=str(current_factor_weights[dest_type]["country_hotel_count_weight"]),
        help="Coefficient for country-relative hotel count normalization (0-1)"
    )

    expenditure_score_weight = st.text_input(
        f"Expenditure Score Coefficient:",
        value=str(current_factor_weights[dest_type]["expenditure_score_weight"]),
        help="Coefficient for outbound tourism expenditure score (0-1)"
    )

    departure_score_weight = st.text_input(
        f"Departure Score Coefficient:",
        value=str(current_factor_weights[dest_type]["departure_score_weight"]),
        help="Coefficient for outbound tourism departure score (0-1)"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Coefficients"
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
                
                st.sidebar.success(f"{dest_type.replace('_', ' ').title()} coefficients updated successfully!")
                return True
            else:
                st.sidebar.error("All coefficients must be between 0 and 1.")
                
        except ValueError:
            st.sidebar.error("Please enter valid numeric values for all coefficients.")
    
    return False


def render_hotel_factor_form(dest_type, current_factor_weights):
    """Render factor weight form for hotels (6 factors)"""
    
    # Hotel-specific weights (6 factors: includes agoda/google)
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
        f"Agoda Score Coefficient:",
        value=str(current_factor_weights[dest_type]["agoda_score_weight"]),
        help="Hotel's individual Agoda review score coefficient (0-1)"
    )

    google_score_weight = st.text_input(
        f"Google Score Coefficient:",
        value=str(current_factor_weights[dest_type]["google_score_weight"]),
        help="Hotel's individual Google review score coefficient (0-1)"
    )

    expenditure_score_weight = st.text_input(
        f"Expenditure Score Coefficient:",
        value=str(current_factor_weights[dest_type]["expenditure_score_weight"]),
        help="Inherits the outbound tourism expenditure score from the hotel's country"
    )

    departure_score_weight = st.text_input(
        f"Departure Score Coefficient:",
        value=str(current_factor_weights[dest_type]["departure_score_weight"]),
        help="Inherits the outbound tourism departure score from the hotel's country"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Coefficients"
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
                
                st.sidebar.success(f"{dest_type.replace('_', ' ').title()} coefficients updated successfully!")
                return True
            else:
                st.sidebar.error("All coefficients must be between 0 and 1.")
                
        except ValueError:
            st.sidebar.error("Please enter valid numeric values for all coefficients.")
    
    return False


def render_search_results(fts_results, current_factor_weights):
    """
    Render search results with in-memory score calculation using coefficient-based scoring system.
    Takes raw FTS results and current weights, calculates scores in Python.
    """
    if not fts_results:
        st.write("No matching destinations found.")
        return

    # Calculate scores in memory using current factor weights (coefficient-based scoring system)
    scored_results = calculate_scores_in_memory(fts_results, current_factor_weights)
    
    if not scored_results:
        st.write("No matching destinations found.")
        return

    # Create main results dataframe (simplified without category weight info)
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
            "Final Score",  # This is now the simple coefficient-based score
            "Coefficient: Hotel Count",
            "Coefficient: Country Hotel Count",
            "Coefficient: Agoda Score",
            "Coefficient: Google Score",
            "Coefficient: Expenditure Score",
            "Coefficient: Departure Score",
            "Country Total Hotels",
            "Base Score",           # Same as final score now
            "Category Weight",      # Set to 0 (legacy compatibility)
            "Category Multiplier"   # Set to 1 (legacy compatibility)
        ],
    )

    # Create a display name column that formats differently based on type
    df["Display Name"] = df.apply(
        lambda row: (
            f"{row['Name']}, {row['City']}"
            if row["Type"] in ["area", "small_area"]
            else row["Name"]
        ),
        axis=1,
    )

    st.write(f"Found {len(scored_results)} matching destinations:")

    # Show results with simplified columns
    display_df = df[
        [
            "Display Name",
            "Type",
            "Area",
            "City",
            "Country",
            "Final Score"
        ]
    ]
    
    st.dataframe(
        display_df,
        column_config={
            "Display Name": st.column_config.TextColumn(width="medium"),
            "Final Score": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    # Show current weight configuration
    with st.expander("View Current Weight Configuration"):
        
        # === SMALL CITY THRESHOLD SECTION ===
        current_threshold = load_small_city_threshold()
        st.subheader("🏘️ Small City/Area Threshold")
        st.markdown(f"**Current Threshold:** {current_threshold} hotels")
        st.markdown("Cities and areas with this many hotels or fewer are classified as 'small'")
        
        st.divider()
        
        # === FACTOR WEIGHTS DISPLAY ===
        st.subheader("⚙️ Current Factor Coefficients")
        
        factor_weights_display = []
        
        for dest_type, weights in current_factor_weights.items():
            display_name = dest_type.replace('_', ' ').title()
            
            if dest_type == 'hotel':
                # Hotels have 6 factors
                factor_weights_display.append({
                    "Type": display_name,
                    "Hotel Count": f"{weights['hotel_count_weight']:.3f}",
                    "Country Hotel Count": f"{weights['country_hotel_count_weight']:.3f}",
                    "Agoda Score": f"{weights['agoda_score_weight']:.3f}",
                    "Google Score": f"{weights['google_score_weight']:.3f}",
                    "Expenditure Score": f"{weights['expenditure_score_weight']:.3f}",
                    "Departure Score": f"{weights['departure_score_weight']:.3f}",
                    "Factor Count": "6"
                })
            else:
                # Locations have 4 factors (including small_area)
                factor_weights_display.append({
                    "Type": display_name,
                    "Hotel Count": f"{weights['hotel_count_weight']:.3f}",
                    "Country Hotel Count": f"{weights['country_hotel_count_weight']:.3f}",
                    "Agoda Score": "N/A",  # Not applicable for locations
                    "Google Score": "N/A",  # Not applicable for locations
                    "Expenditure Score": f"{weights['expenditure_score_weight']:.3f}",
                    "Departure Score": f"{weights['departure_score_weight']:.3f}",
                    "Factor Count": "4"
                })
        
        factor_df = pd.DataFrame(factor_weights_display)
        st.dataframe(factor_df, hide_index=True)
        
        st.divider()
        
        # === SCORING EXPLANATION ===
        st.subheader("📊 Scoring System")
        st.markdown("""
        **Coefficient-Based Formula:**
        
        `Final Score = Σ(factorᵢ × coeffᵢ) / N`
        
        **Factor Structure:**
        - **Cities, Small Cities, Areas & Small Areas**: 4 factors (divide by 4)
        - **Hotels**: 6 factors (divide by 6)
        
        **Strategic Control:**
        - **High coefficients**: Destination type scores higher
        - **Low coefficients**: Destination type scores lower
        - **Example**: Set hotel coefficients to 0.01 to suppress hotels, city coefficients to 1.0 to boost cities
        
        **Dynamic Classification:** Cities and areas are automatically classified as "Small" if their hotel count ≤ threshold.
        
        *Coefficient values directly control competitive balance between all 5 destination types!*
        """)

    # Show scoring breakdown for top 10 results
    with st.expander("View Detailed Scoring for Top 10 Results"):
        top_10 = df.head(10)
        
        for i, (_, row) in enumerate(top_10.iterrows(), 1):
            display_type = row['Type'].replace('_', ' ').title()
            st.markdown(f"**#{i}: {row['Display Name']} ({display_type})**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Final Score", f"{row['Final Score']:.4f}")
            
            with col2:
                # Calculate the sum used in formula
                if row['Type'] == 'hotel':
                    weighted_sum = (
                        row['Normalized: Hotel Count'] * row['Coefficient: Hotel Count'] +
                        row['Normalized: Country Hotel Count'] * row['Coefficient: Country Hotel Count'] +
                        row['Normalized: Agoda Score'] * row['Coefficient: Agoda Score'] +
                        row['Normalized: Google Score'] * row['Coefficient: Google Score'] +
                        row['Normalized: Expenditure Score'] * row['Coefficient: Expenditure Score'] +
                        row['Normalized: Departure Score'] * row['Coefficient: Departure Score']
                    )
                    factor_count = 6
                else:
                    weighted_sum = (
                        row['Normalized: Hotel Count'] * row['Coefficient: Hotel Count'] +
                        row['Normalized: Country Hotel Count'] * row['Coefficient: Country Hotel Count'] +
                        row['Normalized: Expenditure Score'] * row['Coefficient: Expenditure Score'] +
                        row['Normalized: Departure Score'] * row['Coefficient: Departure Score']
                    )
                    factor_count = 4
                    
                st.metric("Calculation", f"{weighted_sum:.2f} ÷ {factor_count}")
            
            # Show factor breakdown based on type
            if row['Type'] == 'hotel':
                factors = [
                    ("Global Hotel Count", row['Normalized: Hotel Count'], row['Coefficient: Hotel Count']),
                    ("Country Hotel Count", row['Normalized: Country Hotel Count'], row['Coefficient: Country Hotel Count']),
                    ("Agoda Score", row['Normalized: Agoda Score'], row['Coefficient: Agoda Score']),
                    ("Google Score", row['Normalized: Google Score'], row['Coefficient: Google Score']),
                    ("Expenditure Score", row['Normalized: Expenditure Score'], row['Coefficient: Expenditure Score']),
                    ("Departure Score", row['Normalized: Departure Score'], row['Coefficient: Departure Score'])
                ]
            else:
                # Cities, areas, small_cities, small_areas - only show 4 relevant factors
                factors = [
                    ("Global Hotel Count", row['Normalized: Hotel Count'], row['Coefficient: Hotel Count']),
                    ("Country Hotel Count", row['Normalized: Country Hotel Count'], row['Coefficient: Country Hotel Count']),
                    ("Expenditure Score", row['Normalized: Expenditure Score'], row['Coefficient: Expenditure Score']),
                    ("Departure Score", row['Normalized: Departure Score'], row['Coefficient: Departure Score'])
                ]
            
            factor_breakdown = []
            for factor_name, normalized_value, coefficient in factors:
                contribution = normalized_value * coefficient
                factor_breakdown.append({
                    "Factor": factor_name,
                    "Normalized Value": f"{normalized_value:.0f}",
                    "Coefficient": f"{coefficient:.4f}",
                    "Contribution": f"{contribution:.2f}"
                })
            
            if factor_breakdown:
                factor_df = pd.DataFrame(factor_breakdown)
                st.dataframe(factor_df, hide_index=True)
            
            st.markdown("---")