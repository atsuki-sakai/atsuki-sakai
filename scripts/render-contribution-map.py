"""Render the public GitHub contribution calendar as an illustrated city map."""

import re
import sys
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

LEVEL_COLORS = ("#392a42", "#9c4c7e", "#de6c93", "#ff996f", "#ffe2a0")
MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
GRID_X = 242
GRID_Y = 82
WEEK_PITCH = 13
DAY_PITCH = 19


class PublicCalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, int] = {}
        self.heading: list[str] = []
        self.in_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.in_heading |= tag == "h2" and attributes.get("id") == (
            "js-contribution-activity-description"
        )
        if tag != "td" or "ContributionCalendar-day" not in (
            attributes.get("class") or ""
        ).split():
            return

        day = date.fromisoformat(attributes.get("data-date") or "")
        level = int(attributes.get("data-level") or "-1")
        if day in self.days or not 0 <= level < len(LEVEL_COLORS):
            raise ValueError(f"Invalid public contribution cell {day}")
        self.days[day] = level

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self.in_heading = False

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading.append(data)

    def read_calendar(self) -> tuple[int, list[tuple[date, int]]]:
        heading = " ".join("".join(self.heading).split())
        total = re.fullmatch(r"([0-9,]+) contributions? in the last year", heading)
        days = sorted(self.days.items())
        if (
            total is None
            or not 365 <= len(days) <= 367
            or (days[-1][0] - days[0][0]).days != len(days) - 1
        ):
            raise ValueError("Unable to read the public GitHub contribution calendar")
        return int(total[1].replace(",", "")), days


def render_map(total: int, days: list[tuple[date, int]]) -> str:
    first_day = days[0][0]
    last_day = days[-1][0]
    week_start = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    month_labels = []
    blocks = []
    for day, level in days:
        week, weekday = divmod((day - week_start).days, 7)
        x = GRID_X + week * WEEK_PITCH
        y = GRID_Y + weekday * DAY_PITCH
        blocks.append(
            f'    <rect x="{x}" y="{y}" width="10" height="15" rx="1" '
            f'fill="{LEVEL_COLORS[level]}" data-date="{day}" data-level="{level}"/>'
        )
        if day.day == 1:
            month_labels.append(f'    <text x="{x}" y="69">{MONTH_NAMES[day.month - 1]}</text>')

    weekdays = (
        f'    <text x="234" y="{GRID_Y + row * DAY_PITCH + 11}" text-anchor="end">{name}</text>'
        for name, row in (("Mon", 1), ("Wed", 3), ("Fri", 5))
    )
    labels = "\n".join([*month_labels, *weekdays])
    city_blocks = "\n".join(blocks)
    legend = "\n".join(
        f'    <rect x="{796 + index * 16}" y="242" width="12" height="12" rx="1" fill="{color}"/>'
        for index, color in enumerate(LEVEL_COLORS)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="281" viewBox="0 0 960 281" role="img" aria-labelledby="title desc">
  <title id="title">Contribution map · {total:,} contributions in the last year</title>
  <desc id="desc">GitHub's public activity from {first_day} through {last_day}, arranged as city blocks. Each column is a week. Pink, coral, and ivory show increasing activity.</desc>
  <defs>
    <clipPath id="frame"><rect x="3" y="3" width="954" height="275" rx="10"/></clipPath>
    <pattern id="blocks" width="52" height="38" patternUnits="userSpaceOnUse" patternTransform="rotate(-12)">
      <path d="M0 0h52v38H0z M16 0v13h36 M0 23h33v15 M38 13v10" fill="none" stroke="#57384e" stroke-width="1.5"/>
    </pattern>
  </defs>
  <g clip-path="url(#frame)">
    <rect width="960" height="281" fill="#221827"/>
    <rect x="188" width="772" height="281" fill="url(#blocks)"/>
    <path d="M191 287c50-20 98-65 151-58 52 7 67 49 117 51s55-49 110-50c50-1 70 28 112 28s53-30 104-33c63-4 98 42 183 23" fill="none" stroke="#16121e" stroke-width="28"/>
    <path d="M191 287c50-20 98-65 151-58 52 7 67 49 117 51s55-49 110-50c50-1 70 28 112 28s53-30 104-33c63-4 98 42 183 23" fill="none" stroke="#397e80" stroke-width="18"/>
    <path d="M204 284c52-23 91-61 142-52 51 9 63 46 114 49 43 2 60-49 113-50s70 28 109 28c42 0 54-30 107-32 60-3 90 40 177 23" fill="none" stroke="#83c8b4" stroke-width="2"/>
    <path d="m193 235 69 1 56 45m181-8 58-54m98 59 66-58m162-8 62 59M222 47l103-19 109 12 192-17 210 19 123-18" fill="none" stroke="#170f1b" stroke-width="8"/>
    <path d="m193 235 69 1 56 45m181-8 58-54m98 59 66-58m162-8 62 59M222 47l103-19 109 12 192-17 210 19 123-18" fill="none" stroke="#b06e77" stroke-width="3"/>
    <path d="M0 0h187l20 281H0Z" fill="#4a2943" stroke="#15101a" stroke-width="5"/>
    <path d="m4 222 35-11 31 5 79-20 52 4 6 81H0Z" fill="#362238"/>
    <path d="M24 27h135" stroke="#fa9870" stroke-width="3"/>
    <rect x="209" y="51" width="735" height="169" rx="5" fill="#201724" stroke="#0e0a11" stroke-width="3"/>
    <g fill="#f6dbc6" font-family="Consolas, Menlo, monospace" font-size="10.5" font-weight="700">
{labels}
    </g>
    <g stroke="#0e0a11" stroke-width=".7">
{city_blocks}
    </g>
    <g fill="#fff0d5" font-family="Impact, Arial Narrow, Helvetica, sans-serif" font-weight="800">
      <text x="23" y="55" font-size="19">CONTRIBUTION</text>
      <text x="22" y="91" font-size="38">MAP</text>
      <text x="19" y="162" font-size="57" letter-spacing="-2">{total:,}</text>
      <text x="24" y="186" font-size="13" letter-spacing=".5">IN THE LAST YEAR</text>
    </g>
    <g fill="#f2c2af" font-family="Consolas, Menlo, monospace" font-size="11">
      <text x="24" y="233">{first_day}</text>
      <text x="24" y="252">→ {last_day}</text>
    </g>
    <rect x="741" y="233" width="203" height="30" rx="4" fill="#201724" stroke="#0e0a11" stroke-width="2"/>
    <g fill="#f6dbc6" font-family="Helvetica, sans-serif" font-size="13" font-weight="700">
      <text x="754" y="253">Less</text>
      <text x="883" y="253">More</text>
    </g>
    <g stroke="#100b13" stroke-width=".7">
{legend}
    </g>
  </g>
  <rect x="3" y="3" width="954" height="275" rx="10" fill="none" stroke="#100b13" stroke-width="6"/>
</svg>
"""


def main() -> None:
    parser = PublicCalendarParser()
    parser.feed(sys.stdin.read())
    parser.close()
    total, days = parser.read_calendar()
    Path("assets/contribution-map.svg").write_text(render_map(total, days), encoding="utf-8")


if __name__ == "__main__":
    main()
