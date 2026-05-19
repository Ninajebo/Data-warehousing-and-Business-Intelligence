"""
ETL Pipeline — Music Analytics Data Warehouse
IST 3201 — Data Warehousing and Business Intelligence
Makerere University | May 2026

Source: final_features_v2.xlsx
Target: music_warehouse.db (SQLite star schema)
"""

import pandas as pd
import sqlite3
import os

# ── EXTRACT ──────────────────────────────────────────────────────────────────
print("=== EXTRACT ===")
df = pd.read_excel('final_features_v2.xlsx')
print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

# ── TRANSFORM ─────────────────────────────────────────────────────────────────
print("\n=== TRANSFORM ===")

# 1. Fill missing artists
df['artist'] = df['artist'].fillna('Unknown Artist')
print(f"Filled {df['artist'].isna().sum()} null artists")

# 2. Infer genre from title keywords
def infer_genre(title):
    t = str(title).lower()
    if any(w in t for w in ['gospel','praise','worship','hallelujah','jesus','god','faith','grace']):
        return 'Gospel'
    elif any(w in t for w in ['dancehall','ragga','reggae']):
        return 'Dancehall'
    elif any(w in t for w in ['hip hop','hiphop','rap','trap']):
        return 'Hip Hop'
    elif any(w in t for w in ['afrobeat','afro beat','afropop']):
        return 'Afrobeat'
    else:
        return 'Afropop'

df['genre'] = df['title'].apply(infer_genre)
print("Genre distribution:")
print(df['genre'].value_counts().to_string())

# 3. Map era from year
df['decade'] = (df['year'] // 10) * 10
df['era'] = df['decade'].map({2000: '2000s', 2010: '2010s', 2020: '2020s'})
print("\nEra distribution:")
print(df['era'].value_counts().sort_index().to_string())

# ── LOAD ──────────────────────────────────────────────────────────────────────
print("\n=== LOAD ===")

db_path = 'music_warehouse.db'
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create dimension tables
cur.executescript("""
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    year     INTEGER NOT NULL,
    decade   INTEGER NOT NULL,
    era      TEXT    NOT NULL
);

CREATE TABLE dim_artist (
    artist_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT    NOT NULL UNIQUE
);

CREATE TABLE dim_genre (
    genre_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    genre_name TEXT    NOT NULL UNIQUE
);

CREATE TABLE dim_label (
    label_key    INTEGER PRIMARY KEY,
    label_name   TEXT    NOT NULL,
    binary_value INTEGER NOT NULL
);

CREATE TABLE dim_song (
    song_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   TEXT,
    title      TEXT    NOT NULL,
    artist_key INTEGER REFERENCES dim_artist(artist_key),
    genre_key  INTEGER REFERENCES dim_genre(genre_key),
    date_key   INTEGER REFERENCES dim_date(date_key)
);

CREATE TABLE fact_predictions (
    fact_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    song_key   INTEGER REFERENCES dim_song(song_key),
    artist_key INTEGER REFERENCES dim_artist(artist_key),
    genre_key  INTEGER REFERENCES dim_genre(genre_key),
    date_key   INTEGER REFERENCES dim_date(date_key),
    label_key  INTEGER REFERENCES dim_label(label_key),
    views      INTEGER,
    -- Audio features (18)
    tempo_bpm              REAL, tempo_stability        REAL,
    beat_strength_mean     REAL, beat_strength_std      REAL,
    beat_count             REAL, onset_rate             REAL,
    onset_strength_mean    REAL, onset_strength_std     REAL,
    syncopation_proxy      REAL, rhythmic_complexity    REAL,
    rms_mean               REAL, rms_std                REAL,
    rms_dynamic_range      REAL, spectral_centroid_mean REAL,
    spectral_bandwidth_mean REAL, zero_crossing_rate_mean REAL,
    low_freq_energy_ratio  REAL, danceability_proxy     REAL,
    -- Lyric features (18)
    word_count             REAL, line_count             REAL,
    unique_word_ratio      REAL, avg_word_length        REAL,
    repetition_rate        REAL, readability_score      REAL,
    sentiment_compound     REAL, sentiment_positive     REAL,
    sentiment_negative     REAL, sentiment_neutral      REAL,
    sentiment_intensity    REAL, sentiment_consistency  REAL,
    topic_diversity        REAL, thematic_coherence_proxy REAL,
    concrete_word_ratio    REAL, verse_count            REAL,
    chorus_repetition_rate REAL, has_outlier_feature    REAL
);

CREATE TABLE dw_metadata (
    meta_key   TEXT PRIMARY KEY,
    meta_value TEXT
);
""")

# Populate dim_date
for y in df['year'].unique():
    d = (int(y) // 10) * 10
    e = f"{d}s"
    cur.execute("INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?)", (int(y), int(y), d, e))

# Populate dim_artist and dim_genre
for a in df['artist'].unique():
    cur.execute("INSERT OR IGNORE INTO dim_artist(artist_name) VALUES (?)", (str(a),))
for g in df['genre'].unique():
    cur.execute("INSERT OR IGNORE INTO dim_genre(genre_name) VALUES (?)", (str(g),))

# Populate dim_label
cur.execute("INSERT INTO dim_label VALUES (0, 'flop', 0)")
cur.execute("INSERT INTO dim_label VALUES (1, 'hit',  1)")

# Build lookup dicts
artist_map = {r[1]: r[0] for r in cur.execute("SELECT artist_key, artist_name FROM dim_artist")}
genre_map  = {r[1]: r[0] for r in cur.execute("SELECT genre_key,  genre_name  FROM dim_genre")}

# Feature column lists
audio_cols = [
    'tempo_bpm','tempo_stability','beat_strength_mean','beat_strength_std',
    'beat_count','onset_rate','onset_strength_mean','onset_strength_std',
    'syncopation_proxy','rhythmic_complexity','rms_mean','rms_std',
    'rms_dynamic_range','spectral_centroid_mean','spectral_bandwidth_mean',
    'zero_crossing_rate_mean','low_freq_energy_ratio','danceability_proxy'
]
lyric_cols = [
    'word_count','line_count','unique_word_ratio','avg_word_length',
    'repetition_rate','readability_score','sentiment_compound','sentiment_positive',
    'sentiment_negative','sentiment_neutral','sentiment_intensity','sentiment_consistency',
    'topic_diversity','thematic_coherence_proxy','concrete_word_ratio','verse_count',
    'chorus_repetition_rate','has_outlier_feature'
]

# Insert songs and facts
for _, row in df.iterrows():
    ak = artist_map[str(row['artist'])]
    gk = genre_map[row['genre']]
    dk = int(row['year'])
    lk = int(row['binary_label'])

    cur.execute(
        "INSERT INTO dim_song(video_id,title,artist_key,genre_key,date_key) VALUES(?,?,?,?,?)",
        (row['video_id'], str(row['title'])[:200], ak, gk, dk)
    )
    sk = cur.lastrowid

    avals = [float(row[c]) if pd.notna(row.get(c)) else None for c in audio_cols]
    lvals = [float(row[c]) if pd.notna(row.get(c)) else None for c in lyric_cols]

    placeholders = ",".join(["?"] * 36)
    cur.execute(
        f"""INSERT INTO fact_predictions(
            song_key,artist_key,genre_key,date_key,label_key,views,
            tempo_bpm,tempo_stability,beat_strength_mean,beat_strength_std,
            beat_count,onset_rate,onset_strength_mean,onset_strength_std,
            syncopation_proxy,rhythmic_complexity,rms_mean,rms_std,rms_dynamic_range,
            spectral_centroid_mean,spectral_bandwidth_mean,zero_crossing_rate_mean,
            low_freq_energy_ratio,danceability_proxy,
            word_count,line_count,unique_word_ratio,avg_word_length,repetition_rate,
            readability_score,sentiment_compound,sentiment_positive,sentiment_negative,
            sentiment_neutral,sentiment_intensity,sentiment_consistency,topic_diversity,
            thematic_coherence_proxy,concrete_word_ratio,verse_count,
            chorus_repetition_rate,has_outlier_feature
        ) VALUES (?,?,?,?,?,?,{placeholders})""",
        [sk, ak, gk, dk, lk, int(row['views'])] + avals + lvals
    )

# Metadata
meta = [
    ('source_file',      'final_features_v2.xlsx'),
    ('total_tracks',     '2018'),
    ('hit_count',        '740'),
    ('flop_count',       '1278'),
    ('year_range',       '2000-2026'),
    ('granularity',      'One row per track'),
    ('partitioning',     'By year, decade, genre'),
    ('record_of_source', 'YouTube audio + librosa + Whisper/VADER lyrics'),
    ('etl_version',      '1.0'),
    ('created',          '2026-05'),
]
cur.executemany("INSERT INTO dw_metadata VALUES(?,?)", meta)
conn.commit()

# ── VERIFY ────────────────────────────────────────────────────────────────────
print("\n=== VERIFICATION ===")
for tbl in ['dim_date','dim_artist','dim_genre','dim_label','dim_song','fact_predictions','dw_metadata']:
    cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {tbl:<25} {cnt:>5} rows")

conn.close()
print("\nETL complete. Database saved to music_warehouse.db")
