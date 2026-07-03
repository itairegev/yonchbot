"""The progress dashboard.

Reads the diary (data/games.csv) and builds one HTML page you can open in
any browser: big numbers on top (games, level), a bar chart of games per
day below, and the full table at the bottom.

The page is a single file with no internet needed - everything is inside.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .progress import Diary

# Bar colors, checked with a color-vision validator for light & dark screens.
BAR_LIGHT = "#2563eb"
BAR_DARK = "#3b82f6"


def games_per_day(games: list[dict]) -> list[tuple[str, int]]:
    """Count how many games happened on each date, oldest first."""
    counts = Counter(g["when"][:10] for g in games)  # first 10 chars = YYYY-MM-DD
    return sorted(counts.items())


def build_dashboard(diary: Diary, out_path: str | Path) -> Path:
    games = diary.read_games()
    totals = diary.totals()
    per_day = games_per_day(games)
    max_count = max((c for _, c in per_day), default=1)

    bars = []
    for i, (day, count) in enumerate(per_day):
        height_pct = round(100 * count / max_count, 1)
        nice_day = day[5:]  # drop the year: "07-15" is enough
        bars.append(
            f'<div class="bar-col" data-day="{day}" data-count="{count}">'
            f'<div class="bar" style="height:{height_pct}%"></div>'
            f'<div class="bar-label">{nice_day}</div></div>'
        )

    rows = "".join(
        f"<tr><td>{g['when'].replace('T', ' ')}</td><td>{g['steps_played']}</td>"
        f"<td>{'✅' if g['finished'] == 'yes' else '⏹️'}</td><td>{g['notes']}</td></tr>"
        for g in reversed(games)
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YonchBot Progress</title>
<style>
  :root {{ --bg:#fcfcfb; --ink:#1f2937; --muted:#6b7280; --card:#ffffff;
           --line:#e5e7eb; --bar:{BAR_LIGHT}; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#1a1a19; --ink:#f3f4f6; --muted:#9ca3af; --card:#242423;
             --line:#3a3a38; --bar:{BAR_DARK}; }}
  }}
  body {{ margin:0; padding:24px; background:var(--bg); color:var(--ink);
         font-family:-apple-system, "Segoe UI", sans-serif; }}
  h1 {{ margin:0 0 4px; }} .sub {{ color:var(--muted); margin:0 0 24px; }}
  .tiles {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:28px; }}
  .tile {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:16px 22px; min-width:130px; }}
  .tile .num {{ font-size:2.2rem; font-weight:700; }}
  .tile .cap {{ color:var(--muted); font-size:.85rem; }}
  .chart-card {{ background:var(--card); border:1px solid var(--line);
                border-radius:12px; padding:20px; margin-bottom:28px; }}
  .chart {{ display:flex; align-items:flex-end; gap:2px; height:180px; }}
  .bar-col {{ flex:1; max-width:56px; display:flex; flex-direction:column;
             justify-content:flex-end; height:100%; position:relative; cursor:default; }}
  .bar {{ background:var(--bar); border-radius:4px 4px 0 0; min-height:3px; }}
  .bar-label {{ text-align:center; font-size:.7rem; color:var(--muted); padding-top:6px; }}
  .bar-col:hover .bar {{ opacity:.85; }}
  .bar-col:hover::after {{ content:attr(data-count) " games on " attr(data-day);
    position:absolute; bottom:100%; left:50%; transform:translateX(-50%);
    background:var(--ink); color:var(--bg); padding:4px 8px; border-radius:6px;
    font-size:.75rem; white-space:nowrap; margin-bottom:4px; }}
  table {{ border-collapse:collapse; width:100%; background:var(--card);
          border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--line);
           font-size:.9rem; }}
  th {{ color:var(--muted); font-weight:600; }}
  .empty {{ color:var(--muted); padding:32px; text-align:center; }}
</style>
</head>
<body>
<h1>🤖 YonchBot</h1>
<p class="sub">Built by Yonch &amp; his uncle · every game the bot plays is progress</p>
<div class="tiles">
  <div class="tile"><div class="num">{totals.games}</div><div class="cap">games played</div></div>
  <div class="tile"><div class="num">{totals.finished}</div><div class="cap">games finished</div></div>
  <div class="tile"><div class="num">Lv. {totals.bot_level}</div><div class="cap">bot level · next in {totals.next_level_in}</div></div>
  <div class="tile"><div class="num">{totals.total_steps}</div><div class="cap">moves made</div></div>
</div>
<div class="chart-card">
  <h3 style="margin:0 0 16px">Games per day</h3>
  {'<div class="chart">' + ''.join(bars) + '</div>' if bars else '<div class="empty">No games yet — run the bot and come back!</div>'}
</div>
<h3>Every game</h3>
<table>
<tr><th>When</th><th>Moves</th><th>Finished</th><th>Notes</th></tr>
{rows if rows else '<tr><td colspan="4" class="empty">The diary is empty so far.</td></tr>'}
</table>
</body>
</html>"""

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
