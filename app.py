from database import *
from search_logic import *


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

    # Simplified sidebar header
    st.sidebar.header("Factor Weight Configuration")

    # Get current weights from factor_weights table
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT type, hotel_count_weight, country_hotel_count_weight, agoda_score_weight, google_score_weight FROM factor_weights"
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
        }

    # Default values if no weights found
    if "city" not in current_weights:
        current_weights["city"] = {
            "hotel_count_weight": 0.5,
            "country_hotel_count_weight": 0.5,
            "agoda_score_weight": 0,
            "google_score_weight": 0,
        }
    if "area" not in current_weights:
        current_weights["area"] = {
            "hotel_count_weight": 0.5,
            "country_hotel_count_weight": 0.5,
            "agoda_score_weight": 0,
            "google_score_weight": 0,
        }
    if "hotel" not in current_weights:
        current_weights["hotel"] = {
            "hotel_count_weight": 0,
            "country_hotel_count_weight": 0,
            "agoda_score_weight": 0.6,
            "google_score_weight": 0.4,
        }

    # Weight adjustment forms - one for each destination type
    st.sidebar.markdown(
        """
    Customize the importance of each factor for optimal search results:
    - **Cities & Areas**: Hotel count normalization factors
    - **Hotels**: Review score factors (Agoda vs Google)
    
    *Adjust weights below to fine-tune your search experience.*
    """
    )

    dest_types = ["city", "area", "hotel"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")

        with st.sidebar.form(f"{dest_type}_weight_form"):
            if dest_type == "hotel":
                # Hotel-specific weights (Agoda and Google scores)
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

                # Show weight sum for validation
                weight_sum = agoda_score_weight + google_score_weight
                if weight_sum > 0:
                    st.write(f"Weight Sum: {weight_sum:.2f}")

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
                )

                if submit_weights:
                    if update_weights(
                        dest_type, 
                        agoda_score_weight=agoda_score_weight, 
                        google_score_weight=google_score_weight
                    ):
                        st.sidebar.success(
                            f"{dest_type.title()} weights updated successfully!"
                        )
                    else:
                        st.sidebar.error(
                            f"Failed to update {dest_type.title()} weights. Make sure values are between 0 and 1."
                        )
            else:
                # City/Area weights (hotel count normalization)
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

                # Show weight sum for validation
                weight_sum = hotel_count_weight + country_hotel_count_weight
                if weight_sum > 0:
                    st.write(f"Weight Sum: {weight_sum:.2f}")

                submit_weights = st.form_submit_button(
                    f"Update {dest_type.title()} Weights"
                )

                if submit_weights:
                    if update_weights(
                        dest_type, 
                        hotel_count_weight=hotel_count_weight, 
                        country_hotel_count_weight=country_hotel_count_weight
                    ):
                        st.sidebar.success(
                            f"{dest_type.title()} weights updated successfully!"
                        )
                    else:
                        st.sidebar.error(
                            f"Failed to update {dest_type.title()} weights. Make sure values are between 0 and 1."
                        )

    # Search section
    query = st.text_input("Search for a destination:")
    if query:
        results = search_destinations(query)
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
                    "Normalized: Factor 1",  # For cities/areas: Global Hotel Count, For hotels: Agoda Score
                    "Normalized: Factor 2",  # For cities/areas: Country Hotel Count, For hotels: Google Score
                    "Total Score",
                    "Factor 1 Weight",      # For cities/areas: Hotel Count Weight, For hotels: Agoda Score Weight
                    "Factor 2 Weight",      # For cities/areas: Country Hotel Count Weight, For hotels: Google Score Weight
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
                    "Normalized: Factor 1",
                    "Normalized: Factor 2",
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
                    ["Type", "Factor 1 Weight", "Factor 2 Weight"]
                ].drop_duplicates()
                
                # Add meaningful column names based on type
                weights_display = []
                for _, row in weights_df.iterrows():
                    if row["Type"] == "hotel":
                        weights_display.append({
                            "Type": row["Type"],
                            "Factor 1 (Agoda Score)": row["Factor 1 Weight"],
                            "Factor 2 (Google Score)": row["Factor 2 Weight"]
                        })
                    else:
                        weights_display.append({
                            "Type": row["Type"],
                            "Factor 1 (Global Hotel Count)": row["Factor 1 Weight"],
                            "Factor 2 (Country Hotel Count)": row["Factor 2 Weight"]
                        })
                
                weights_display_df = pd.DataFrame(weights_display)
                st.dataframe(weights_display_df, hide_index=True)
        else:
            st.write("No matching destinations found.")


if __name__ == "__main__":
    main()