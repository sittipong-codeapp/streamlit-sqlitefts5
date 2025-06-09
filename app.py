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
        "SELECT type, hotel_count_weight, country_hotel_count_weight FROM factor_weights"
    )
    weights_data = cursor.fetchall()
    conn.close()

    # Create dictionary of current weights by destination type
    current_weights = {}
    for dest_type, hotel_count_weight, country_hotel_count_weight in weights_data:
        current_weights[dest_type] = {
            "hotel_count_weight": hotel_count_weight,
            "country_hotel_count_weight": country_hotel_count_weight,
        }

    # Default values if no weights found (two-factor system)
    if "city" not in current_weights:
        current_weights["city"] = {
            "hotel_count_weight": 0.5,
            "country_hotel_count_weight": 0.5,
        }
    if "area" not in current_weights:
        current_weights["area"] = {
            "hotel_count_weight": 0.5,
            "country_hotel_count_weight": 0.5,
        }

    # Weight adjustment forms - one for each destination type
    st.sidebar.markdown(
        """
    Customize the importance of each factor for optimal search results:
    - **Global Hotel Normalization**: Compare destinations worldwide
    - **Country Hotel Normalization**: Compare destinations within the same country
    
    *Adjust weights below to fine-tune your search experience.*
    """
    )

    dest_types = ["city", "area"]

    for dest_type in dest_types:
        st.sidebar.subheader(f"{dest_type.title()} Factor Weights")

        with st.sidebar.form(f"{dest_type}_weight_form"):
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
                    dest_type, hotel_count_weight, country_hotel_count_weight
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
                    "Normalized: Global Hotel Count",
                    "Normalized: Country Hotel Count",
                    "Total Score",
                    "Hotel Count Weight",
                    "Country Hotel Count Weight",
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
                    "Normalized: Global Hotel Count",
                    "Normalized: Country Hotel Count",
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
                # Group by type and show weights
                weights_df = df[
                    ["Type", "Hotel Count Weight", "Country Hotel Count Weight"]
                ].drop_duplicates()
                st.dataframe(
                    weights_df,
                    hide_index=True,
                )
        else:
            st.write("No matching destinations found.")


if __name__ == "__main__":
    main()
