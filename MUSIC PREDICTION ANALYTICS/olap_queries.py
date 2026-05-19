"""
OLAP Queries — Music Analytics Data Warehouse
IST 3201 — Data Warehousing and Business Intelligence
Makerere University | May 2026

Run this script against music_warehouse.db to reproduce all analytical results.
Requirements: pip install pandas
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect('music_warehouse.db')

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 1 — SLICE: Hit Rate by Genre
# Module 3 — OLAP slice operation (single dimension filter)
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("QUERY 1: Hit Rate by Genre (SLICE)")
print("=" * 60)
q1 = pd.read_sql_query("""
    SELECT
        g.genre_name                                    AS Genre,
        COUNT(*)                                        AS Total_Tracks,
        SUM(f.label_key)                                AS HITs,
        ROUND(100.0 * SUM(f.label_key) / COUNT(*), 1)  AS Hit_Rate_Pct
    FROM fact_predictions f
    JOIN dim_genre g ON f.genre_key = g.genre_key
    GROUP BY g.genre_name
    ORDER BY Hit_Rate_Pct DESC
""", conn)
print(q1.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 2 — SLICE: Hit Rate by Era (Decade)
# Module 3 — OLAP slice across the time dimension
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUERY 2: Hit Rate by Era (SLICE)")
print("=" * 60)
q2 = pd.read_sql_query("""
    SELECT
        d.era                                           AS Era,
        COUNT(*)                                        AS Total_Tracks,
        SUM(f.label_key)                                AS HITs,
        ROUND(100.0 * SUM(f.label_key) / COUNT(*), 1)  AS Hit_Rate_Pct
    FROM fact_predictions f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.era
    ORDER BY d.era
""", conn)
print(q2.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 3 — DRILL-DOWN: Hit Rate by Year
# Module 3 — OLAP drill-down from era → year
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUERY 3: Hit Rate by Year (DRILL-DOWN)")
print("=" * 60)
q3 = pd.read_sql_query("""
    SELECT
        d.year                                          AS Year,
        COUNT(*)                                        AS Total_Tracks,
        SUM(f.label_key)                                AS HITs,
        ROUND(100.0 * SUM(f.label_key) / COUNT(*), 1)  AS Hit_Rate_Pct
    FROM fact_predictions f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year
    ORDER BY d.year
""", conn)
print(q3.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 4 — DICE / ROLAP CROSS-TAB: Genre × Era
# Module 3 — ROLAP cross-tabulation (two-dimension analysis)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUERY 4: Genre × Era Cross-Tabulation (ROLAP DICE)")
print("=" * 60)
q4 = pd.read_sql_query("""
    SELECT
        g.genre_name    AS Genre,
        d.era           AS Era,
        COUNT(*)        AS Total_Tracks,
        SUM(f.label_key) AS HITs,
        ROUND(100.0 * SUM(f.label_key) / COUNT(*), 1) AS Hit_Rate_Pct
    FROM fact_predictions f
    JOIN dim_genre g ON f.genre_key = g.genre_key
    JOIN dim_date  d ON f.date_key  = d.date_key
    GROUP BY g.genre_name, d.era
    ORDER BY g.genre_name, d.era
""", conn)
print(q4.to_string(index=False))

# Pivot for readability
pivot = q4.pivot_table(
    index='Genre', columns='Era',
    values='Hit_Rate_Pct', aggfunc='first'
).fillna('—')
print("\nPivoted Cross-Tab (Hit Rate %):")
print(pivot.to_string())

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 5 — RANKING: Top Artists by Hit Rate (min 5 tracks)
# Module 3 — Ranking query on artist dimension
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUERY 5: Top Artists by Hit Rate — min 5 tracks (RANKING)")
print("=" * 60)
q5 = pd.read_sql_query("""
    SELECT
        a.artist_name                                   AS Artist,
        COUNT(*)                                        AS Total_Tracks,
        SUM(f.label_key)                                AS HITs,
        ROUND(100.0 * SUM(f.label_key) / COUNT(*), 1)  AS Hit_Rate_Pct
    FROM fact_predictions f
    JOIN dim_artist a ON f.artist_key = a.artist_key
    GROUP BY a.artist_name
    HAVING Total_Tracks >= 5
    ORDER BY Hit_Rate_Pct DESC, Total_Tracks DESC
    LIMIT 10
""", conn)
print(q5.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 6 — FEATURE COMPARISON: Average Audio/Lyric Features HIT vs FLOP
# Module 3 — Analytical comparison across label dimension
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("QUERY 6: Avg Feature Comparison — HITs vs FLOPs")
print("=" * 60)
q6 = pd.read_sql_query("""
    SELECT
        l.label_name                            AS Label,
        ROUND(AVG(f.tempo_bpm), 1)              AS Avg_Tempo_BPM,
        ROUND(AVG(f.danceability_proxy), 3)     AS Avg_Danceability,
        ROUND(AVG(f.rhythmic_complexity), 3)    AS Avg_Rhythmic_Complexity,
        ROUND(AVG(f.sentiment_compound), 3)     AS Avg_Sentiment,
        ROUND(AVG(f.unique_word_ratio), 3)      AS Avg_Vocab_Richness,
        ROUND(AVG(f.rms_mean), 3)               AS Avg_Energy
    FROM fact_predictions f
    JOIN dim_label l ON f.label_key = l.label_key
    GROUP BY l.label_name
""", conn)
print(q6.to_string(index=False))

# ─────────────────────────────────────────────────────────────────────────────
# MOLAP — Pandas Pivot Table (in-memory multidimensional cube)
# Module 3 — MOLAP comparison (vs SQLite ROLAP above)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("MOLAP: Pandas Pivot Table — Avg Hit Rate by Genre × Era")
print("=" * 60)
df_all = pd.read_sql_query("""
    SELECT f.label_key, g.genre_name, d.era
    FROM fact_predictions f
    JOIN dim_genre g ON f.genre_key = g.genre_key
    JOIN dim_date  d ON f.date_key  = d.date_key
""", conn)

molap = df_all.pivot_table(
    index='genre_name', columns='era',
    values='label_key', aggfunc='mean'
).round(3)
print(molap.to_string())
print("\n(Values = average hit rate per cell; 1.0 = 100% hit rate)")

conn.close()
print("\n" + "=" * 60)
print("All OLAP queries complete.")
print("=" * 60)
