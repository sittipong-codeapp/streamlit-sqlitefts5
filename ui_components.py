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
    UPDATED: Changed hotel_count_weight -> city_score_weight, country_hotel_count_weight -> area_score_weight.
    """
    
    # Hotel-specific weights (6 factors: UPDATED labels and variable names)
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
        # UPDATED: Use new weight names
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
    Render search results with in-memory score calculation using coefficient-based scoring system.
    Takes raw FTS results and current weights, calculates scores in Python.
    UPDATED: Hotel calculation display now shows city/area scores instead of inherited hotel counts.
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
            "Coefficient: Factor 1",      # hotel_count_weight OR city_score_weight
            "Coefficient: Factor 2",      # country_hotel_count_weight OR area_score_weight
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

    # Add Hotel Number column - show raw hotel count for locations, blank for hotels
    df["Hotel Number"] = df.apply(
        lambda row: (
            "" if row["Type"] == "hotel" 
            else str(int(row["Hotel Count"]))
        ),
        axis=1,
    )

    # Add Calculation column - show detailed scoring breakdown
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

    # Show results with new columns
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
            "Calculation": st.column_config.TextColumn(width="large"),
        },
    )