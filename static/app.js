/**
 * SoundCluster — CSV K-Medoids Edition with Music Recommender
 * app.js
 */

// ── State ─────────────────────────────────────────────────────────────────
const state = {
  tracks: [],
  clusterData: null,
  playlistMeta: null,
  sortKey: null,
  sortAsc: true,
  searchQuery: '',
  clusterFilter: '',
  currentK: null,
  selectedSeed: null,   // { id, name, genre } of selected seed track
};

const CLUSTER_COLORS = [
  '#1DB954', '#1e90ff', '#ff6b6b', '#ffd93d',
  '#c77dff', '#ff9f43', '#00d2d3', '#e84393', '#a8e6cf', '#fddb92'
];
const RADAR_FEATURES = ['danceability', 'energy', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence'];
const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, sans-serif', color: '#f0f4f8' },
  margin: { l: 50, r: 30, t: 40, b: 50 },
};
const FEATURE_COLS = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'];

// ── Initialise ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadGenres);

async function loadGenres() {
  try {
    const res = await fetch('/api/genres');
    const data = await res.json();
    const sel = document.getElementById('genre-select');
    (data.genres || []).forEach(g => {
      const opt = document.createElement('option');
      opt.value = g; opt.textContent = g.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      sel.appendChild(opt);
    });
  } catch (e) { console.warn('Could not load genres', e); }
}

// ── Analyze ───────────────────────────────────────────────────────────────
async function analyzePlaylist() {
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true; btn.textContent = 'Analyzing…';
  showLoading(true);
  setStep(1);

  const genre = document.getElementById('genre-select').value;
  const yearFrom = parseInt(document.getElementById('year-from').value) || 2000;
  const yearTo = parseInt(document.getElementById('year-to').value) || 2023;
  const minPop = parseInt(document.getElementById('pop-slider').value) || 0;

  try {
    const res = await fetch('/api/playlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre, year_from: yearFrom, year_to: yearTo, min_popularity: minPop }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to load tracks');

    setStep(2);
    state.tracks = data.tracks;
    state.playlistMeta = data.playlist;

    setStep(3);
    const clusterRes = await fetch('/api/cluster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks: state.tracks, n_clusters: state.currentK }),
    });
    const clusterData = await clusterRes.json();
    if (!clusterRes.ok) throw new Error(clusterData.error || 'Clustering failed');

    state.clusterData = clusterData;
    state.tracks.forEach((t, i) => { t.cluster = clusterData.labels[i]; });

    setStep(4);
    await sleep(300);
    renderAll();
    showLoading(false);
    document.getElementById('results-section').classList.remove('hidden');
    document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    showLoading(false);
    showError(err.message || 'Something went wrong.');
    console.error(err);
  } finally {
    btn.disabled = false; btn.textContent = 'Analyze';
  }
}

async function reCluster() {
  if (!state.tracks.length) return;
  showLoading(true);
  setStep(3);
  try {
    const res = await fetch('/api/cluster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks: state.tracks, n_clusters: state.currentK }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Clustering failed');
    state.clusterData = data;
    state.tracks.forEach((t, i) => { t.cluster = data.labels[i]; });
    setStep(4);
    await sleep(200);
    renderAll();
  } catch (err) { showError(err.message); }
  finally { showLoading(false); }
}

function onKSlider(val) {
  state.currentK = parseInt(val);
  document.getElementById('k-display').textContent = val;
}

// ── Render All ────────────────────────────────────────────────────────────
function renderAll() {
  const { clusterData, playlistMeta, tracks } = state;
  const n = clusterData.n_clusters;

  document.getElementById('playlist-name').textContent = playlistMeta.name;
  document.getElementById('playlist-owner').textContent = playlistMeta.description || `by ${playlistMeta.owner}`;
  document.getElementById('track-count').textContent = tracks.length;
  document.getElementById('cluster-count').textContent = n;

  const slider = document.getElementById('k-slider');
  slider.value = n;
  document.getElementById('k-display').textContent = n;
  state.currentK = n;

  renderClusterCards(clusterData.cluster_summaries, CLUSTER_COLORS);
  renderScatterPlot(clusterData, tracks, CLUSTER_COLORS);
  renderScatter3D(clusterData, tracks, CLUSTER_COLORS);
  renderRadarChart(clusterData.cluster_summaries, CLUSTER_COLORS);
  renderHeatmap(clusterData.corr_matrix, clusterData.feature_cols);
  renderBarChart(clusterData.cluster_summaries, CLUSTER_COLORS);
  renderTable(tracks);
  populateClusterFilter(n);

  // Reset recommender
  state.selectedSeed = null;
  document.getElementById('seed-name').textContent = '— click a song row to select —';
  document.getElementById('recommend-btn').disabled = true;
  document.getElementById('rec-results').classList.add('hidden');
  document.getElementById('rec-results').innerHTML = '';
}

// ── Cluster Cards ─────────────────────────────────────────────────────────
function renderClusterCards(summaries, colors) {
  const container = document.getElementById('cluster-cards');
  container.innerHTML = '';
  const MINI_FEATURES = ['danceability', 'energy', 'valence', 'tempo', 'acousticness'];

  summaries.forEach((s, i) => {
    const color = colors[i % colors.length];
    const card = document.createElement('div');
    card.className = 'cluster-card';
    card.style.setProperty('--cluster-color', color);

    const barsHTML = MINI_FEATURES.map(f => {
      const raw = s.centroid[f] ?? 0;
      const pct = f === 'tempo' ? (raw / 200) * 100 : raw * 100;
      const val = f === 'tempo' ? Math.round(raw) + ' bpm' : raw.toFixed(2);
      return `<div class="mini-bar-wrap">
        <span class="mini-bar-label">${f.charAt(0).toUpperCase() + f.slice(1, 5)}.</span>
        <div class="mini-bar-bg"><div class="mini-bar-fill" style="width:${Math.min(pct, 100).toFixed(1)}%"></div></div>
        <span class="mini-bar-val">${val}</span>
      </div>`;
    }).join('');

    const genreTags = (s.top_genres || []).map(g =>
      `<span class="genre-tag">${g.replace(/-/g, ' ')}</span>`
    ).join('');

    card.innerHTML = `
      <div class="cluster-label">Cluster ${i + 1}</div>
      <div class="cluster-size">${s.size}</div>
      <div class="cluster-size-label">songs</div>
      <div class="medoid-info" title="Most representative song in this cluster">
        <span class="medoid-icon">⭐</span>
        <div>
          <div class="medoid-name">${s.medoid_name || '—'}</div>
          <div class="medoid-artist">${s.medoid_artist || ''}</div>
        </div>
      </div>
      <div class="genre-tags">${genreTags}</div>
      <div class="cluster-top-features">${barsHTML}</div>`;
    container.appendChild(card);
  });
}

// ── Scatter 2D ────────────────────────────────────────────────────────────
function renderScatterPlot(clusterData, tracks, colors) {
  const { labels, pca_coords, n_clusters, pca_variance, cluster_summaries } = clusterData;
  const medoidIdSet = new Set(cluster_summaries.map(s => s.medoid_id));
  const traces = [];

  for (let k = 0; k < n_clusters; k++) {
    const indices = labels.map((l, i) => l === k ? i : -1).filter(i => i >= 0);
    const color = colors[k % colors.length];

    // Regular members
    const regIdx = indices.filter(i => !medoidIdSet.has(tracks[i].id));
    traces.push({
      type: 'scatter', mode: 'markers', name: `Cluster ${k + 1}`,
      x: regIdx.map(i => pca_coords[i][0]),
      y: regIdx.map(i => pca_coords[i][1]),
      text: regIdx.map(i => `<b>${tracks[i].name}</b><br>${tracks[i].artists[0]}<br>Genre: ${tracks[i].genre}`),
      hovertemplate: '%{text}<extra></extra>',
      marker: { size: 7, color, line: { color: 'rgba(0,0,0,0.35)', width: 1 }, opacity: 0.75 },
    });

    // Medoids — bigger star marker
    const medIdx = indices.filter(i => medoidIdSet.has(tracks[i].id));
    if (medIdx.length) {
      traces.push({
        type: 'scatter', mode: 'markers+text', name: `C${k + 1} Medoid`,
        x: medIdx.map(i => pca_coords[i][0]),
        y: medIdx.map(i => pca_coords[i][1]),
        text: medIdx.map(i => tracks[i].name.length > 14 ? tracks[i].name.slice(0, 12) + '…' : tracks[i].name),
        textposition: 'top center',
        textfont: { size: 9, color },
        hovertext: medIdx.map(i => `<b>⭐ MEDOID: ${tracks[i].name}</b><br>${tracks[i].artists[0]}`),
        hovertemplate: '%{hovertext}<extra></extra>',
        marker: { size: 16, color, symbol: 'star', line: { color: '#fff', width: 1.5 } },
        showlegend: false,
      });
    }
  }

  const xV = pca_variance[0] ? `(${(pca_variance[0] * 100).toFixed(1)}%)` : '';
  const yV = pca_variance[1] ? `(${(pca_variance[1] * 100).toFixed(1)}%)` : '';
  Plotly.newPlot('scatter-plot', traces, {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { title: `PC1 ${xV}`, gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.12)' },
    yaxis: { title: `PC2 ${yV}`, gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.12)' },
    legend: { bgcolor: 'rgba(0,0,0,0)', bordercolor: 'rgba(255,255,255,0.1)', borderwidth: 1, tracegroupgap: 4 },
    hovermode: 'closest',
  }, { responsive: true, displayModeBar: false });
}

// ── Scatter 3D ────────────────────────────────────────────────────────────
function renderScatter3D(clusterData, tracks, colors) {
  const { labels, pca3_coords, n_clusters } = clusterData;
  const traces = [];
  for (let k = 0; k < n_clusters; k++) {
    const indices = labels.map((l, i) => l === k ? i : -1).filter(i => i >= 0);
    traces.push({
      type: 'scatter3d', mode: 'markers', name: `Cluster ${k + 1}`,
      x: indices.map(i => pca3_coords[i][0]),
      y: indices.map(i => pca3_coords[i][1]),
      z: indices.map(i => pca3_coords[i][2]),
      text: indices.map(i => `${tracks[i].name} — ${tracks[i].artists[0]}`),
      hovertemplate: '<b>%{text}</b><extra></extra>',
      marker: { size: 4, color: colors[k % colors.length], opacity: 0.75 },
    });
  }
  Plotly.newPlot('scatter3d-plot', traces, {
    ...PLOTLY_LAYOUT_BASE,
    scene: {
      xaxis: { title: 'PC1', gridcolor: 'rgba(255,255,255,0.06)', backgroundcolor: 'rgba(0,0,0,0)' },
      yaxis: { title: 'PC2', gridcolor: 'rgba(255,255,255,0.06)', backgroundcolor: 'rgba(0,0,0,0)' },
      zaxis: { title: 'PC3', gridcolor: 'rgba(255,255,255,0.06)', backgroundcolor: 'rgba(0,0,0,0)' },
      bgcolor: 'rgba(0,0,0,0)',
    },
    margin: { l: 0, r: 0, t: 30, b: 0 },
  }, { responsive: true });
}

// ── Radar ─────────────────────────────────────────────────────────────────
function renderRadarChart(summaries, colors) {
  const catsFull = [...RADAR_FEATURES, RADAR_FEATURES[0]];
  const traces = summaries.map((s, i) => {
    const vals = RADAR_FEATURES.map(f => s.centroid[f] ?? 0);
    return {
      type: 'scatterpolar', name: `Cluster ${i + 1}`,
      r: [...vals, vals[0]], theta: catsFull,
      fill: 'toself',
      fillcolor: hexToRgba(colors[i % colors.length], 0.18),
      line: { color: colors[i % colors.length], width: 2 },
    };
  });
  Plotly.newPlot('radar-plot', traces, {
    ...PLOTLY_LAYOUT_BASE,
    polar: {
      bgcolor: 'rgba(0,0,0,0)',
      radialaxis: { visible: true, range: [0, 1], gridcolor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.3)' },
      angularaxis: { gridcolor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.6)' },
    },
    showlegend: true, legend: { bgcolor: 'rgba(0,0,0,0)' },
    margin: { l: 60, r: 60, t: 40, b: 60 },
  }, { responsive: true, displayModeBar: false });
}

// ── Heatmap ───────────────────────────────────────────────────────────────
function renderHeatmap(corrMatrix, featureCols) {
  const short = featureCols.map(f => f === 'instrumentalness' ? 'Instrum.' : f.charAt(0).toUpperCase() + f.slice(1));
  Plotly.newPlot('heatmap-plot', [{
    type: 'heatmap', z: corrMatrix, x: short, y: short,
    colorscale: [[0, '#1e3a5f'], [0.5, '#080b10'], [1, '#1DB954']],
    zmin: -1, zmax: 1,
    hovertemplate: '%{x} × %{y}: <b>%{z:.2f}</b><extra></extra>',
    text: corrMatrix.map(row => row.map(v => v.toFixed(2))),
    texttemplate: '%{text}', textfont: { size: 10 },
  }], {
    ...PLOTLY_LAYOUT_BASE,
    xaxis: { side: 'bottom', tickfont: { size: 11 } },
    yaxis: { tickfont: { size: 11 }, autorange: 'reversed' },
    margin: { l: 110, r: 20, t: 30, b: 90 },
  }, { responsive: true, displayModeBar: false });
}

// ── Bar Chart ─────────────────────────────────────────────────────────────
function renderBarChart(summaries, colors) {
  const barF = ['danceability', 'energy', 'valence', 'speechiness', 'acousticness', 'liveness'];
  const traces = summaries.map((s, i) => ({
    type: 'bar', name: `Cluster ${i + 1}`,
    x: barF.map(f => f.charAt(0).toUpperCase() + f.slice(1)),
    y: barF.map(f => parseFloat((s.centroid[f] ?? 0).toFixed(3))),
    marker: { color: hexToRgba(colors[i % colors.length], 0.8), line: { color: colors[i % colors.length], width: 1.5 } },
    hovertemplate: '%{x}: <b>%{y:.3f}</b><extra></extra>',
  }));
  Plotly.newPlot('bar-plot', traces, {
    ...PLOTLY_LAYOUT_BASE,
    barmode: 'group',
    xaxis: { gridcolor: 'rgba(255,255,255,0.06)' },
    yaxis: { gridcolor: 'rgba(255,255,255,0.06)', range: [0, 1] },
    bargap: 0.15, bargroupgap: 0.05,
    legend: { bgcolor: 'rgba(0,0,0,0)' },
  }, { responsive: true, displayModeBar: false });
}

// ── Songs Table ───────────────────────────────────────────────────────────
function populateClusterFilter(n) {
  const sel = document.getElementById('cluster-filter');
  sel.innerHTML = '<option value="">All Clusters</option>';
  for (let i = 0; i < n; i++) {
    const opt = document.createElement('option');
    opt.value = i; opt.textContent = `Cluster ${i + 1}`;
    sel.appendChild(opt);
  }
}

function filterTable(val) {
  if (typeof val === 'string') state.searchQuery = val.toLowerCase();
  state.clusterFilter = document.getElementById('cluster-filter').value;
  renderTableRows();
}

function sortTable(key) {
  if (state.sortKey === key) state.sortAsc = !state.sortAsc;
  else { state.sortKey = key; state.sortAsc = true; }
  renderTableRows();
}

function renderTable(tracks) { renderTableRows(); }

function renderTableRows() {
  const { tracks, sortKey, sortAsc, searchQuery, clusterFilter } = state;
  const tbody = document.getElementById('songs-tbody');

  let filtered = tracks.filter(t => {
    const q = searchQuery;
    const m1 = !q || t.name.toLowerCase().includes(q) || t.artists.join(' ').toLowerCase().includes(q) || (t.genre || '').toLowerCase().includes(q);
    const m2 = clusterFilter === '' || String(t.cluster) === String(clusterFilter);
    return m1 && m2;
  });

  if (sortKey) {
    filtered.sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (sortKey === 'artists') { va = va.join(', '); vb = vb.join(', '); }
      if (typeof va === 'number') return sortAsc ? va - vb : vb - va;
      return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    });
  }

  tbody.innerHTML = filtered.map((t, idx) => {
    const color = CLUSTER_COLORS[t.cluster % CLUSTER_COLORS.length];
    const badge = `<span class="cluster-badge" style="color:${color};border-color:${hexToRgba(color, 0.4)};background:${hexToRgba(color, 0.12)}">C${t.cluster + 1}</span>`;
    const isSelected = state.selectedSeed && state.selectedSeed.id === t.id;
    const rowClass = isSelected ? 'selected-row' : '';
    const bar = (val, max = 1) => {
      const pct = Math.min((val / max) * 100, 100).toFixed(1);
      return `<div style="display:flex;align-items:center;gap:0.3rem">
        <div style="width:44px;height:4px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden">
          <div style="width:${pct}%;height:100%;background:${color};border-radius:4px"></div>
        </div>
        <span>${val.toFixed(2)}</span></div>`;
    };
    return `<tr class="${rowClass}" onclick="selectSeed('${t.id}','${escHtml(t.name)}','${escHtml(t.genre || '')}')" style="cursor:pointer">
      <td>${idx + 1}</td>
      <td class="song-name" title="${escHtml(t.name)}">${escHtml(t.name)}</td>
      <td title="${escHtml(t.artists.join(', '))}">${escHtml(t.artists[0])}</td>
      <td><span class="genre-tag small">${(t.genre || '').replace(/-/g, ' ')}</span></td>
      <td>${badge}</td>
      <td>${bar(t.danceability)}</td>
      <td>${bar(t.energy)}</td>
      <td>${bar(t.valence)}</td>
      <td>${Math.round(t.tempo)} bpm</td>
      <td>${t.popularity}</td>
    </tr>`;
  }).join('');
}

// ── Recommender ───────────────────────────────────────────────────────────
function selectSeed(id, name, genre) {
  state.selectedSeed = { id, name, genre };
  document.getElementById('seed-name').textContent = name;
  document.getElementById('recommend-btn').disabled = false;
  // Re-render table to highlight selected row
  renderTableRows();
}

async function fetchRecommendations() {
  if (!state.selectedSeed) return;
  const btn = document.getElementById('recommend-btn');
  btn.disabled = true; btn.textContent = 'Searching…';

  const genreLock = document.getElementById('genre-lock').checked;
  const recDiv = document.getElementById('rec-results');
  recDiv.innerHTML = '<div class="rec-loading">Finding similar songs across 1.1M tracks…</div>';
  recDiv.classList.remove('hidden');

  try {
    const body = {
      seed_ids: [state.selectedSeed.id],
      n: 12,
    };
    if (genreLock && state.selectedSeed.genre) {
      body.genre = state.selectedSeed.genre;
    }

    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Recommendation failed');

    renderRecommendations(data.recommendations, state.selectedSeed.name);
  } catch (err) {
    recDiv.innerHTML = `<div class="rec-error">Error: ${escHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Find Similar';
  }
}

function renderRecommendations(recs, seedName) {
  const recDiv = document.getElementById('rec-results');
  if (!recs || !recs.length) {
    recDiv.innerHTML = '<p style="color:var(--text-muted);padding:1rem;">No similar songs found.</p>';
    return;
  }

  const cards = recs.map((r, i) => {
    const sim = Math.round(r.similarity * 100);
    const simColor = sim >= 90 ? '#1DB954' : sim >= 70 ? '#ffd93d' : '#ff9f43';
    return `
    <div class="rec-card" onclick="selectSeed('${r.id}','${escHtml(r.name)}','${escHtml(r.genre || '')}')" style="cursor:pointer" title="Click to use as new seed">
      <div class="rec-rank">${i + 1}</div>
      <div class="rec-info">
        <div class="rec-name">${escHtml(r.name)}</div>
        <div class="rec-artist">${escHtml(r.artists[0] || '')} · ${(r.genre || '').replace(/-/g, ' ')} · ${r.year}</div>
        <div class="rec-features">
          ${miniFeatureBar('Dance', r.danceability)}
          ${miniFeatureBar('Energy', r.energy)}
          ${miniFeatureBar('Valence', r.valence)}
        </div>
      </div>
      <div class="rec-sim" style="color:${simColor}">${sim}%<div class="rec-sim-label">match</div></div>
    </div>`;
  }).join('');

  recDiv.innerHTML = `
    <div class="rec-header">Songs similar to <b>${escHtml(seedName)}</b> — from the full 1.1M track dataset</div>
    <div class="rec-grid">${cards}</div>`;
}

function miniFeatureBar(label, val) {
  const pct = Math.min((val || 0) * 100, 100).toFixed(0);
  return `<div class="rec-feat"><span>${label}</span><div class="rec-feat-bar"><div style="width:${pct}%;background:var(--green)"></div></div></div>`;
}

// ── Tab Switching ─────────────────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
  setTimeout(() => {
    const pid = { scatter: 'scatter-plot', scatter3d: 'scatter3d-plot', radar: 'radar-plot', heatmap: 'heatmap-plot', bar: 'bar-plot' }[tab];
    try { Plotly.Plots.resize(document.getElementById(pid)); } catch (_) { }
  }, 50);
}

// ── Loading UI ────────────────────────────────────────────────────────────
function showLoading(show) {
  document.getElementById('loading-overlay').classList.toggle('hidden', !show);
  if (show) {
    document.querySelectorAll('.step-dot').forEach(d => d.classList.remove('active', 'done'));
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  }
}

function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const dot = document.getElementById(`step-${i}`)?.querySelector('.step-dot');
    const step = document.getElementById(`step-${i}`);
    if (!dot || !step) continue;
    if (i < n) { dot.classList.remove('active'); dot.classList.add('done'); }
    else if (i === n) { dot.classList.add('active'); dot.classList.remove('done'); step.classList.add('active'); }
    else { dot.classList.remove('active', 'done'); }
  }
}

// ── Error Banner ──────────────────────────────────────────────────────────
function showError(msg) {
  const banner = document.getElementById('error-banner');
  document.getElementById('error-message').textContent = msg;
  banner.classList.remove('hidden');
  setTimeout(closeError, 8000);
}
function closeError() { document.getElementById('error-banner').classList.add('hidden'); }

// ── Utilities ─────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
function escHtml(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;'); }
