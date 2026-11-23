"""Render public GitHub commit contributions and opened PRs by repository language."""

import json
import subprocess
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

LOGIN = "atsuki-sakai"
PROFILE_REPOSITORY = f"{LOGIN}/{LOGIN}"
OUTPUT = Path(__file__).resolve().parents[1] / "assets/activity-languages.svg"
MAX_REPOSITORIES = 100
WINDOW_DAYS = 365
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!, $repos: Int!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalRepositoriesWithContributedCommits
      totalRepositoriesWithContributedPullRequests
      commits: commitContributionsByRepository(maxRepositories: $repos) {
        repository { nameWithOwner visibility primaryLanguage { name } }
        contributions(first: 1) { totalCount }
      }
      pullRequests: pullRequestContributionsByRepository(maxRepositories: $repos) {
        repository { nameWithOwner visibility primaryLanguage { name } }
        contributions(first: 1) { totalCount }
      }
    }
  }
}
"""
# Strip repository metadata before handing the GitHub response to the renderer.
FILTER = """
def included:
  .repository.visibility == "PUBLIC" and .repository.nameWithOwner != "%s";
def language:
  .repository.primaryLanguage.name // "Unclassified";
.data.user.contributionsCollection |
if . == null then error("GitHub returned no contribution collection")
else {
  complete: (
    (.commits | length) == .totalRepositoriesWithContributedCommits
    and (.pullRequests | length) == .totalRepositoriesWithContributedPullRequests
  ),
  commits: [.commits[] | select(included) |
    {language: language, count: .contributions.totalCount}],
  pullRequests: [.pullRequests[] | select(included) |
    {language: language, count: .contributions.totalCount}]
}
end
""" % PROFILE_REPOSITORY


def query_activity(start: date, end: date) -> dict:
    result = subprocess.run(
        [
            "gh", "api", "graphql", "--hostname", "github.com",
            "-f", f"query={QUERY}",
            "-f", f"login={LOGIN}",
            "-f", f"from={start.isoformat()}T00:00:00Z",
            "-f", f"to={end.isoformat()}T23:59:59Z",
            "-F", f"repos={MAX_REPOSITORIES}",
            "--jq", FILTER,
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    return json.loads(result.stdout)


def collect_activity(start: date, end: date) -> tuple[Counter[str], Counter[str]]:
    result = query_activity(start, end)
    if not result["complete"]:
        if start == end:
            raise RuntimeError(f"GitHub contribution groups are incomplete for {start.isoformat()}")
        midpoint = start + (end - start) // 2
        early_commits, early_prs = collect_activity(start, midpoint)
        late_commits, late_prs = collect_activity(midpoint + timedelta(days=1), end)
        return early_commits + late_commits, early_prs + late_prs

    commits: Counter[str] = Counter()
    pull_requests: Counter[str] = Counter()
    for row in result["commits"]:
        commits[row["language"]] += row["count"]
    for row in result["pullRequests"]:
        pull_requests[row["language"]] += row["count"]
    return commits, pull_requests


def chart_rows(commits: Counter[str], pull_requests: Counter[str]) -> list[tuple[str, int, int]]:
    languages = sorted(
        commits.keys() | pull_requests.keys(),
        key=lambda language: (-commits[language], -pull_requests[language], language.casefold()),
    )
    if len(languages) <= 6:
        return [(language, commits[language], pull_requests[language]) for language in languages]

    shown, remaining = languages[:5], languages[5:]
    return [(language, commits[language], pull_requests[language]) for language in shown] + [
        ("Other languages", sum(commits[l] for l in remaining), sum(pull_requests[l] for l in remaining)),
    ]


def draw_value(x: int, y: int, count: int, maximum: int, paint: str, delay: int) -> str:
    width = round(188 * count / maximum, 1)
    return (
        f'<rect x="{x}" y="{y - 16}" width="188" height="14" rx="3" fill="#49364b"/>'
        f'<rect class="bar" style="--delay:{delay}ms" x="{x}" y="{y - 16}" '
        f'width="{width}" height="14" rx="3" fill="{paint}"/>'
        f'<text x="{x + 244}" y="{y}" text-anchor="end" class="count">{count:,}</text>'
    )


def render_card(
    commits: Counter[str],
    pull_requests: Counter[str],
    start: date,
    end: date,
) -> str:
    rows = chart_rows(commits, pull_requests)
    max_commits = max((row[1] for row in rows), default=0) or 1
    max_pull_requests = max((row[2] for row in rows), default=0) or 1
    row_markup = []
    for index, (language, commit_count, pr_count) in enumerate(rows):
        y = 186 + index * 43
        row_markup.append(
            f'    <text x="40" y="{y}" class="language">{escape(language)}</text>\n'
            f'    {draw_value(337, y, commit_count, max_commits, "#96dfbc", index * 75)}\n'
            f'    {draw_value(667, y, pr_count, max_pull_requests, "#f88169", index * 75 + 100)}\n'
            f'    <path d="M40 {y + 15}H920" stroke="#49364b"/>'
        )
    if not rows:
        row_markup.append('    <text x="40" y="191" class="language">No public activity in this period.</text>')

    chart = "\n".join(row_markup)
    height = 234 + max(1, len(rows)) * 43
    description = " ".join(
        f"{language}: {commit_count} commit{'s' if commit_count != 1 else ''}, "
        f"{pr_count} opened pull request{'s' if pr_count != 1 else ''}."
        for language, commit_count, pr_count in rows
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">
  <title id="title">Public activity by language</title>
  <desc id="desc">GitHub contribution counts in public repositories from {start} through {end}, excluding this profile repository. Each contribution is grouped by its repository’s primary language. {escape(description)}</desc>
  <style>
    text {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .language, .count {{ fill: #fbebd3; font-size: 26px; font-weight: 650; }}
    .count {{ font-variant-numeric: tabular-nums; }}
    @media (prefers-reduced-motion: no-preference) {{
      .bar {{
        transform-box: fill-box;
        transform-origin: left center;
        animation: draw-bar 9s cubic-bezier(.2,.65,.32,1) var(--delay) infinite both;
      }}
      @keyframes draw-bar {{
        0%, 100% {{ transform: scaleX(0); }}
        12%, 94% {{ transform: scaleX(1); }}
      }}
    }}
  </style>
  <defs>
    <pattern id="halftone" width="10" height="10" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.4" fill="#703b4b"/>
    </pattern>
    <clipPath id="clip"><path d="M4 4H956V98H4Z"/></clipPath>
  </defs>
  <path fill="#211829" d="M4 4H956V{height - 4}H4Z"/>
  <path fill="#f88169" d="M4 4H956V98H4Z"/>
  <g clip-path="url(#clip)">
    <path fill="#ee9a78" d="M729 0H958V101H665Z"/>
    <path fill="url(#halftone)" d="M729 0H960V101H665Z" opacity=".55"/>
    <path d="M847 -18L787 101M890 -18L830 101M944 -18L884 101" fill="none" stroke="#703b4b" stroke-width="5" opacity=".5"/>
  </g>
  <path d="M4 98H956M4 4H956V{height - 4}H4Z" fill="none" stroke="#130f18" stroke-width="7" stroke-linejoin="round"/>
  <text x="40" y="63" fill="#211829" font-size="41" font-weight="900" letter-spacing="-1">Public activity by language</text>
  <text x="913" y="61" fill="#211829" text-anchor="end" font-size="24" font-weight="850">LAST 365 DAYS</text>
  <text x="40" y="140" fill="#fbebd3" font-size="25" font-weight="800">Primary language</text>
  <text x="337" y="140" fill="#96dfbc" font-size="25" font-weight="800">Commits</text>
  <text x="581" y="140" fill="#96dfbc" text-anchor="end" font-size="25" font-weight="800">{sum(commits.values()):,}</text>
  <text x="667" y="140" fill="#f88169" font-size="25" font-weight="800">PRs opened</text>
  <text x="911" y="140" fill="#f88169" text-anchor="end" font-size="25" font-weight="800">{sum(pull_requests.values()):,}</text>
  <path d="M40 155H920" stroke="#865569" stroke-width="2"/>
{chart}
  <text x="40" y="{height - 56}" fill="#f3c5a9" font-size="22">GitHub contributions grouped by each public repository’s primary language.</text>
  <text x="40" y="{height - 24}" fill="#f3c5a9" font-size="22">{start} to {end} (UTC) · Excludes this profile repository</text>
</svg>
"""


def main() -> None:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=WINDOW_DAYS - 1)
    commits, pull_requests = collect_activity(start, end)
    OUTPUT.write_text(render_card(commits, pull_requests, start, end), encoding="utf-8")


if __name__ == "__main__":
    main()
