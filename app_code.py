import streamlit as st
import duckdb
from streamlit_keplergl import keplergl_static
from keplergl import KeplerGl
import datetime

st.set_page_config(layout="wide", page_title="Parking Analytics")
con = duckdb.connect()

# --- 1. TARGETING SYSTEM & PRESETS ---
st.sidebar.header("📍 Location Targeting")

# Preset dictionary
LA_PRESETS = {
    "Little Tokyo": "34.0494, -118.2411",
    "DTLA (Crypto.com Arena)": "34.0430, -118.2673",
    "West Hollywood": "34.0900, -118.3813",
    "Santa Monica Pier": "34.0100, -118.4960",
    "Hollywood Walk of Fame": "34.1016, -118.3268",
    "Silver Lake": "34.0907, -118.2785",
    "Koreatown": "34.0617, -118.3089",
    "The Grove": "34.0722, -118.3581",
    "Venice Boardwalk": "33.9850, -118.4695",
    "Custom (Type Below)": "CUSTOM"
}

selection = st.sidebar.selectbox("Jump to Neighborhood", options=list(LA_PRESETS.keys()))

# Coordinate handling
if selection == "Custom (Type Below)":
    coords_input = st.sidebar.text_input("Enter Lat, Lon", value="34.0494, -118.2411")
else:
    coords_input = LA_PRESETS[selection]

try:
    lat_str, lon_str = coords_input.split(',')
    curr_lat = float(lat_str.strip())
    curr_lon = float(lon_str.strip())
except:
    # Fallback if typing is messy
    curr_lat, curr_lon = 34.0494, -118.2411

if st.sidebar.button("🎯 Sync & Re-Analyze"):
    st.cache_data.clear()

# --- 2. FILTERS ---
st.sidebar.header("🎯 Filters")

radius_ft = st.sidebar.select_slider("Search Radius (Feet)", 
                                     options=[25, 50, 75, 100, 125, 150, 200, 250, 500, 1000, 5000], 
                                     value=100)
radius_km = (radius_ft * 0.3048) / 1000

hour_range = st.sidebar.slider("Hour of Day", 0, 23, (10, 14))

# Updated to 2025 to match your data format
date_range = st.sidebar.date_input("Date Range", 
                                   value=(datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)))

# --- 3. DATA LOADING ---
@st.cache_data
def get_map_data(lat, lon, rad, h_start, h_end, d_range):
    if len(d_range) != 2:
        return None
    d_start, d_end = d_range
    
    # Ensure the table name 'data_v5.parquet' matches your latest conversion
    query = f"""
        SELECT * FROM 'data_v5.parquet'
        WHERE (6371 * acos(LEAST(GREATEST(cos(radians({lat})) * cos(radians(latitude)) * cos(radians(longitude) - radians({lon})) + 
               sin(radians({lat})) * sin(radians(latitude)), -1), 1))) <= {rad}
        AND hour(issue_timestamp) BETWEEN {h_start} AND {h_end}
        AND CAST(issue_timestamp AS DATE) BETWEEN '{d_start}' AND '{d_end}'
        LIMIT 50000
    """
    df = con.execute(query).df()

    if not df.empty:
        df['latitude'] = df['latitude'].astype(float)
        df['longitude'] = df['longitude'].astype(float)
        for col in df.columns:
            if col not in ['latitude', 'longitude']:
                df[col] = df[col].astype(str)
    return df

# --- 4. EXECUTION ---
df = get_map_data(curr_lat, curr_lon, radius_km, hour_range[0], hour_range[1], date_range)

# --- 5. RENDER ---
st.title("Big Data Traffic Mapper 🚗")

if df is not None and not df.empty:
    st.subheader(f"Analyzing {selection}")
    st.write(f"Showing **{len(df)}** citations within **{radius_ft}ft** of target.")
    
    # Violation Filter
    all_types = sorted([str(x) for x in df['violation_description'].unique() if x is not None])
    selected = st.multiselect("Filter by Violation Type", options=all_types, default=all_types[:3])
    
    display_df = df[df['violation_description'].isin(selected)]
    
    # Kepler Config
    config = {
        'version': 'v1',
        'config': {
            'mapState': {
                'latitude': curr_lat,
                'longitude': curr_lon,
                'zoom': 17 if radius_ft < 300 else 14,
                'pitch': 40
            },
            'visState': {
                'layers': [{
                    'type': 'point',
                    'config': {
                        'dataId': 'Citations',
                        'label': 'Citations',
                        'color': [255, 153, 0] # Orange points
                    }
                }]
            }
        }
    }
    
    map_1 = KeplerGl(height=700, config=config)
    map_1.add_data(data=display_df, name="Citations")
    keplergl_static(map_1)
    
elif df is not None:
    st.warning(f"No citations found within {radius_ft}ft of these coordinates for the selected time.")
    st.info("💡 Pro-tip: Increase the radius or check if the date range covers your dataset.")
