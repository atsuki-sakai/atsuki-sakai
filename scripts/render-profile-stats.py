"""Render a profile card from paginated GitHub repository metadata on stdin."""

import json
import sys
from collections import Counter
from html import escape
from pathlib import Path


def render_card(repository_count: int, languages: Counter[str]) -> str:
    top_languages = sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:4]
    largest_count = max(languages.values(), default=1)
    rows = []
    for index, (language, count) in enumerate(top_languages):
        y = 96 + 39 * index
        bar_width = round(292 * count / largest_count, 1)
        rows.append(
            f'    <text x="345" y="{y}">{escape(language)}</text>\n'
            f'    <rect x="552" y="{y - 14}" width="292" height="13" fill="#49364b" stroke="#130f18" stroke-width="2"/>\n'
            f'    <rect class="language-bar" style="--delay: {index * 120}ms" x="552" y="{y - 14}" width="{bar_width}" height="13" fill="#96dfbc" stroke="#130f18" stroke-width="2"/>\n'
            f'    <text x="914" y="{y}" text-anchor="end">{count}</text>'
        )
    description = ", ".join(f"{language} {count}" for language, count in top_languages)
    chart = "\n".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="261" viewBox="0 0 960 261" role="img" aria-labelledby="title desc">
  <title id="title">Public repository stats</title>
  <desc id="desc">{repository_count} repositories. Top primary languages by repository count: {escape(description)}.</desc>
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
    <text x="345" y="46" fill="#fbebd3" font-size="24" font-weight="850">Primary languages</text>
    <text x="914" y="46" fill="#f3c5a9" font-size="19" text-anchor="end">By repository count</text>
  </g>
  <g fill="#fbebd3" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="22" font-weight="600">
{chart}
  </g>
</svg>
"""


def main() -> None:
    pages = json.load(sys.stdin)
    repositories = [
        repo
        for page in pages
        for repo in page
        if not (repo["private"] or repo["fork"] or repo["archived"])
    ]
    languages = Counter(repo["language"] for repo in repositories if repo["language"])
    output = render_card(len(repositories), languages)
    Path("assets/public-repositories.svg").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
