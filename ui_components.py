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
        *Set the hotel count threshold that determines classification:*
        - Cities with **≤ threshold hotels** = Small City
        - Cities with **> threshold hotels** = Regular City
        - Areas in **small cities** = Small Area (regardless of area size)
        - Areas in **regular cities** = Regular Area (regardless of area size)
        """
    )

    with st.sidebar.form("threshold_form"):
        current_threshold = load_small_city_threshold()
        threshold_input = st.text_input(
            "Hotel Count Threshold:", 
            value=str(current_threshold),
            help="Cities with this many hotels or fewer will be classified as 'small'. Areas inherit this classification from their parent city."
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
    hotel_count_weight = st.slider(
        f"Global Hotel Normalization:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["hotel_count_weight"]),
        step=0.01,
        help="Coefficient for global hotel count normalization (0-1)"
    )

    country_hotel_count_weight = st.slider(
        f"Country Hotel Normalization:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["country_hotel_count_weight"]),
        step=0.01,
        help="Coefficient for country-relative hotel count normalization (0-1)"
    )

    expenditure_score_weight = st.slider(
        f"Expenditure Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["expenditure_score_weight"]),
        step=0.01,
        help="Coefficient for outbound tourism expenditure score (0-1)"
    )

    departure_score_weight = st.slider(
        f"Departure Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["departure_score_weight"]),
        step=0.01,
        help="Coefficient for outbound tourism departure score (0-1)"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Coefficients"
    )

    if submit_weights:
        # No need for validation since sliders enforce range automatically
        # Update in-memory weights - NO DATABASE CALL
        current_factor_weights[dest_type].update({
            "hotel_count_weight": hotel_count_weight,
            "country_hotel_count_weight": country_hotel_count_weight,
            "expenditure_score_weight": expenditure_score_weight,
            "departure_score_weight": departure_score_weight
        })
        
        st.sidebar.success(f"{dest_type.replace('_', ' ').title()} coefficients updated successfully!")
        return True
    
    return False


def render_hotel_factor_form(dest_type, current_factor_weights):
    """
    Render factor weight form for hotels (6 factors).
    Uses new weight names: city_score_weight and area_score_weight.
    """
    
    # Hotel-specific weights (6 factors: Updated labels and variable names)
    city_score_weight = st.slider(
        f"City Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["city_score_weight"]),
        step=0.01,
        help="Coefficient for the hotel's parent city calculated score (0-1)"
    )

    area_score_weight = st.slider(
        f"Area Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["area_score_weight"]),
        step=0.01,
        help="Coefficient for the hotel's parent area calculated score (0-1)"
    )

    agoda_score_weight = st.slider(
        f"Agoda Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["agoda_score_weight"]),
        step=0.01,
        help="Hotel's individual Agoda review score coefficient (0-1)"
    )

    google_score_weight = st.slider(
        f"Google Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["google_score_weight"]),
        step=0.01,
        help="Hotel's individual Google review score coefficient (0-1)"
    )

    expenditure_score_weight = st.slider(
        f"Expenditure Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["expenditure_score_weight"]),
        step=0.01,
        help="Inherits the outbound tourism expenditure score from the hotel's country"
    )

    departure_score_weight = st.slider(
        f"Departure Score Coefficient:",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["departure_score_weight"]),
        step=0.01,
        help="Inherits the outbound tourism departure score from the hotel's country"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Coefficients"
    )

    if submit_weights:
        # No need for validation since sliders enforce range automatically
        # Update in-memory weights - NO DATABASE CALL
        # Use new weight names
        current_factor_weights[dest_type].update({
            "city_score_weight": city_score_weight,
            "area_score_weight": area_score_weight,
            "agoda_score_weight": agoda_score_weight,
            "google_score_weight": google_score_weight,
            "expenditure_score_weight": expenditure_score_weight,
            "departure_score_weight": departure_score_weight
        })
        
        st.sidebar.success(f"{dest_type.replace('_', ' ').title()} coefficients updated successfully!")
        return True
    
    return False


def render_search_results(fts_results, current_factor_weights):
    """
    SIMPLIFIED: Render search results that come pre-scored from the enhanced search logic.
    No longer needs to calculate scores since they come with final_score already computed.
    Now mainly focuses on formatting and displaying the pre-calculated results.
    """
    if not fts_results:
        st.write("No matching destinations found.")
        return

    # Check if results are already in tuple format (legacy) or dict format (new)
    if fts_results and isinstance(fts_results[0], dict):
        # New format: results come as dictionaries with pre-calculated scores
        scored_results = convert_dict_results_to_tuple_format(fts_results, current_factor_weights)
    else:
        # Legacy format: results are already tuples, use as-is
        scored_results = fts_results
    
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
            "Final Score",  # This is the pre-calculated score from search
            "Coefficient: Factor 1",      # hotel_count_weight OR city_score_weight
            "Coefficient: Factor 2",      # country_hotel_count_weight OR area_score_weight
            "Coefficient: Agoda Score",
            "Coefficient: Google Score",
            "Coefficient: Expenditure Score",
            "Coefficient: Departure Score",
            "Country Total Hotels",
            "Base Score",           # Same as final score
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

    # Add Hotel Number column - show raw hotel count for locations, blank for hotels
    df["Hotel Number"] = df.apply(
        lambda row: (
            "" if row["Type"] == "hotel" 
            else str(int(row["Hotel Count"]))
        ),
        axis=1,
    )

    # Add Calculation column - show detailed scoring breakdown
    # WARNING: DO NOT CHANGE THE CALCULATION FORMAT! Must remain: coeff(factor) + coeff(factor) => sum / count => result
    def create_calculation_string(row):
        dest_type = row["Type"]
        
        if dest_type == "hotel":
            # Hotels: 6 factors
            factors = [
                (row["Coefficient: Factor 1"], row["Normalized: Hotel Count"]),
                (row["Coefficient: Factor 2"], row["Normalized: Country Hotel Count"]),
                (row["Coefficient: Agoda Score"], row["Normalized: Agoda Score"]),
                (row["Coefficient: Google Score"], row["Normalized: Google Score"]),
                (row["Coefficient: Expenditure Score"], row["Normalized: Expenditure Score"]),
                (row["Coefficient: Departure Score"], row["Normalized: Departure Score"])
            ]
            factor_count = 6
        else:
            # Locations: 4 factors (city, small_city, area, small_area)
            factors = [
                (row["Coefficient: Factor 1"], row["Normalized: Hotel Count"]),
                (row["Coefficient: Factor 2"], row["Normalized: Country Hotel Count"]),
                (row["Coefficient: Expenditure Score"], row["Normalized: Expenditure Score"]),
                (row["Coefficient: Departure Score"], row["Normalized: Departure Score"])
            ]
            factor_count = 4
        
        # Create calculation parts
        calc_parts = []
        total_sum = 0
        
        for coeff, factor in factors:
            calc_parts.append(f"{coeff:.2f}({int(factor)})")
            total_sum += coeff * factor
        
        # Format: coeff(factor) + coeff(factor) + ... => sum / count => final_score
        calculation_str = " + ".join(calc_parts)
        final_score = total_sum / factor_count
        
        return f"{calculation_str} => {total_sum:.2f} / {factor_count} => {final_score:.2f}"
    
    df["Calculation"] = df.apply(create_calculation_string, axis=1)

    st.write(f"Found {len(scored_results)} matching destinations:")

    # Show results with enhanced calculation display
    display_df = df[
        [
            "Display Name",
            "Type",
            "Area",
            "City",
            "Country",
            "Final Score",
            "Hotel Number",
            "Calculation"
        ]
    ]
    
    st.dataframe(
        display_df,
        column_config={
            "Display Name": st.column_config.TextColumn(width="medium"),
            "Final Score": st.column_config.NumberColumn(format="%.4f"),
            "Hotel Number": st.column_config.TextColumn(width="small"),
            "Calculation": st.column_config.TextColumn(width="extra_large"),
        },
    )


def convert_dict_results_to_tuple_format(dict_results, current_factor_weights):
    """
    Convert new dictionary format results to the legacy tuple format expected by the UI.
    This ensures compatibility with existing display code.
    """
    # Load threshold for classification
    small_city_threshold = load_small_city_threshold()
    
    converted_results = []
    
    for result in dict_results:
        dest_type = result['type']
        
        # Dynamic classification for display
        if dest_type == 'city' and result.get('hotel_count', 0) <= small_city_threshold:
            dest_type = 'small_city'
        elif dest_type == 'area' and result.get('parent_city_hotel_count', 0) <= small_city_threshold:
            dest_type = 'small_area'
        
        # Get final score (should be pre-calculated)
        final_score = result.get('final_score', 0)
        
        # Prepare weights for UI display (6-position array format)
        if dest_type == 'hotel':
            hotel_weights = current_factor_weights['hotel']
            padded_weights = [
                hotel_weights['city_score_weight'],
                hotel_weights['area_score_weight'],
                hotel_weights['agoda_score_weight'],
                hotel_weights['google_score_weight'],
                hotel_weights['expenditure_score_weight'],
                hotel_weights['departure_score_weight']
            ]
            # For hotels, show calculated city/area scores in the normalized fields
            hotel_count_norm = result.get('city_score', 0)  # Show city score
            country_hotel_norm = result.get('area_score', 0)  # Show area score
        else:
            # Location types - map 4 weights to 6-position array
            location_weights = current_factor_weights[dest_type]
            padded_weights = [
                location_weights['hotel_count_weight'],
                location_weights['country_hotel_count_weight'],
                0,  # agoda_score_weight (not applicable)
                0,  # google_score_weight (not applicable)
                location_weights['expenditure_score_weight'],
                location_weights['departure_score_weight']
            ]
            # For locations, show actual normalized values
            hotel_count_norm = result.get('hotel_count_normalized', 0)
            country_hotel_norm = result.get('country_hotel_count_normalized', 0)
        
        # Create result tuple in the format expected by UI
        tuple_result = (
            dest_type,
            result['name'],
            result['country_name'],
            result['city_name'],
            result.get('area_name', ''),
            result.get('hotel_count', 0),
            hotel_count_norm,  # This will show city_score for hotels, hotel_count_normalized for locations
            country_hotel_norm,  # This will show area_score for hotels, country_hotel_count_normalized for locations
            result.get('agoda_score_normalized', 0),
            result.get('google_score_normalized', 0),
            result.get('expenditure_score_normalized', 0),
            result.get('departure_score_normalized', 0),
            final_score,  # Pre-calculated final score
            padded_weights[0],  # Weight 1
            padded_weights[1],  # Weight 2
            padded_weights[2],  # Weight 3 (agoda)
            padded_weights[3],  # Weight 4 (google)
            padded_weights[4],  # Weight 5 (expenditure)
            padded_weights[5],  # Weight 6 (departure)
            result.get('country_total_hotels', 0),
            final_score,  # Base score same as final score
            0,  # Category weight (legacy, set to 0)
            1   # Category multiplier (legacy, set to 1)
        )
        
        converted_results.append(tuple_result)
    
    return converted_results