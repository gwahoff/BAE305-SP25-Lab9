
from pathlib import Path

import altair as alt
import folium
from folium.plugins import MarkerCluster
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


CSV_PATH = Path(__file__).with_name("station.csv")
RESULTS_CSV_PATH = Path(__file__).with_name("narrowresult.csv")


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


def load_clean_results(results_csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
	"""Load narrowresult data and remove blank or zero-valued measurements."""
	results = pd.read_csv(results_csv_path)

	required_columns = {
		"MonitoringLocationIdentifier",
		"CharacteristicName",
		"ResultMeasureValue",
	}
	missing_columns = required_columns - set(results.columns)
	if missing_columns:
		raise ValueError(f"Missing required columns in narrowresult.csv: {sorted(missing_columns)}")

	cleaned = results.copy()
	cleaned["MonitoringLocationIdentifier"] = cleaned["MonitoringLocationIdentifier"].astype(str).str.strip()
	cleaned["CharacteristicName"] = cleaned["CharacteristicName"].astype(str).str.strip()
	cleaned["ResultMeasureValue"] = pd.to_numeric(cleaned["ResultMeasureValue"], errors="coerce")

	cleaned = cleaned[
		(cleaned["MonitoringLocationIdentifier"].ne(""))
		& (cleaned["CharacteristicName"].ne(""))
		& (cleaned["ResultMeasureValue"].notna())
		& (cleaned["ResultMeasureValue"] > 0)
	].copy()

	return results, cleaned


def build_cleaned_results_map(cleaned_results: pd.DataFrame, station_csv_path: Path | str = CSV_PATH) -> folium.Map:
	"""Build a map for stations that appear in cleaned narrowresult records."""
	station_records = load_station_records(Path(station_csv_path), unique_sites=True)

	location_counts = (
		cleaned_results.groupby("MonitoringLocationIdentifier", dropna=True)
		.size()
		.rename("result_count")
		.reset_index()
	)

	map_points = station_records.merge(
		location_counts,
		left_on="site_id",
		right_on="MonitoringLocationIdentifier",
		how="inner",
	)

	if map_points.empty:
		return folium.Map(location=[37.8, -84.3], zoom_start=7)

	center_lat = map_points["latitude"].mean()
	center_lon = map_points["longitude"].mean()
	results_map = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="CartoDB positron")
	cluster = MarkerCluster(name="Cleaned results").add_to(results_map)

	for _, site in map_points.iterrows():
		popup_text = (
			f"{site['site_name']}<br>{site['site_id']}"
			f"<br>Cleaned results: {int(site['result_count'])}"
		)
		folium.Marker(
			location=[site["latitude"], site["longitude"]],
			popup=folium.Popup(popup_text, max_width=320),
			tooltip=site["site_name"],
		).add_to(cluster)

	return results_map


def prepare_timeseries_data(cleaned_results: pd.DataFrame) -> pd.DataFrame:
	"""Prepare cleaned results for a site-by-site time series chart."""
	plot_data = cleaned_results.copy()
	plot_data["ActivityStartDate"] = pd.to_datetime(plot_data["ActivityStartDate"], errors="coerce")
	plot_data = plot_data.dropna(subset=["ActivityStartDate", "ResultMeasureValue", "MonitoringLocationIdentifier"])
	plot_data = plot_data[
		["ActivityStartDate", "MonitoringLocationIdentifier", "CharacteristicName", "ResultMeasureValue"]
	].copy()

	# Average duplicate records for the same site/date/characteristic so each line renders cleanly.
	plot_data = (
		plot_data.groupby(["ActivityStartDate", "MonitoringLocationIdentifier", "CharacteristicName"], as_index=False)["ResultMeasureValue"]
		.mean()
	)
	return plot_data


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
	st.write("Browse station maps and cleaned measurement results from station.csv and narrowresult.csv.")

	unique_sites = load_measurement_sites(CSV_PATH)
	all_stations = load_all_stations(CSV_PATH)
	raw_results, cleaned_results = load_clean_results(RESULTS_CSV_PATH)

	metric_left, metric_mid, metric_right = st.columns(3)
	with metric_left:
		st.metric("Unique sites", len(unique_sites))
	with metric_mid:
		st.metric("All station records", len(all_stations))
	with metric_right:
		st.metric("Cleaned measurements", len(cleaned_results))

	unique_tab, all_tab, cleaned_tab = st.tabs(["Unique sites", "All stations", "Cleaned results"])

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

	with cleaned_tab:
		st.subheader("Cleaned narrowresult records")
		removed_count = len(raw_results) - len(cleaned_results)
		st.write(f"Rows in narrowresult.csv: {len(raw_results):,}. Rows removed as blank/zero/non-numeric: {removed_count:,}.")

		plot_data = prepare_timeseries_data(cleaned_results)
		st.subheader("Measured values over time by site")
		characteristics = sorted(plot_data["CharacteristicName"].dropna().unique().tolist())
		selected_characteristic = st.selectbox(
			"Select characteristic to plot",
			options=characteristics,
			index=0 if characteristics else None,
		)

		if selected_characteristic:
			series_data = plot_data[plot_data["CharacteristicName"] == selected_characteristic].copy()
			if series_data.empty:
				st.info("No cleaned rows available for the selected characteristic.")
			else:
				min_value = float(series_data["ResultMeasureValue"].min())
				max_value = float(series_data["ResultMeasureValue"].max())
				selected_range = st.slider(
					"Measured value range",
					min_value=min_value,
					max_value=max_value,
					value=(min_value, max_value),
				)
				series_data = series_data[
					(series_data["ResultMeasureValue"] >= selected_range[0])
					& (series_data["ResultMeasureValue"] <= selected_range[1])
				]
				if series_data.empty:
					st.info("No rows match the selected measured value range.")
				else:
					line_chart = (
						alt.Chart(series_data)
						.mark_line(point=True)
						.encode(
							x=alt.X("ActivityStartDate:T", title="Time"),
							y=alt.Y("ResultMeasureValue:Q", title="Measured value"),
							color=alt.Color("MonitoringLocationIdentifier:N", title="Site"),
							tooltip=[
								alt.Tooltip("ActivityStartDate:T", title="Date"),
								alt.Tooltip("MonitoringLocationIdentifier:N", title="Site"),
								alt.Tooltip("ResultMeasureValue:Q", title="Measured value", format=".3f"),
							],
						)
						.properties(height=420)
					)
					st.altair_chart(line_chart, use_container_width=True)
		else:
			st.info("No characteristics are available to plot.")

		preview_columns = [
			"MonitoringLocationIdentifier",
			"CharacteristicName",
			"ResultMeasureValue",
			"ResultMeasure/MeasureUnitCode",
			"ActivityStartDate",
		]
		existing_preview_columns = [col for col in preview_columns if col in cleaned_results.columns]
		st.dataframe(
			cleaned_results[existing_preview_columns].sort_values("ActivityStartDate", ascending=False),
			use_container_width=True,
			hide_index=True,
		)

		st.subheader("Map of cleaned-result locations")
		cleaned_results_map = build_cleaned_results_map(cleaned_results, station_csv_path=CSV_PATH)
		st_folium(cleaned_results_map, width=900, height=650)


if __name__ == "__main__":
	main()

