import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")
st.title("Water Quality Explorer")

# Upload files
station_file = st.file_uploader("Upload station.csv", type="csv")
results_file = st.file_uploader("Upload narrowresult.csv", type="csv")

if station_file and results_file:
    # Load data
    station_df = pd.read_csv(station_file)
    results_df = pd.read_csv(results_file)

    # Clean station data
    station_df = station_df[[
        "MonitoringLocationIdentifier",
        "MonitoringLocationName",
        "MonitoringLocationDescriptionText",
        "LatitudeMeasure",
        "LongitudeMeasure"
    ]]
    station_df = station_df.dropna().drop_duplicates(subset=["MonitoringLocationIdentifier"])

    # Clean results data
    results_df = results_df[[
        "ActivityStartDate",
        "MonitoringLocationIdentifier",
        "CharacteristicName",
        "ResultMeasureValue",
        "ResultMeasure/MeasureUnitCode"
    ]]
    results_df['ActivityStartDate'] = pd.to_datetime(results_df['ActivityStartDate'], errors='coerce')
    results_df['ResultMeasureValue'] = pd.to_numeric(results_df['ResultMeasureValue'], errors='coerce')
    results_df = results_df.dropna()

    # UI for contaminant selection
    all_characteristics = sorted(results_df['CharacteristicName'].dropna().unique())
    selected_characteristic = st.selectbox("Select a contaminant", all_characteristics)

    # Filter for selected characteristic
    characteristic_df = results_df[results_df["CharacteristicName"] == selected_characteristic]

    if not characteristic_df.empty:
        # UI: date and value ranges
        min_date, max_date = characteristic_df["ActivityStartDate"].min(), characteristic_df["ActivityStartDate"].max()
        start_end_dates = st.date_input("Select date range", [min_date, max_date])
        min_val = float(characteristic_df["ResultMeasureValue"].min())
        max_val = float(characteristic_df["ResultMeasureValue"].max())
        val_range = st.slider("Select value range", min_val, max_val, (min_val, max_val))

        if len(start_end_dates) == 2:
            start_date, end_date = start_end_dates

            # Apply filters
            mask = (
                (characteristic_df["ActivityStartDate"] >= pd.to_datetime(start_date)) &
                (characteristic_df["ActivityStartDate"] <= pd.to_datetime(end_date)) &
                (characteristic_df["ResultMeasureValue"] >= val_range[0]) &
                (characteristic_df["ResultMeasureValue"] <= val_range[1])
            )
            matching_data = characteristic_df[mask]

            # Join results with station info
            matching_station_ids = matching_data["MonitoringLocationIdentifier"].unique()
            station_df_filtered = station_df[station_df["MonitoringLocationIdentifier"].isin(matching_station_ids)]

            # === Map ===
            if not station_df_filtered.empty:
                avg_lat = station_df_filtered["LatitudeMeasure"].mean()
                avg_lon = station_df_filtered["LongitudeMeasure"].mean()

                folium_map = folium.Map(location=[avg_lat, avg_lon], zoom_start=6)
                marker_cluster = MarkerCluster().add_to(folium_map)

                for _, row in station_df_filtered.iterrows():
                    folium.Marker(
                        location=[row["LatitudeMeasure"], row["LongitudeMeasure"]],
                        popup=f"<b>{row['MonitoringLocationName']}</b><br>{row['MonitoringLocationDescriptionText']}",
                        tooltip=row["MonitoringLocationName"]
                    ).add_to(marker_cluster)

                st.subheader("📍 Map of Stations Affected by Selected Contaminant")
                st.markdown(
                    f"This map shows stations that measured **{selected_characteristic}** "
                    f"between **{start_date}** and **{end_date}**, with values between **{val_range[0]}** and **{val_range[1]}**."
                )
                st_folium(folium_map, width=700, height=500)
            else:
                st.warning("🚫 No stations found that match the filters. Try adjusting your contaminant, date, or value range.")

            # === Trend Plot (Filtered Data Only) ===
            if not matching_data.empty:
                st.subheader("📈 Trend Over Time for Selected Contaminant (Filtered Data)")
                fig, ax = plt.subplots(figsize=(10, 5))
                for site, group in matching_data.groupby("MonitoringLocationIdentifier"):
                    group_sorted = group.sort_values("ActivityStartDate")
                    ax.plot(group_sorted["ActivityStartDate"], group_sorted["ResultMeasureValue"], label=site)

                unit = matching_data["ResultMeasure/MeasureUnitCode"].mode().iloc[0] if not matching_data.empty else ""
                ax.set_title(f"{selected_characteristic} Over Time (Filtered)")
                ax.set_xlabel("Date")
                ax.set_ylabel(f"{selected_characteristic} ({unit})")
                ax.legend(title="Site", bbox_to_anchor=(1.05, 1), loc='upper left')
                ax.grid(True)
                st.pyplot(fig)
            else:
                st.warning("📉 No data available in this range to plot a trend.")
        else:
            st.warning("Please select a valid start and end date.")
    else:
        st.warning("No data found for the selected contaminant.")
