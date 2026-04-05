import streamlit as st
import duckdb
from streamlit_keplergl import keplergl_static
from keplergl import KeplerGl

# MOVE THIS TO THE VERY TOP (Must be first Streamlit command)
st.set_page_config(layout="wide", page_title="Big Data Traffic Mapper 🚗")

con = duckdb.connect()

@st.cache_data
def get_all_violation_types():
    query = "SELECT DISTINCT violation_description FROM 'data_v3.parquet' WHERE violation_description IS NOT NULL ORDER BY 1"
    return con.execute(query).df()['violation_description'].tolist()

@st.cache_data
def get_filtered_map_data(selected_list):
    if not selected_list:
        return None
    
    formatted_list = "', '".join(selected_list)
    query = f"""
        SELECT * FROM 'data_v3.parquet' 
        WHERE violation_description IN ('{formatted_list}')
        AND latitude IS NOT NULL
        LIMIT 40000
    """
    df = con.execute(query).df()

    # --- THE BRUTE FORCE JSON FIX ---
    # Convert lat/lon to floats first so they stay as numbers
    df['latitude'] = df['latitude'].astype(float)
    df['longitude'] = df['longitude'].astype(float)

    # For every other column, if it's a date or a weird object, make it a string
    for col in df.columns:
        if col not in ['latitude', 'longitude']:
            # This catches Timestamps, Decimals, and Nulls
            df[col] = df[col].astype(str)
    
    return df

# UI LOGIC
all_types = get_all_violation_types()

st.sidebar.header("Violation Filters")
if all_types:
    # Safely pick a default
    default_selection = [all_types[0]]
    selected_violations = st.sidebar.multiselect("Violation Types", all_types, default=default_selection)
    df = get_filtered_map_data(selected_violations)
else:
    st.error("Data not loaded correctly.")
    df = None

# RENDER
st.title("Big Data Traffic Mapper 🚗")

if df is not None:
    st.write(f"Displaying {len(df)} points")
    
    initial_config = {
        'version': 'v1',
        'config': {
            'mapState': {
                'latitude': 34.0494, # Little Tokyo
                'longitude': -118.2411,
                'zoom': 13,
                'pitch': 45
            }
        }
    }
    
    map_1 = KeplerGl(height=700, config=initial_config)
    map_1.add_data(data=df, name="Citations")
    keplergl_static(map_1)