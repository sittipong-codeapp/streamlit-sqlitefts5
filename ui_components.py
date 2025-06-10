import streamlit as st
import pandas as pd
from scoring import calculate_scores_in_memory


def render_sidebar(current_weights):
    """Render the sidebar with weight configuration forms - now updates in-memory weights"""
    st.sidebar.header("Factor Weight Configuration")

    # Weight adjustment forms - one for each destination type
    st.sidebar.markdown(
        """
    Customize the importance of each factor for optimal search results:
    - **Cities & Areas**: Hotel count normalization + outbound tourism factors
    - **Hotels**: City hotel normalization + individual review scores + outbound tourism factors
    
    *Adjust weights below to fine-tune your search experience.*
    """
    )

    dest_types = ["city", "area", "hotel"]
    weights_updated = False

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (6 factors: city normalization + hotel review scores + outbound scores)
                hotel_count_weight = st.text_input(
                    f"Global Hotel Normalization:",
                    value=str(current_weights[dest_type]["hotel_count_weight"]),
                    help="Inherits the global hotel count normalization from the hotel's city"
                )

                country_hotel_count_weight = st.text_input(
                    f"Country Hotel Normalization:",
                    value=str(current_weights[dest_type]["country_hotel_count_weight"]),
                    help="Inherits the country hotel count normalization from the hotel's city"
                )

                agoda_score_weight = st.text_input(
                    f"Agoda Score Weight:",
                    value=str(current_weights[dest_type]["agoda_score_weight"]),
                    help="Hotel's individual Agoda review score"
                )

                google_score_weight = st.text_input(
                    f"Google Score Weight:",
                    value=str(current_weights[dest_type]["google_score_weight"]),
                    help="Hotel's individual Google review score"
                )

                expenditure_score_weight = st.text_input(
                    f"Expenditure Score Weight:",
                    value=str(current_weights[dest_type]["expenditure_score_weight"]),
                    help="Inherits the outbound tourism expenditure score from the hotel's country"
                )

                departure_score_weight = st.text_input(
                    f"Departure Score Weight:",
                    value=str(current_weights[dest_type]["departure_score_weight"]),
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
                    st.write(f"Weight Sum: {weight_sum:.4f}")
                except ValueError:
                    st.write("Invalid weight values entered")
                    weight_sum = 0

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
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
                            current_weights[dest_type].update({
                                "hotel_count_weight": hotel_count_weight_float,
                                "country_hotel_count_weight": country_hotel_count_weight_float,
                                "agoda_score_weight": agoda_score_weight_float,
                                "google_score_weight": google_score_weight_float,
                                "expenditure_score_weight": expenditure_score_weight_float,
                                "departure_score_weight": departure_score_weight_float
                            })
                            
                            st.sidebar.success(f"{dest_type.title()} weights updated successfully!")
                            weights_updated = True
                            
                            # Mark that weights have changed for potential auto-recalculation
                            if 'search_results_cache' in st.session_state:
                                st.session_state.weights_changed = True
                        else:
                            st.sidebar.error("All weights must be between 0 and 1.")
                            
                    except ValueError:
                        st.sidebar.error("Please enter valid numeric values for all weights.")

            else:
                # City/Area weights (4 factors: hotel count normalization + outbound scores)
                hotel_count_weight = st.text_input(
                    f"Global Hotel Normalization:",
                    value=str(current_weights[dest_type]["hotel_count_weight"]),
                )

                country_hotel_count_weight = st.text_input(
                    f"Country Hotel Normalization:",
                    value=str(current_weights[dest_type]["country_hotel_count_weight"]),
                )

                expenditure_score_weight = st.text_input(
                    f"Expenditure Score Weight:",
                    value=str(current_weights[dest_type]["expenditure_score_weight"]),
                )

                departure_score_weight = st.text_input(
                    f"Departure Score Weight:",
                    value=str(current_weights[dest_type]["departure_score_weight"]),
                )

                # Convert string inputs to float and show weight sum for validation
                try:
                    weight_sum = (
                        float(hotel_count_weight) + 
                        float(country_hotel_count_weight) + 
                        float(expenditure_score_weight) + 
                        float(departure_score_weight)
                    )
                    st.write(f"Weight Sum: {weight_sum:.4f}")
                except ValueError:
                    st.write("Invalid weight values entered")
                    weight_sum = 0

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
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
                            current_weights[dest_type].update({
                                "hotel_count_weight": hotel_count_weight_float,
                                "country_hotel_count_weight": country_hotel_count_weight_float,
                                "expenditure_score_weight": expenditure_score_weight_float,
                                "departure_score_weight": departure_score_weight_float
                            })
                            
                            st.sidebar.success(f"{dest_type.title()} weights updated successfully!")
                            weights_updated = True
                            
                            # Mark that weights have changed for potential auto-recalculation
                            if 'search_results_cache' in st.session_state:
                                st.session_state.weights_changed = True
                        else:
                            st.sidebar.error("All weights must be between 0 and 1.")
                            
                    except ValueError:
                        st.sidebar.error("Please enter valid numeric values for all weights.")

    return weights_updated


def render_search_results(fts_results, current_weights):
    """
    Render search results with in-memory score calculation.
    Takes raw FTS results and current weights, calculates scores in Python.
    """
    if not fts_results:
        st.write("No matching destinations found.")
        return

    # Calculate scores in memory using current weights
    scored_results = calculate_scores_in_memory(fts_results, current_weights)
    
    if not scored_results:
        st.write("No matching destinations found.")
        return

    # Create main results dataframe (same format as before)
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
            "Total Score",
            "Weight: Hotel Count",
            "Weight: Country Hotel Count",
            "Weight: Agoda Score",
            "Weight: Google Score",
            "Weight: Expenditure Score",
            "Weight: Departure Score",
            "Country Total Hotels",
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

    # Show results with location hierarchy
    display_df = df[
        [
            "Display Name",
            "Type",
            "Country",
            "Total Score",
            "Normalized: Hotel Count",
            "Normalized: Country Hotel Count",
            "Normalized: Agoda Score",
            "Normalized: Google Score",
            "Normalized: Expenditure Score",
            "Normalized: Departure Score",
            "Hotel Count",
            "Country Total Hotels",
        ]
    ]
    st.dataframe(
        display_df,
        column_config={
            "Display Name": st.column_config.TextColumn(width="medium"),
            "Total Score": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    # Show factor weights explanation
    with st.expander("View Factor Weights for Results"):
        # Group by type and show weights with appropriate labels
        weights_df = df[
            ["Type", "Weight: Hotel Count", "Weight: Country Hotel Count", 
             "Weight: Agoda Score", "Weight: Google Score", 
             "Weight: Expenditure Score", "Weight: Departure Score"]
        ].drop_duplicates()
        
        # Add meaningful column names based on type
        weights_display = []
        for _, row in weights_df.iterrows():
            if row["Type"] == "hotel":
                # Hotels show all 6 factors
                weights_display.append({
                    "Type": row["Type"],
                    "Global Hotel Count": f"{row['Weight: Hotel Count']:.4f}",
                    "Country Hotel Count": f"{row['Weight: Country Hotel Count']:.4f}",
                    "Agoda Score": f"{row['Weight: Agoda Score']:.4f}",
                    "Google Score": f"{row['Weight: Google Score']:.4f}",
                    "Expenditure Score": f"{row['Weight: Expenditure Score']:.4f}",
                    "Departure Score": f"{row['Weight: Departure Score']:.4f}"
                })
            else:
                # Cities and areas show 4 factors
                weights_display.append({
                    "Type": row["Type"],
                    "Global Hotel Count": f"{row['Weight: Hotel Count']:.4f}",
                    "Country Hotel Count": f"{row['Weight: Country Hotel Count']:.4f}",
                    "Expenditure Score": f"{row['Weight: Expenditure Score']:.4f}",
                    "Departure Score": f"{row['Weight: Departure Score']:.4f}"
                })
        
        weights_display_df = pd.DataFrame(weights_display)
        st.dataframe(weights_display_df, hide_index=True)