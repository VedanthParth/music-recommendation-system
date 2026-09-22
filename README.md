# 🎵 SoundCluster — Spotify Audio-Feature Clustering & Recommender

Clusters tracks from a Kaggle Spotify audio-features dataset and recommends similar songs using content-based similarity. Live Spotify API access wasn't usable for this (Spotify's audio-features data isn't accessible for bulk analysis like this), so the project runs on a downloaded Kaggle dataset instead.

## Features

- 📂 **Data source** — a local Kaggle Spotify audio-features dataset (`spotify_data.csv`), not the live Spotify API
- 🎚️ **Audio features** — 9 features per track: danceability, energy, loudness, speechiness, acousticness, instrumentalness, liveness, valence, tempo
- 🔬 **K-Medoids clustering** — custom PAM (Partition Around Medoids) implementation, no external clustering library
- 🧭 **Recommender** — given one or more seed tracks, returns the most similar tracks from the dataset using cosine similarity on standardized features
- 📊 **Visualizations** (Plotly.js) — PCA-based cluster views and related charts
- 🔎 **Genre & stats endpoints** for exploring the dataset

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Place a Kaggle Spotify audio-features CSV as `spotify_data.csv` in the project root (this file is not committed to the repo — see `.gitignore`)
3. Run:
   ```
   python app.py
   ```
4. Open http://localhost:5000 in your browser

## Project Structure

```
music-recommendation-system/
├── app.py               # Flask backend: CSV loading, K-Medoids clustering, recommender, PCA
├── requirements.txt     # Python dependencies
├── spotify_test.py      # Early experiment with live Spotify API access, superseded by the CSV approach
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js           # Frontend logic + Plotly.js charts
```

## Audio Features Used

| Feature | Description |
|---|---|
| Danceability | How suitable for dancing (0–1) |
| Energy | Intensity and activity (0–1) |
| Loudness | Overall loudness in dB |
| Speechiness | Presence of spoken words (0–1) |
| Acousticness | Confidence it's acoustic (0–1) |
| Instrumentalness | Likelihood of no vocals (0–1) |
| Liveness | Presence of live audience (0–1) |
| Valence | Musical positiveness (0–1) |
| Tempo | Estimated tempo in BPM |

## Team and Credits

This was a team project. Core implementation (Flask backend, K-Medoids clustering, similarity-based recommender, and Plotly.js visualizations) by Sanjeb (github.com/Sanjeb). Forked here as part of shared coursework.
