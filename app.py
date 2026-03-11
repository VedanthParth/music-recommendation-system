"""
app.py  —  SoundCluster  (CSV edition with K-Medoids + Recommender)
Data source: spotify_data.csv
Clustering:  K-Medoids (PAM implementation, no external library needed)
"""

import os
import csv
import math
import random
import logging
import secrets
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
CORS(app)

# ── Configuration ──────────────────────────────────────────────────────────
CSV_PATH      = Path(__file__).parent / "spotify_data.csv"
VIZ_SAMPLE    = 1500   # tracks shown in scatter / cluster viz
FEATURE_COLS  = [
    "danceability", "energy", "loudness", "speechiness",
    "acousticness", "instrumentalness", "liveness", "valence", "tempo"
]

# ── Load & Pre-process CSV ─────────────────────────────────────────────────
logger.info("Loading CSV …")
_ALL_TRACKS: list[dict] = []

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    count = 0
    for row in reader:
        if count >= 1000:
            break
        if not row.get("track_name") or not row.get("artist_name"):
            continue
        try:
            track = {
                "id":               row["track_id"],
                "name":             row["track_name"],
                "artists":          [row["artist_name"]],
                "album":            "",
                "album_image":      "",
                "duration_ms":      int(float(row.get("duration_ms", 0) or 0)),
                "popularity":       int(float(row.get("popularity", 0) or 0)),
                "explicit":         0.0,
                "year":             int(float(row.get("year", 0) or 0)),
                "genre":            row.get("genre", ""),
                "features_real":    True,
                "danceability":     float(row.get("danceability", 0) or 0),
                "energy":           float(row.get("energy", 0) or 0),
                "loudness":         float(row.get("loudness", 0) or 0),
                "speechiness":      float(row.get("speechiness", 0) or 0),
                "acousticness":     float(row.get("acousticness", 0) or 0),
                "instrumentalness": float(row.get("instrumentalness", 0) or 0),
                "liveness":         float(row.get("liveness", 0) or 0),
                "valence":          float(row.get("valence", 0) or 0),
                "tempo":            float(row.get("tempo", 0) or 0),
                "key":              int(float(row.get("key", 0) or 0)),
                "mode":             int(float(row.get("mode", 0) or 0)),
                "time_signature":   int(float(row.get("time_signature", 4) or 4)),
            }
            _ALL_TRACKS.append(track)
            count += 1
        except (ValueError, KeyError):
            continue

logger.info("Loaded %d tracks from CSV.", len(_ALL_TRACKS))

# Build a lookup dict by track_id for recommender
_TRACK_BY_ID: dict[str, dict] = {t["id"]: t for t in _ALL_TRACKS}

# Pre-compute feature matrix for the full dataset (for recommender similarity)
_FULL_X_RAW = np.array([[t[f] for f in FEATURE_COLS] for t in _ALL_TRACKS], dtype=float)
_FULL_SCALER = StandardScaler()
_FULL_X_SCALED = _FULL_SCALER.fit_transform(_FULL_X_RAW)
_FULL_ID_INDEX = {t["id"]: i for i, t in enumerate(_ALL_TRACKS)}


# ── K-Medoids (PAM — fast approximate) ────────────────────────────────────

def _kmedoids(X: np.ndarray, k: int, max_iter: int = 100, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """
    Partition Around Medoids (PAM):
    Returns (labels, medoid_indices).
    Uses a greedy swap with random restarts for speed on mid-sized datasets.
    """
    rng = np.random.default_rng(seed)
    n = len(X)

    # ── Pre-compute pairwise distances (Euclidean) ──────────────────────
    # For n > 2000 use approximate via random projections; for smaller, exact.
    if n > 3000:
        # Random projection down to 20 dims for distance computation
        proj = rng.standard_normal((X.shape[1], 20)) / math.sqrt(20)
        Xp   = X @ proj
    else:
        Xp = X

    # Compute pairwise squared distances chunk-wise
    norms  = (Xp ** 2).sum(axis=1)
    D = norms[:, None] + norms[None, :] - 2 * (Xp @ Xp.T)
    D = np.maximum(D, 0)  # numerical safety

    best_cost    = np.inf
    best_labels  = np.zeros(n, dtype=int)
    best_medoids = np.arange(k)

    for _ in range(3):  # 3 random re-starts
        medoids = rng.choice(n, k, replace=False)
        labels  = np.zeros(n, dtype=int)

        for iteration in range(max_iter):
            # Assignment step
            dist_to_medoids = D[:, medoids]  # (n, k)
            new_labels = np.argmin(dist_to_medoids, axis=1)

            # Update step — for each cluster, pick the point minimising total distance
            new_medoids = medoids.copy()
            for c in range(k):
                members = np.where(new_labels == c)[0]
                if len(members) == 0:
                    new_medoids[c] = rng.choice(n)
                    continue
                sub_D = D[np.ix_(members, members)]
                new_medoids[c] = members[np.argmin(sub_D.sum(axis=1))]

            if np.array_equal(new_medoids, medoids) or np.array_equal(new_labels, labels):
                labels = new_labels
                medoids = new_medoids
                break
            labels  = new_labels
            medoids = new_medoids

        # Total cost = sum of distances to assigned medoids
        cost = D[np.arange(n), medoids[labels]].sum()
        if cost < best_cost:
            best_cost    = cost
            best_labels  = labels
            best_medoids = medoids

    return best_labels, best_medoids


def _elbow_k(X: np.ndarray, k_min: int = 3, k_max: int = 8) -> int:
    """Pick best k via largest gap in K-Means inertia (faster than K-Medoids for elbow)."""
    from sklearn.cluster import KMeans
    k_range  = range(k_min, k_max + 1)
    inertias = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)
    if len(inertias) < 2:
        return k_min
    diffs    = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    best_idx = diffs.index(max(diffs))
    return list(k_range)[best_idx + 1]


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── /api/genres — returns all available genres ─────────────────────────────
@app.route("/api/genres")
def genres():
    genre_set = sorted({t["genre"] for t in _ALL_TRACKS if t["genre"]})
    return jsonify({"genres": genre_set})


# ── /api/playlist — returns a stratified sample for clustering viz ──────────
@app.route("/api/playlist", methods=["POST"])
def get_playlist():
    data  = request.get_json(force=True) or {}
    genre = data.get("genre", "").strip()
    year_from = int(data.get("year_from", 2000) or 2000)
    year_to   = int(data.get("year_to",   2023) or 2023)
    min_pop   = int(data.get("min_popularity", 0) or 0)

    # Filter
    filtered = [
        t for t in _ALL_TRACKS
        if (not genre or t["genre"] == genre)
        and year_from <= t["year"] <= year_to
        and t["popularity"] >= min_pop
    ]

    if not filtered:
        return jsonify({"error": "No tracks match the selected filters."}), 400

    # For balanced representation: stratify by genre if showing all genres
    if not genre and len(filtered) > VIZ_SAMPLE:
        # Stratified sample across genres
        genres_present = list({t["genre"] for t in filtered})
        per_genre = max(1, VIZ_SAMPLE // len(genres_present))
        by_genre: dict[str, list] = {}
        for t in filtered:
            by_genre.setdefault(t["genre"], []).append(t)
        sample: list[dict] = []
        for g, tracks in by_genre.items():
            sample.extend(random.sample(tracks, min(per_genre, len(tracks))))
        if len(sample) < VIZ_SAMPLE:
            # Top up with random draws from the remainder
            rest = [t for t in filtered if t not in set(sample)]
            sample.extend(random.sample(rest, min(VIZ_SAMPLE - len(sample), len(rest))))
        filtered = sample[:VIZ_SAMPLE]
    elif len(filtered) > VIZ_SAMPLE:
        filtered = random.sample(filtered, VIZ_SAMPLE)

    active_genres = sorted({t["genre"] for t in filtered})
    active_years  = sorted({t["year"] for t in filtered})

    return jsonify({
        "playlist": {
            "id":           "csv_demo",
            "name":         f"Spotify Dataset{' — ' + genre if genre else ''}",
            "description":  f"{len(filtered):,} tracks · {min(active_years)}–{max(active_years)} · {len(active_genres)} genres",
            "image":        "",
            "owner":        "spotify_data.csv",
            "total_tracks": len(filtered),
        },
        "tracks":        filtered,
        "real_features": len(filtered),
        "demo_mode":     True,
    })


# ── /api/cluster — K-Medoids on the provided tracks ───────────────────────
@app.route("/api/cluster", methods=["POST"])
def cluster_tracks():
    data       = request.get_json(force=True)
    tracks     = data.get("tracks", [])
    n_clusters = data.get("n_clusters", None)

    if len(tracks) < 4:
        return jsonify({"error": "Need at least 4 tracks to cluster"}), 400

    X_raw = np.array([[t.get(f, 0) for f in FEATURE_COLS] for t in tracks], dtype=float)

    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)

    if n_clusters is None:
        n_clusters = _elbow_k(X, k_min=3, k_max=min(8, len(tracks) // 3))

    labels, medoid_indices = _kmedoids(X, k=n_clusters)
    labels = labels.tolist()

    # PCA 2D
    pca2     = PCA(n_components=2, random_state=42)
    pca_coords   = pca2.fit_transform(X).tolist()
    pca_variance = pca2.explained_variance_ratio_.tolist()

    # PCA 3D
    pca3     = PCA(n_components=min(3, X.shape[1]), random_state=42)
    pca3_coords = pca3.fit_transform(X).tolist()

    cluster_summaries = []
    for k in range(n_clusters):
        idx     = [i for i, lbl in enumerate(labels) if lbl == k]
        members = X_raw[idx]

        centroid = members.mean(axis=0).tolist()
        medoid_local_idx = medoid_indices[k]  # index in X (tracks array)
        medoid_track = tracks[medoid_local_idx]

        cluster_summaries.append({
            "cluster":       k,
            "size":          len(idx),
            "medoid_id":     medoid_track["id"],
            "medoid_name":   medoid_track["name"],
            "medoid_artist": medoid_track["artists"][0] if medoid_track.get("artists") else "",
            "centroid": {feat: round(centroid[i], 4) for i, feat in enumerate(FEATURE_COLS)},
            "top_genres":    _top_genres([tracks[i] for i in idx], 3),
        })

    corr_matrix = np.corrcoef(X_raw.T).tolist()

    return jsonify({
        "n_clusters":        n_clusters,
        "labels":            labels,
        "pca_coords":        pca_coords,
        "pca3_coords":       pca3_coords,
        "pca_variance":      pca_variance,
        "cluster_summaries": cluster_summaries,
        "feature_cols":      FEATURE_COLS,
        "corr_matrix":       corr_matrix,
    })


# ── /api/recommend — find N nearest neighbours in the FULL dataset ─────────
@app.route("/api/recommend", methods=["POST"])
def recommend():
    """
    Given one or more seed track IDs (or raw feature values),
    return the top N most similar tracks from the entire CSV dataset
    using cosine similarity on scaled audio features.
    """
    data       = request.get_json(force=True)
    seed_ids   = data.get("seed_ids", [])       # list of track_id strings
    n_results  = min(int(data.get("n", 10)), 50)
    genre_filter = data.get("genre", "").strip()  # optional genre filter

    if not seed_ids:
        return jsonify({"error": "Provide at least one seed_id"}), 400

    # Resolve seeds to row indices
    seed_indices = [_FULL_ID_INDEX[sid] for sid in seed_ids if sid in _FULL_ID_INDEX]
    if not seed_indices:
        return jsonify({"error": "None of the provided seed IDs were found in the dataset"}), 404

    # Query vector = mean of seed feature vectors (already scaled)
    query_vec = _FULL_X_SCALED[seed_indices].mean(axis=0)  # (n_features,)

    # Cosine similarity against the full scaled matrix
    norms      = np.linalg.norm(_FULL_X_SCALED, axis=1)
    query_norm = np.linalg.norm(query_vec)
    # Avoid division by zero
    safe_norms = np.where(norms == 0, 1e-8, norms)
    similarities = (_FULL_X_SCALED @ query_vec) / (safe_norms * (query_norm or 1e-8))

    # Exclude the seeds themselves
    similarities[seed_indices] = -2.0

    # Apply genre filter if requested
    if genre_filter:
        mask = np.array([t["genre"] != genre_filter for t in _ALL_TRACKS])
        similarities[mask] = -2.0

    # Top N
    top_indices = np.argsort(similarities)[::-1][:n_results]

    recommendations = []
    for idx in top_indices:
        t = _ALL_TRACKS[idx]
        recommendations.append({
            **t,
            "similarity": round(float(similarities[idx]), 4),
        })

    return jsonify({
        "seeds":           [_ALL_TRACKS[i]["name"] for i in seed_indices],
        "recommendations": recommendations,
    })


# ── /api/stats — quick dataset stats ──────────────────────────────────────
@app.route("/api/stats")
def stats():
    genres_count = {}
    for t in _ALL_TRACKS:
        genres_count[t["genre"]] = genres_count.get(t["genre"], 0) + 1
    return jsonify({
        "total_tracks": len(_ALL_TRACKS),
        "genres":       dict(sorted(genres_count.items(), key=lambda x: -x[1])),
        "year_range":   [min(t["year"] for t in _ALL_TRACKS), max(t["year"] for t in _ALL_TRACKS)],
    })


# ── Helpers ────────────────────────────────────────────────────────────────

def _top_genres(tracks: list[dict], n: int) -> list[str]:
    counts: dict[str, int] = {}
    for t in tracks:
        g = t.get("genre", "")
        if g:
            counts[g] = counts.get(g, 0) + 1
    return [g for g, _ in sorted(counts.items(), key=lambda x: -x[1])[:n]]


if __name__ == "__main__":
    app.run(debug=True, port=5000)
