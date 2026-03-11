# 🎵 SoundCluster — Spotify Playlist Audio Feature Visualizer

Analyze any Spotify playlist and visualize its songs as K-means clusters based on audio features like danceability, energy, valence, tempo, and more.

## Features

- 🔐 **Spotify OAuth2 login** — Secure authorization code flow
- 📋 **Playlist support** — Any public or private playlist you have access to
- 🎚️ **Audio features** — Fetches all 9 Spotify audio features per track
- 🔬 **K-Means clustering** — Auto-selects optimal k (or let you choose with a slider)
- 📊 **5 interactive visualizations** (Plotly.js):
  - PCA 2D Cluster Scatter
  - PCA 3D Cluster Scatter (rotatable)
  - Feature Radar Chart per cluster
  - Feature Correlation Heatmap
  - Grouped Feature Bar Chart
- 🔎 **Songs Table** — Sortable, searchable, filterable by cluster

## Setup

### 1. Create a Spotify Developer App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add `http://localhost:5000/callback` as a **Redirect URI**
4. Copy your **Client ID** and **Client Secret**

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:5000/callback
FLASK_SECRET_KEY=any_random_long_string
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

## Usage

1. Click **Login with Spotify** and authorize the app
2. Paste a Spotify playlist URL (e.g. `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`)
3. Click **Analyze**
4. Explore the 5 visualizations and the songs table
5. Adjust the **cluster slider** and click **Re-cluster** to experiment

## Project Structure

```
Spotify-music-recommender/
├── app.py              # Flask backend (OAuth2, Spotify API, clustering)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── templates/
│   └── index.html      # Main SPA template
└── static/
    ├── style.css        # Dark-mode design system
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
