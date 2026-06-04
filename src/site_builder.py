import json
from typing import Dict, List


def build_sparkline_svg(ratings: List[float], width: int = 80, height: int = 20) -> str:
    if len(ratings) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(ratings), max(ratings)
    span = hi - lo if hi != lo else 1.0
    pts = []
    for i, r in enumerate(ratings):
        x = i * width / (len(ratings) - 1)
        y = height - (r - lo) / span * height
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#22c55e" if ratings[-1] >= ratings[0] else "#ef4444"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'</svg>'
    )


def build_leaderboard_html(players: List[Dict]) -> str:
    rows = []
    for i, p in enumerate(players, 1):
        d = p['rating_delta_30d']
        d_color = "#22c55e" if d >= 0 else "#ef4444"
        d_str = f"+{d:.1f}" if d >= 0 else f"{d:.1f}"
        rows.append(
            f'<tr class="player-row" data-player-id="{p["player_id"]}" style="cursor:pointer">'
            f'<td>{i}</td>'
            f'<td><strong>{p["name"]}</strong></td>'
            f'<td>{p["current_rating"]:.1f}</td>'
            f'<td style="color:{d_color}">{d_str}</td>'
            f'<td>{p["matches_played"]}</td>'
            f'<td>{build_sparkline_svg(p["recent_ratings"])}</td>'
            f'</tr>'
        )
    return (
        '<table id="leaderboard">'
        '<thead><tr><th>#</th><th>Player</th><th>ELO</th>'
        '<th>30d Δ</th><th>Matches</th><th>Trend</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )


def build_site(players: List[Dict], player_histories: Dict[str, List[Dict]]) -> str:
    leaderboard = build_leaderboard_html(players)
    histories_json = json.dumps(player_histories)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Premier League Player ELO</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 1rem 2rem; background: #0f0f0f; color: #e5e5e5; }}
  h1 {{ color: #38bdf8; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #94a3b8; margin-top: 0; font-size: 0.9rem; }}
  .filter-bar {{ display: flex; gap: 1rem; margin-bottom: 1rem; align-items: center; flex-wrap: wrap; }}
  .filter-bar label {{ color: #94a3b8; font-size: 0.85rem; }}
  .filter-bar input {{ background: #1a1a1a; border: 1px solid #333; color: #e5e5e5; padding: 0.3rem 0.6rem; border-radius: 4px; }}
  #leaderboard {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
  #leaderboard th {{ text-align: left; padding: 0.5rem 1rem; border-bottom: 2px solid #333; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  #leaderboard td {{ padding: 0.5rem 1rem; border-bottom: 1px solid #1f1f1f; font-size: 0.9rem; }}
  #leaderboard tr:hover td {{ background: #1a1a1a; }}
  #leaderboard tr.selected td {{ background: #1e3a5f; }}
  #detail {{ background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; padding: 1.25rem; margin-top: 1rem; display: none; }}
  #detail h2 {{ color: #38bdf8; margin-top: 0; }}
</style>
</head>
<body>
<h1>Premier League Player ELO</h1>
<p class="subtitle">Player ratings calculated from xG events: +xG for attackers on the pitch, −xG for defenders. Click a player to see their full timeline. Data: StatsBomb + understat, 2020–2025.</p>

<div class="filter-bar">
  <label>Min matches: <input type="number" id="min-matches" value="10" min="1" style="width:60px"></label>
  <label>Search: <input type="text" id="search" placeholder="Player name…"></label>
</div>

{leaderboard}

<div id="detail">
  <h2 id="detail-name"></h2>
  <div id="detail-chart"></div>
</div>

<script>
const HISTORIES = {histories_json};

document.getElementById('min-matches').addEventListener('input', filterTable);
document.getElementById('search').addEventListener('input', filterTable);

function filterTable() {{
  const min = parseInt(document.getElementById('min-matches').value) || 0;
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#leaderboard tbody tr').forEach(row => {{
    const matches = parseInt(row.cells[4].textContent);
    const name = row.cells[1].textContent.toLowerCase();
    row.style.display = (matches >= min && name.includes(q)) ? '' : 'none';
  }});
}}

document.querySelectorAll('.player-row').forEach(row => {{
  row.addEventListener('click', () => {{
    document.querySelectorAll('.player-row').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    showDetail(row.dataset.playerId, row.cells[1].textContent.trim());
  }});
}});

function showDetail(pid, name) {{
  const history = HISTORIES[pid];
  if (!history || history.length === 0) return;

  const dates = history.map(h => h.date);
  const ratings = history.map(h => h.rating_after);
  const tips = history.map(h =>
    h.home_team + ' vs ' + h.away_team +
    '<br>' + (h.rating_delta >= 0 ? '+' : '') + h.rating_delta.toFixed(2) + ' ELO'
  );

  const shapes = [], annotations = [];
  for (let i = 1; i < history.length; i++) {{
    if (history[i].player_team !== history[i - 1].player_team) {{
      shapes.push({{
        type: 'line', x0: dates[i], x1: dates[i],
        y0: 0, y1: 1, yref: 'paper',
        line: {{ color: '#f59e0b', width: 1, dash: 'dot' }}
      }});
      annotations.push({{
        x: dates[i], y: 1.08, yref: 'paper',
        text: history[i].player_team, showarrow: false,
        font: {{ color: '#f59e0b', size: 9 }}
      }});
    }}
  }}

  Plotly.newPlot('detail-chart', [{{
    x: dates, y: ratings, mode: 'lines+markers',
    marker: {{ size: 4, color: '#38bdf8' }},
    line: {{ color: '#38bdf8', width: 2 }},
    text: tips,
    hovertemplate: '%{{text}}<br>ELO: %{{y:.1f}}<extra></extra>'
  }}], {{
    paper_bgcolor: '#141414', plot_bgcolor: '#141414',
    font: {{ color: '#e5e5e5' }},
    xaxis: {{ gridcolor: '#2a2a2a', title: 'Date' }},
    yaxis: {{ gridcolor: '#2a2a2a', title: 'ELO Rating' }},
    shapes, annotations,
    margin: {{ t: 30, r: 20, b: 50, l: 60 }}, height: 320
  }}, {{responsive: true}});

  document.getElementById('detail-name').textContent = name;
  document.getElementById('detail').style.display = 'block';
  document.getElementById('detail').scrollIntoView({{behavior: 'smooth'}});
}}
</script>
</body>
</html>"""
