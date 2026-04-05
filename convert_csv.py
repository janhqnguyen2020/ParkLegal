import duckdb
con = duckdb.connect()
query = """
COPY (
    SELECT 
        *,
        strptime(issue_date, '%Y %b %d %I:%M:%S %p') AS issue_timestamp,
        loc_lat AS latitude, 
        loc_long AS longitude
    FROM read_csv_auto('Parking_Citations_20260404.csv')
    WHERE latitude IS NOT NULL
) TO 'data_v3.parquet' (FORMAT PARQUET)
"""
con.execute(query)