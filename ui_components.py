import streamlit as st
import pandas as pd
from database import get_connection
from scoring import update_weights


def render_sidebar():
    """Render the sidebar with weight configuration forms"""
    st.sidebar.header("Factor Weight Configuration")

    # Get current weights from factor_weights table
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight, expenditure_score_weight, departure_score_weight FROM factor_weights"
    )
    weights_data = cursor.fetchall()
    conn.close()

    # Create dictionary of current weights by destination type
    current_weights = {}
    for row in weights_data:
        dest_type = row[0]
        current_weights[dest_type] = {
            "hotel_count_weight": row[1],
            "country_hotel_count_weight": row[2],
            "agoda_score_weight": row[3] if len(row) > 3 else 0,
            "google_score_weight": row[4] if len(row) > 4 else 0,
            "expenditure_score_weight": row[5] if len(row) > 5 else 0,
            "departure_score_weight": row[6] if len(row) > 6 else 0,
        }

    # Default values if no weights found
    if "city" not in current_weights:
        current_weights["city"] = {
            "hotel_count_weight": 0.4,
            "country_hotel_count_weight": 0.2,
            "agoda_score_weight": 0,
            "google_score_weight": 0,
            "expenditure_score_weight": 0.25,
            "departure_score_weight": 0.15,
        }
    if "area" not in current_weights:
        current_weights["area"] = {
            "hotel_count_weight": 0.3,
            "country_hotel_count_weight": 0.2,
            "agoda_score_weight": 0,
            "google_score_weight": 0,
            "expenditure_score_weight": 0.3,
            "departure_score_weight": 0.2,
        }
    if "hotel" not in current_weights:
        current_weights["hotel"] = {
            "hotel_count_weight": 0,
            "country_hotel_count_weight": 0,
            "agoda_score_weight": 0.3,
            "google_score_weight": 0.2,
            "expenditure_score_weight": 0.3,
            "departure_score_weight": 0.2,
        }

    # Weight adjustment forms - one for each destination type
    st.sidebar.markdown(
        """
    Customize the importance of each factor for optimal search results:
    - **Cities & Areas**: Hotel count normalization + outbound tourism factors
    - **Hotels**: Review scores + outbound tourism factors
    
    *Adjust weights below to fine-tune your search experience.*
    """
    )

    dest_types = ["city", "area", "hotel"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (Agoda, Google, Expenditure, Departure scores)
                agoda_score_weight = st.slider(
                    f"Agoda Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["agoda_score_weight"]),
                    0.05,
                )

                google_score_weight = st.slider(
                    f"Google Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["google_score_weight"]),
                    0.05,
                )

                expenditure_score_weight = st.slider(
                    f"Expenditure Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["expenditure_score_weight"]),
                    0.05,
                )

                departure_score_weight = st.slider(
                    f"Departure Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["departure_score_weight"]),
                    0.05,
                )

                # Show weight sum for validation
                weight_sum = agoda_score_weight + google_score_weight + expenditure_score_weight + departure_score_weight
                if weight_sum > 0:
                    st.write(f"Weight Sum: {weight_sum:.2f}")

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
                )

                if submit_weights:
                    if update_weights(
                        dest_type, 
                        agoda_score_weight=agoda_score_weight, 
                        google_score_weight=google_score_weight,
                        expenditure_score_weight=expenditure_score_weight,
                        departure_score_weight=departure_score_weight
                    ):
                        st.sidebar.success(
                            f"{dest_type.title()} weights updated successfully!"
                        )
                    else:
                        st.sidebar.error(
                            f"Failed to update {dest_type.title()} weights. Make sure values are between 0 and 1."
                        )
            else:
                # City/Area weights (hotel count normalization + outbound scores)
                hotel_count_weight = st.slider(
                    f"Global Hotel Normalization:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["hotel_count_weight"]),
                    0.05,
                )

                country_hotel_count_weight = st.slider(
                    f"Country Hotel Normalization:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["country_hotel_count_weight"]),
                    0.05,
                )

                expenditure_score_weight = st.slider(
                    f"Expenditure Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["expenditure_score_weight"]),
                    0.05,
                )

                departure_score_weight = st.slider(
                    f"Departure Score Weight:",
                    0.0,
                    1.0,
                    float(current_weights[dest_type]["departure_score_weight"]),
                    0.05,
                )

                # Show weight sum for validation
                weight_sum = hotel_count_weight + country_hotel_count_weight + expenditure_score_weight + departure_score_weight
                if weight_sum > 0:
                    st.write(f"Weight Sum: {weight_sum:.2f}")

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
                )

                if submit_weights:
                    if update_weights(
                        dest_type, 
                        hotel_count_weight=hotel_count_weight, 
                        country_hotel_count_weight=country_hotel_count_weight,
                        expenditure_score_weight=expenditure_score_weight,
                        departure_score_weight=departure_score_weight
                    ):
                        st.sidebar.success(
                            f"{dest_type.title()} weights updated successfully!"
                        )
                    else:
                        st.sidebar.error(
                            f"Failed to update {dest_type.title()} weights. Make sure values are between 0 and 1."
                        )


def render_search_results(results):
    """Render search results with tables and explanations"""
    if results:
        # Create main results dataframe
        df = pd.DataFrame(
            results,
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

        st.write(f"Found {len(results)} matching destinations:")

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
                "Total Score": st.column_config.NumberColumn(format="%.2f"),
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
                    weights_display.append({
                        "Type": row["Type"],
                        "Agoda Score": f"{row['Weight: Agoda Score']:.2f}",
                        "Google Score": f"{row['Weight: Google Score']:.2f}",
                        "Expenditure Score": f"{row['Weight: Expenditure Score']:.2f}",
                        "Departure Score": f"{row['Weight: Departure Score']:.2f}"
                    })
                else:
                    weights_display.append({
                        "Type": row["Type"],
                        "Global Hotel Count": f"{row['Weight: Hotel Count']:.2f}",
                        "Country Hotel Count": f"{row['Weight: Country Hotel Count']:.2f}",
                        "Expenditure Score": f"{row['Weight: Expenditure Score']:.2f}",
                        "Departure Score": f"{row['Weight: Departure Score']:.2f}"
                    })
            
            weights_display_df = pd.DataFrame(weights_display)
            st.dataframe(weights_display_df, hide_index=True)

    else:
        st.write("No matching destinations found.")