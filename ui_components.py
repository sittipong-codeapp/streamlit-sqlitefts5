import streamlit as st
import pandas as pd
from scoring import calculate_scores_in_memory, load_small_city_threshold, save_small_city_threshold
from score_calculator import is_small_country


def render_sidebar(current_factor_weights):
    """Render the sidebar with threshold and factor weight configuration forms"""
    st.sidebar.header("Weight Configuration")

    # Track if weights were updated
    factor_weights_updated = False
    threshold_updated = False

    # === SMALL CITY THRESHOLD SECTION (TOP PRIORITY) ===
    # st.sidebar.subheader("🏘️ Small City Threshold")


    # with st.sidebar.form("threshold_form"):
    #     current_threshold = load_small_city_threshold()
    #     threshold_input = st.text_input(
    #         "Hotel Count Threshold:", 
    #         value=str(current_threshold),
    #         help="Cities with this many hotels or fewer will be classified as 'small'. Areas inherit this classification from their parent city."
    #     )
        
    #     submit_threshold = st.form_submit_button("Update Threshold")
        
    #     if submit_threshold:
    #         try:
    #             threshold_value = int(threshold_input)
    #             if threshold_value >= 0:
    #                 save_small_city_threshold(threshold_value)
    #                 st.sidebar.success(f"Threshold updated to {threshold_value} hotels!")
    #                 threshold_updated = True
    #                 # Clear cache when threshold changes
    #                 st.session_state.app_config['last_search_results'] = None
    #                 st.session_state.app_config['threshold_changed'] = True
    #             else:
    #                 st.sidebar.error("Threshold must be 0 or greater.")
    #         except ValueError:
    #             st.sidebar.error("Please enter a valid integer for the threshold.")

    # st.sidebar.divider()

    # === FACTOR WEIGHTS SECTION ===
    st.sidebar.subheader("⚙️ Factor Weight Configuration")
    st.sidebar.markdown(
        """
        *ปรับ slider เพื่อให้น้ำหนักปัจจัยต่างๆ*
        """
    )

    dest_types = ["city", "small_city", "area", "small_area", "hotel"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.replace('_', ' ').title()} Scoring Factors")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (6 factors)
                factor_weights_updated = render_hotel_factor_form(dest_type, current_factor_weights)
            else:
                # Location weights (4 factors)
                factor_weights_updated = render_location_factor_form(dest_type, current_factor_weights)
                
            if factor_weights_updated:
                # FIXED: Set flag in correct location and clear cache immediately
                st.session_state.app_config['weights_changed'] = True
                st.session_state.app_config['last_search_results'] = None

    return factor_weights_updated


def render_location_factor_form(dest_type, current_factor_weights):
    """Render factor weight form for cities, areas, small_cities, small_areas (4 factors only)"""
    
    # Location weights (4 factors: no agoda/google inputs)
    hotel_count_weight = st.slider(
        f"จำนวนโรงแรมเทียบกับทั้งโลก (Hotel Count / World)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["hotel_count_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for global hotel count normalization (0-1)"
    )

    country_hotel_count_weight = st.slider(
        f"จำนวนโรงแรมเทียบในประเทศ (Hotel Count / Country)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["country_hotel_count_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for country-relative hotel count normalization (0-1)"
    )

    expenditure_score_weight = st.slider(
        f"ค่าใช้จ่าย (Expenditure)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["expenditure_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for outbound tourism expenditure score (0-1)"
    )

    departure_score_weight = st.slider(
        f"คนเดินทางขาออก (Departure)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["departure_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for outbound tourism departure score (0-1)"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Scoring Factors"
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
        f"คะแนนของเมือง (City Score)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["city_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for the hotel's parent city calculated score (0-1)"
    )

    area_score_weight = st.slider(
        f"คะแนนของพื้นที่ (Area Score)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["area_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Coefficient for the hotel's parent area calculated score (0-1)"
    )

    agoda_score_weight = st.slider(
        f"คะแนน ranking จาก Agoda (Agoda Score)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["agoda_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Hotel's individual Agoda review score coefficient (0-1)"
    )

    google_score_weight = st.slider(
        f"คะแนน ranking จาก Google Trends (Google Score)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["google_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Hotel's individual Google review score coefficient (0-1)"
    )

    expenditure_score_weight = st.slider(
        f"ค่าใช้จ่าย (Expenditure)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["expenditure_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Inherits the outbound tourism expenditure score from the hotel's country"
    )

    departure_score_weight = st.slider(
        f"คนเดินทางขาออก (Departure)",
        min_value=0.0,
        max_value=1.0,
        value=float(current_factor_weights[dest_type]["departure_score_weight"]),
        step=0.1,
        format="%.1f",
        help="Inherits the outbound tourism departure score from the hotel's country"
    )

    submit_weights = st.form_submit_button(
        f"Update {dest_type.replace('_', ' ').title()} Scoring Factors"
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
    FIXED: Render search results that come pre-scored from the enhanced search logic.
    Final Score column now matches exactly what's shown in the calculation.
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

    # Create main results dataframe with DYNAMIC COLUMN NAMES based on content
    df = pd.DataFrame(
        scored_results,
        columns=[
            "Type",
            "Name",
            "Country",
            "City",
            "Area",
            "Hotel Count",
            "Factor 1 Value",  # CHANGED: This will be hotel_count_normalized OR city_score
            "Factor 2 Value",  # CHANGED: This will be country_hotel_count_normalized OR area_score
            "Normalized: Agoda Score",
            "Normalized: Google Score",
            "Normalized: Expenditure Score",
            "Normalized: Departure Score",
            "Final Score",
            "Coefficient: Factor 1",
            "Coefficient: Factor 2",
            "Coefficient: Agoda Score",
            "Coefficient: Google Score",
            "Coefficient: Expenditure Score",
            "Coefficient: Departure Score",
            "Country Total Hotels",
            "Base Score",
            "Category Weight",
            "Category Multiplier"
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

    # FIXED: Add Calculation column and recalculate Final Score to match calculation
    def create_calculation_string_and_update_final_score(row):
        dest_type = row["Type"]
        
        if dest_type == "hotel":
            # Hotels: 6 factors with correct names
            factors_info = [
                (row["Coefficient: Factor 1"], row["Factor 1 Value"], "City Score"),
                (row["Coefficient: Factor 2"], row["Factor 2 Value"], "Area Score"),
                (row["Coefficient: Agoda Score"], row["Normalized: Agoda Score"], "Agoda"),
                (row["Coefficient: Google Score"], row["Normalized: Google Score"], "Google"),
                (row["Coefficient: Expenditure Score"], row["Normalized: Expenditure Score"], "Expenditure"),
                (row["Coefficient: Departure Score"], row["Normalized: Departure Score"], "Departure")
            ]
            factor_count = 6
        else:
            # Locations: 4 factors with correct names
            factors_info = [
                (row["Coefficient: Factor 1"], row["Factor 1 Value"], "Hotel Count"),
                (row["Coefficient: Factor 2"], row["Factor 2 Value"], "Country Hotel Count"),
                (row["Coefficient: Expenditure Score"], row["Normalized: Expenditure Score"], "Expenditure"),
                (row["Coefficient: Departure Score"], row["Normalized: Departure Score"], "Departure")
            ]
            factor_count = 4
        
        # Create calculation parts with proper names
        calc_parts = []
        calculated_sum = 0
        
        for coeff, factor_value, factor_name in factors_info:
            calc_parts.append(f"{coeff:.1f}({int(factor_value)})")
            calculated_sum += coeff * factor_value
        
        # Calculate the final score that matches the calculation display
        calculated_final_score = calculated_sum / factor_count
        
        # Create calculation string
        calculation_str = " + ".join(calc_parts)
        # calculation_str += f" => {calculated_sum:.2f}/{factor_count} => {calculated_final_score:.4f}"
        
        return calculation_str, calculated_final_score
    
    # Apply the function and update both Calculation and Final Score columns
    calculation_results = df.apply(create_calculation_string_and_update_final_score, axis=1, result_type='expand')
    df["Calculation"] = calculation_results[0]
    df["Final Score"] = calculation_results[1]  # Update Final Score to match calculation

    st.write(f"Found {len(scored_results)} matching destinations:")

    # Show results with enhanced calculation display
    display_df = df[
        [
            "Display Name",
            "Type",
            "Country",
            "Final Score",
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
    FIXED: Convert new dictionary format results to the legacy tuple format with proper data mapping.
    """
    # Load threshold for classification
    small_city_threshold = load_small_city_threshold()
    
    converted_results = []
    
    for result in dict_results:
        dest_type = result['type']
        
        # Dynamic classification for display based on country
        country_id = result.get('country_id')
        if dest_type == 'city' and is_small_country(country_id, small_city_threshold):
            dest_type = 'small_city'
        elif dest_type == 'area' and is_small_country(country_id, small_city_threshold):
            dest_type = 'small_area'
        
        # Get final score (should be pre-calculated)
        final_score = result.get('final_score', 0)
        
        # FIXED: Prepare weights and factor values correctly based on type
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
            # For hotels: Factor 1 = city_score, Factor 2 = area_score
            factor1_value = result.get('city_score', 0)
            factor2_value = result.get('area_score', 0)
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
            # For locations: Factor 1 = hotel_count_normalized, Factor 2 = country_hotel_count_normalized
            factor1_value = result.get('hotel_count_normalized', 0)
            factor2_value = result.get('country_hotel_count_normalized', 0)
        
        # Create result tuple in the format expected by UI
        tuple_result = (
            dest_type,
            result['name'],
            result['country_name'],
            result['city_name'],
            result.get('area_name', ''),
            result.get('hotel_count', 0),
            factor1_value,  # FIXED: Properly mapped factor 1 value
            factor2_value,  # FIXED: Properly mapped factor 2 value
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