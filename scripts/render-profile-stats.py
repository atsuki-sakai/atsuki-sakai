"""Render aggregate language bytes and a count of public GitHub repositories."""

import argparse
import json
import os
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html import escape
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def render_card(
    repository_count: int, languages: Counter[str], include_private: bool
) -> str:
    top_languages = sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:4]
    total_bytes = languages.total()
    scope = "Public + accessible private" if include_private else "Public only"
    rows = []
    summaries = []
    for index, (language, byte_count) in enumerate(top_languages):
        y = 96 + 39 * index
        percentage = 100 * byte_count / total_bytes
        bar_width = round(273 * percentage / 100, 1)
        percentage_label = f"{percentage:.1f}%"
        rows.append(
            f'    <text x="345" y="{y}">{escape(language)}</text>\n'
            f'    <rect x="552" y="{y - 14}" width="273" height="13" '
            'fill="#49364b" stroke="#130f18" stroke-width="2"/>\n'
            f'    <rect class="language-bar" style="--delay: {index * 120}ms" '
            f'x="552" y="{y - 14}" width="{bar_width}" height="13" '
            'fill="#96dfbc" stroke="#130f18" stroke-width="2"/>\n'
            f'    <text x="914" y="{y}" text-anchor="end">{percentage_label}</text>'
        )
        summaries.append(f"{language} {percentage_label}")
    description = ", ".join(summaries) or "No language data"
    chart = "\n".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="261" viewBox="0 0 960 261" role="img" aria-labelledby="title desc">
  <title id="title">Public repository count and top languages</title>
  <desc id="desc">{repository_count} public repositories. Top languages by aggregate bytes, {scope.lower()}: {escape(description)}.</desc>
  <style>
    @media (prefers-reduced-motion: no-preference) {{
      .language-bar {{
        transform-box: fill-box;
        transform-origin: left center;
        animation: draw-bar 8s cubic-bezier(.35,.1,.25,1) var(--delay) infinite;
      }}
      .speed-lines {{
        animation: sweep-lines 8s ease-out infinite;
      }}
      @keyframes draw-bar {{
        0%, 24%, 100% {{ transform: scaleX(1); }}
        7% {{ transform: scaleX(.05); }}
      }}
      @keyframes sweep-lines {{
        0%, 24%, 100% {{ opacity: .42; transform: translateX(0); }}
        7% {{ opacity: .12; transform: translateX(-12px); }}
        15% {{ opacity: .75; transform: translateX(7px); }}
      }}
    }}
  </style>
  <defs>
    <pattern id="halftone" width="10" height="10" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.4" fill="#713742"/>
    </pattern>
    <clipPath id="stat-panel">
      <path d="M4 4H330L288 257H4Z"/>
    </clipPath>
  </defs>
  <path fill="#211829" d="M4 4H956V257H4Z"/>
  <path fill="#f88169" d="M4 4H330L288 257H4Z"/>
  <path fill="url(#halftone)" clip-path="url(#stat-panel)" d="M168 0H335V261H122L168 216Z" opacity=".34"/>
  <path class="speed-lines" d="M173 111h95m-79 18h67m-103 18h93" fill="none" stroke="#713742" stroke-width="4" opacity=".42"/>
  <path d="M330 4L288 257M4 4H956V257H4Z" fill="none" stroke="#130f18" stroke-width="7" stroke-linejoin="round"/>
  <path d="M345 64H914" stroke="#8a5366" stroke-width="2"/>
  <g font-family="system-ui, -apple-system, Segoe UI, sans-serif">
    <text x="33" y="48" fill="#211829" font-size="23" font-weight="850" letter-spacing="1">PUBLIC</text>
    <text x="33" y="75" fill="#211829" font-size="23" font-weight="850" letter-spacing="1">REPOSITORIES</text>
    <text x="28" y="166" fill="#fbebd3" stroke="#211829" stroke-width="3" paint-order="stroke fill" font-size="90" font-weight="900" letter-spacing="-3">{repository_count}</text>
    <text x="33" y="209" fill="#211829" font-size="20" font-weight="650">Excludes forks and</text>
    <text x="33" y="233" fill="#211829" font-size="20" font-weight="650">archived repositories</text>
    <text x="345" y="46" fill="#fbebd3" font-size="24" font-weight="850">Top languages</text>
    <text x="914" y="46" fill="#f3c5a9" font-size="19" text-anchor="end">{scope} · by bytes</text>
  </g>
  <g fill="#fbebd3" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="22" font-weight="600">
{chart}
  </g>
</svg>
"""


def read_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    result = subprocess.run(
        ["gh", "auth", "token", "--hostname", "github.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise SystemExit("Set GH_TOKEN or sign in to github.com via gh auth login.")
    return result.stdout.strip()


def get_api(path: str, token: str, **parameters):
    query = "?" + urlencode(parameters) if parameters else ""
    request = Request(
        f"https://api.github.com/{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=15) as response:
        return json.load(response), 'rel="next"' in response.headers.get("Link", "")


def repository_names(
    owner: str, token: str, *, private: bool = False
) -> list[str]:
    path = "user/repos" if private else f"users/{quote(owner, safe='')}/repos"
    parameters = (
        {"affiliation": "owner", "visibility": "private"}
        if private
        else {"type": "owner"}
    )
    names = []
    page = 1
    more_pages = True
    while more_pages:
        repositories, more_pages = get_api(path, token, per_page=100, page=page, **parameters)
        names.extend(
            repo["name"]
            for repo in repositories
            if repo["owner"]["login"].lower() == owner.lower()
            and repo["private"] == private
            and not (repo["fork"] or repo["archived"])
        )
        page += 1
    return names


def language_bytes(owner: str, repositories: list[str], token: str) -> Counter[str]:
    encoded_owner = quote(owner, safe="")

    def repo_language_bytes(name: str) -> dict[str, int]:
        path = f"repos/{encoded_owner}/{quote(name, safe='')}/languages"
        result, _ = get_api(path, token)
        return result

    aggregate: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=6) as pool:
        for repo_totals in pool.map(repo_language_bytes, repositories):
            aggregate.update(repo_totals)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--include-private", action="store_true")
    args = parser.parse_args()
    token = read_token()
    try:
        public = repository_names(args.owner, token)
        languages = language_bytes(
            args.owner, [name for name in public if name.lower() != args.owner.lower()], token
        )
        if args.include_private:
            private = repository_names(args.owner, token, private=True)
            private_languages = language_bytes(
                args.owner, [name for name in private if name.lower() != args.owner.lower()], token
            )
            if not private_languages:
                raise SystemExit("No eligible private repository language data was accessible.")
            languages.update(private_languages)
    except HTTPError as error:
        raise SystemExit(f"GitHub metadata request failed (HTTP {error.code}).") from None
    except (OSError, HTTPException, ValueError, TypeError, KeyError):
        raise SystemExit("GitHub metadata could not be read or parsed.") from None

    output = render_card(len(public), languages, args.include_private)
    Path("assets/public-repositories.svg").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
