
from pathlib import Path

import folium
from folium.plugins import MarkerCluster
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


CSV_PATH = Path(__file__).with_name("station.csv")


def load_station_records(csv_path: Path, *, unique_sites: bool) -> pd.DataFrame:
	"""Load station data and optionally keep one row per measurement site."""
	df = pd.read_csv(csv_path)

	required_columns = {
		"MonitoringLocationIdentifier",
		"MonitoringLocationName",
		"LatitudeMeasure",
		"LongitudeMeasure",
	}
	missing_columns = required_columns - set(df.columns)
	if missing_columns:
		raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

	records = (
		df.dropna(subset=["LatitudeMeasure", "LongitudeMeasure"])
		.loc[:, ["MonitoringLocationIdentifier", "MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure"]]
		.rename(
			columns={
				"MonitoringLocationIdentifier": "site_id",
				"MonitoringLocationName": "site_name",
				"LatitudeMeasure": "latitude",
				"LongitudeMeasure": "longitude",
			}
		)
		.copy()
	)

	records["latitude"] = pd.to_numeric(records["latitude"], errors="coerce")
	records["longitude"] = pd.to_numeric(records["longitude"], errors="coerce")
	records = records.dropna(subset=["latitude", "longitude"])
	if unique_sites:
		records = records.drop_duplicates(subset=["site_id"])
	return records


def load_measurement_sites(csv_path: Path) -> pd.DataFrame:
	"""Load station data and keep one row per measurement site."""
	return load_station_records(csv_path, unique_sites=True)


def load_all_stations(csv_path: Path) -> pd.DataFrame:
	"""Load station data and preserve every valid station record."""
	return load_station_records(csv_path, unique_sites=False)


def build_station_map_folium(csv_path: Path | str = CSV_PATH, *, unique_sites: bool = True) -> folium.Map:
	"""Build a folium map for unique sites or all station records."""
	records = load_station_records(Path(csv_path), unique_sites=unique_sites)
	if records.empty:
		return folium.Map(location=[37.8, -84.3], zoom_start=7)

	center_lat = records["latitude"].mean()
	center_lon = records["longitude"].mean()
	station_map = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="CartoDB positron")

	if unique_sites:
		for _, site in records.iterrows():
			popup_text = f"{site['site_name']}<br>{site['site_id']}"
			folium.Marker(
				location=[site["latitude"], site["longitude"]],
				popup=folium.Popup(popup_text, max_width=300),
				tooltip=site["site_name"],
			).add_to(station_map)
	else:
		cluster = MarkerCluster(name="All stations").add_to(station_map)
		for _, site in records.iterrows():
			popup_text = f"{site['site_name']}<br>{site['site_id']}"
			folium.Marker(
				location=[site["latitude"], site["longitude"]],
				popup=folium.Popup(popup_text, max_width=300),
				tooltip=site["site_name"],
			).add_to(cluster)

	return station_map


def main() -> None:
	st.set_page_config(page_title="Water Quality Sites", layout="wide")
	st.title("Water Quality Measurement Sites")
	st.write("Browse unique measurement sites or all station records from station.csv.")

	unique_sites = load_measurement_sites(CSV_PATH)
	all_stations = load_all_stations(CSV_PATH)
	metric_left, metric_right = st.columns(2)
	with metric_left:
		st.metric("Unique sites", len(unique_sites))
	with metric_right:
		st.metric("All station records", len(all_stations))

	unique_tab, all_tab = st.tabs(["Unique sites", "All stations"])

	with unique_tab:
		left_column, right_column = st.columns([1, 2])
		with left_column:
			st.subheader("Site names")
			st.dataframe(unique_sites[["site_name", "site_id"]].sort_values("site_name"), use_container_width=True, hide_index=True)

		with right_column:
			st.subheader("Map")
			station_map = build_station_map_folium(CSV_PATH, unique_sites=True)
			st_folium(station_map, width=900, height=650)

	with all_tab:
		st.subheader("All station locations")
		st.dataframe(all_stations[["site_name", "site_id", "latitude", "longitude"]].sort_values("site_name"), use_container_width=True, hide_index=True)
		all_station_map = build_station_map_folium(CSV_PATH, unique_sites=False)
		st_folium(all_station_map, width=900, height=650)


if __name__ == "__main__":
	main()

