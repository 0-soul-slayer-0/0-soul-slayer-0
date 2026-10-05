"""Render a self-hosted profile panel from public GitHub data (stdlib only)."""
import argparse
import datetime
import html
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
USERNAME = os.environ.get("PROFILE_USERNAME", "0-soul-slayer-0")


def api(path, data=None):
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        "https://api.github.com/" + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "public-profile-panel",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get("errors"):
        raise RuntimeError("GitHub returned a GraphQL error; keeping the previous panel")
    return result


def render(contributions, repos):
    calendar = contributions["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    public = [repo for repo in repos if not repo.get("private", False)
              and repo["name"].lower() != USERNAME.lower()]
    original = [repo for repo in public if not repo.get("fork", False)]
    stars = sum(repo["stargazers_count"] for repo in original)
    languages = sorted({repo["language"] for repo in original if repo.get("language")})
    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y")
    colors = {"NONE": "#172335", "FIRST_QUARTILE": "#164e63",
              "SECOND_QUARTILE": "#0e7490", "THIRD_QUARTILE": "#22b8cf",
              "FOURTH_QUARTILE": "#67e8f9"}
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="290" viewBox="0 0 960 290" role="img" aria-labelledby="title desc">',
             '<title id="title">Public GitHub activity</title>',
             '<desc id="desc">Contribution calendar with a decorative animated trace. The trace does not indicate additional contributions.</desc>',
             '<style>text{font-family:Consolas,"Liberation Mono",monospace}.trace{stroke-dasharray:22 99999;animation:trace 38s linear infinite}.head{animation:pulse 3s ease-in-out infinite}@keyframes trace{to{stroke-dashoffset:-6100}}@keyframes pulse{50%{opacity:.35}}@media(prefers-reduced-motion:reduce){.trace{display:none}.head{animation:none}}</style>',
             '<rect x="1" y="1" width="958" height="288" rx="14" fill="#0b1020" stroke="#2d3850"/>',
             '<circle cx="29" cy="28" r="4" fill="#67e8f9" class="head"/>',
             '<text x="43" y="32" font-size="11" fill="#a8b5cd" letter-spacing="2">ACTIVITY / TELEMETRY</text>',
             f'<text x="932" y="32" text-anchor="end" font-size="10" fill="#7d8aa5">UPDATED {updated.upper()} UTC</text>']
    metrics = [(f'{calendar["totalContributions"]:,}', 'CONTRIBUTIONS / LAST YEAR'),
               (str(len(public)), 'PUBLIC PROJECT REPOS'),
               (str(stars), 'STARS / ORIGINAL REPOS'),
               (str(len(languages)), 'PRIMARY LANGUAGES')]
    for i, (value, label) in enumerate(metrics):
        x = 28 + i * 233
        parts += [f'<text x="{x}" y="77" font-size="30" font-weight="bold" fill="{"#67e8f9" if i == 0 else "#e2e8f0"}">{value}</text>',
                  f'<text x="{x}" y="98" font-size="9" fill="#8595b0" letter-spacing=".6">{label}</text>']
    parts.append('<path d="M28 115H932" stroke="#273147"/>')
    weeks = calendar["weeks"]
    cell, step = 10, 16
    start = (960 - ((len(weeks) - 1) * step + cell)) / 2
    trace = []
    for column, week in enumerate(weeks):
        points = []
        for day in week["contributionDays"]:
            date = datetime.date.fromisoformat(day["date"])
            row = (date.weekday() + 1) % 7
            x, y = start + column * step, 134 + row * step
            color = colors[day["contributionLevel"]]
            tooltip = html.escape(f'{day["date"]}: {day["contributionCount"]} contributions')
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}"><title>{tooltip}</title></rect>')
            points.append((x + cell / 2, y + cell / 2))
        trace.extend(points if column % 2 == 0 else reversed(points))
    path = "M" + "L".join(f"{x},{y}" for x, y in trace)
    parts.append(f'<path d="{path}" class="trace" fill="none" stroke="#c4b5fd" stroke-width="3" stroke-linecap="round" opacity=".9"/>')
    parts.append('<text x="28" y="270" font-size="10" fill="#7d8aa5">PUBLIC SIGNAL. CONTINUOUS LEARNING.</text>')
    parts.append('<text x="756" y="270" font-size="10" fill="#7d8aa5">LESS</text>')
    for i, color in enumerate(colors.values()):
        parts.append(f'<rect x="{793+i*16}" y="260" width="10" height="10" rx="2" fill="{color}"/>')
    parts.append('<text x="883" y="270" font-size="10" fill="#7d8aa5">MORE</text></svg>')
    (ROOT / "assets" / "activity.svg").write_text("\n".join(parts) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path)
    args = parser.parse_args()
    if args.snapshot_dir:
        contributions = json.loads((args.snapshot_dir / "contributions.json").read_text())
        repos = json.loads((args.snapshot_dir / "public-repos.json").read_text())
    else:
        query = """query($login:String!){user(login:$login){contributionsCollection{
            contributionCalendar{totalContributions weeks{contributionDays{
            contributionCount contributionLevel date}}}}}}"""
        contributions = api("graphql", {"query": query, "variables": {"login": USERNAME}})
        repos = []
        page = 1
        while True:
            batch = api(f"users/{USERNAME}/repos?per_page=100&type=owner&page={page}")
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    render(contributions, repos)


if __name__ == "__main__":
    main()
