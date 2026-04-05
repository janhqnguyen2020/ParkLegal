import duckdb
con = duckdb.connect()

# The Logic:
# 1. Clean the date: Remove ' 12:00:00 AM'
# 2. Clean the time: Remove commas (',') and pad to 4 digits
# 3. Combine and Parse
query = """
COPY (
    SELECT 
        *,
        strptime(
            regexp_replace(issue_date, ' 12:00:00 AM', '') || ' ' || 
            LPAD(regexp_replace(issue_time::VARCHAR, ',', ''), 4, '0'), 
            '%Y %b %d %H%M'
        ) AS issue_timestamp,
        loc_lat AS latitude, 
        loc_long AS longitude
    FROM read_csv_auto('Parking_Citations_20260404.csv')
    WHERE latitude IS NOT NULL 
      AND loc_lat != 0
) TO 'data_v5.parquet' (FORMAT PARQUET)
"""

print("Cleaning commas and building timestamps...")
con.execute(query)
print("Done! Parquet is now sanitized and ready.")
