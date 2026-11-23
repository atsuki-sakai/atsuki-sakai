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
        y = 96 + 37 * index
        bar_width = round(176 * count / largest_count, 1)
        rows.append(
            f'    <text x="285" y="{y}">{escape(language)}</text>\n'
            f'    <rect x="464" y="{y - 13}" width="176" height="12" rx="6" fill="#2e4947"/>\n'
            f'    <rect x="464" y="{y - 13}" width="{bar_width}" height="12" rx="6" fill="#9de9b4"/>\n'
            f'    <text x="690" y="{y}" text-anchor="end">{count}</text>'
        )
    description = ", ".join(f"{language} {count}" for language, count in top_languages)
    chart = "\n".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="728" height="259" viewBox="0 0 728 259" role="img" aria-labelledby="title desc">
  <title id="title">Public repository stats</title>
  <desc id="desc">{repository_count} repositories. Top primary languages by repository count: {escape(description)}.</desc>
  <rect x="1" y="1" width="726" height="257" rx="17" fill="#111d24" stroke="#46615f" stroke-width="2"/>
  <path d="M255 31v196" stroke="#46615f"/>
  <g font-family="system-ui, -apple-system, Segoe UI, sans-serif">
    <text x="34" y="53" fill="#bcd1ca" font-size="19" font-weight="600">Public repositories</text>
    <text x="32" y="150" fill="#f5f9f6" font-size="78" font-weight="700">{repository_count}</text>
    <text x="34" y="194" fill="#bcd1ca" font-size="17">Excludes forks</text>
    <text x="34" y="219" fill="#bcd1ca" font-size="17">and archived repos</text>
    <text x="285" y="53" fill="#bcd1ca" font-size="19" font-weight="600">Top languages by repository count</text>
  </g>
  <g fill="#f5f9f6" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="19">
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
