"""Render the public GitHub contribution calendar as an illustrated city map."""

import re
import sys
from datetime import date, timedelta
from html.parser import HTMLParser
from itertools import accumulate
from pathlib import Path
from typing import NamedTuple

LEVEL_COLORS = ("#392a42", "#9c4c7e", "#de6c93", "#ff996f", "#ffe2a0")
MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
GRID_X = 242
GRID_Y = 82
WEEK_PITCH = 13
DAY_PITCH = 19
CANAL_PATH = (
    "M204 284c52-23 91-61 142-52 51 9 63 46 114 49 43 2 60-49 113-50"
    "s70 28 109 28c42 0 54-30 107-32 60-3 90 40 177 23"
)


class ActivityDay(NamedTuple):
    date: date
    level: int
    count: int


class PublicCalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[date, tuple[int, str]] = {}
        self.heading: list[str] = []
        self.tooltips: dict[str, list[str]] = {}
        self.in_heading = False
        self.tooltip_target: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.in_heading |= tag == "h2" and attributes.get("id") == (
            "js-contribution-activity-description"
        )
        if tag == "tool-tip":
            target = attributes.get("for") or ""
            if target.startswith("contribution-day-component-"):
                if target in self.tooltips:
                    raise ValueError(f"Duplicate contribution tooltip {target}")
                self.tooltip_target = target
                self.tooltips[target] = []

        if tag != "td" or "ContributionCalendar-day" not in (
            attributes.get("class") or ""
        ).split():
            return

        day = date.fromisoformat(attributes.get("data-date") or "")
        level = int(attributes.get("data-level") or "-1")
        cell_id = attributes.get("id") or ""
        if day in self.days or not cell_id or not 0 <= level < len(LEVEL_COLORS):
            raise ValueError(f"Invalid public contribution cell {day}")
        self.days[day] = (level, cell_id)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self.in_heading = False
        if tag == "tool-tip":
            self.tooltip_target = None

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading.append(data)
        if self.tooltip_target is not None:
            self.tooltips[self.tooltip_target].append(data)

    def read_calendar(self) -> tuple[int, list[ActivityDay]]:
        heading = " ".join("".join(self.heading).split())
        total = re.fullmatch(r"([0-9,]+) contributions? in the last year", heading)
        dates = sorted(self.days)
        if (
            total is None
            or not 365 <= len(dates) <= 367
            or (dates[-1] - dates[0]).days != len(dates) - 1
        ):
            raise ValueError("Unable to read the public GitHub contribution calendar")
        days = []
        for day in dates:
            level, cell_id = self.days[day]
            label = " ".join("".join(self.tooltips.get(cell_id, [])).split())
            match = re.match(r"(No|[0-9,]+) contributions? on ", label)
            if match is None:
                raise ValueError(f"Unable to read contribution count for {day}")
            count = 0 if match[1] == "No" else int(match[1].replace(",", ""))
            # GitHub may compress low-activity days, but an empty day must always be level 0.
            if (count == 0) != (level == 0):
                raise ValueError(f"Contribution level and count disagree for {day}")
            days.append(ActivityDay(day, level, count))

        yearly_total = int(total[1].replace(",", ""))
        if sum(day.count for day in days) != yearly_total:
            raise ValueError("Daily contribution counts do not match GitHub's yearly total")
        return yearly_total, days


def render_map(total: int, days: list[ActivityDay]) -> str:
    first_day = days[0].date
    last_day = days[-1].date
    week_start = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    month_labels = []
    blocks = []
    week_count = (last_day - week_start).days // 7 + 1
    weekly_counts = [0] * week_count
    for day, level, count in days:
        week, weekday = divmod((day - week_start).days, 7)
        weekly_counts[week] += count
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
    grid_width = week_count * WEEK_PITCH
    counter_size = min(57, 276 // len(f"{total:,}"))
    frame_height = 77
    counter_frames = "\n".join(
        f'      <text x="19" y="{162 + frame_height * step}">{count:,}</text>'
        for step, count in enumerate(accumulate(weekly_counts, initial=0))
    )
    legend = "\n".join(
        f'    <rect x="{796 + index * 16}" y="242" width="12" height="12" rx="1" fill="{color}"/>'
        for index, color in enumerate(LEVEL_COLORS)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="281" viewBox="0 0 960 281" role="img" aria-labelledby="title desc">
  <title id="title">Contribution map · {total:,} contributions in the last year</title>
  <desc id="desc">GitHub's public activity from {first_day} through {last_day}, arranged as city blocks. Each column is a week. Pink, coral, and ivory show increasing activity.</desc>
  <style>
    .motion {{ display: none; }}
    @media (prefers-reduced-motion: no-preference) {{
      .motion {{ display: inline; }}
      .still-total {{ display: none; }}
      .total-frames {{ animation: accumulate 3.6s steps({week_count}, end) both; }}
      .scan {{ animation: scan-city 3.6s linear both; }}
      .progress {{ animation: chart-progress 3.6s linear both; }}
      .current {{ animation: drift 8s linear infinite; }}
      .boat {{
        offset-path: path('{CANAL_PATH}');
        offset-rotate: auto;
        animation: cross-river 10s linear infinite;
      }}
      @keyframes accumulate {{ to {{ transform: translateY(-{frame_height * week_count}px); }} }}
      @keyframes scan-city {{
        from {{ transform: translateX(0); opacity: 1; }}
        96% {{ opacity: 1; }}
        to {{ transform: translateX({grid_width}px); opacity: 0; }}
      }}
      @keyframes chart-progress {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
      @keyframes drift {{ to {{ stroke-dashoffset: -100; }} }}
      @keyframes cross-river {{
        from {{ offset-distance: 0%; }}
        94%, to {{ offset-distance: 100%; }}
        0%, 100% {{ opacity: 0; }}
        12%, 87% {{ opacity: 1; }}
      }}
    }}
  </style>
  <defs>
    <clipPath id="counter-window"><rect x="12" y="105" width="175" height="70"/></clipPath>
    <clipPath id="grid-window"><rect x="{GRID_X}" y="78" width="{grid_width}" height="137"/></clipPath>
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
    <path d="{CANAL_PATH}" fill="none" stroke="#83c8b4" stroke-width="2"/>
    <path class="motion current" d="{CANAL_PATH}" fill="none" stroke="#b4f3ce" stroke-width="2"
          pathLength="100" stroke-dasharray="2 9 1 13" stroke-linecap="round"/>
    <g class="motion boat" aria-hidden="true">
      <path d="M-14 2h-12m11 3h-7" fill="none" stroke="#b4f3ce" stroke-width="1.4" stroke-linecap="round"/>
      <path d="M-11-3h17l6-2-4 7H-7Z" fill="#ff9d6e" stroke="#15101a" stroke-width="1.5" stroke-linejoin="round"/>
      <path d="M-5-4h6l2-4h-7Z" fill="#fff0d5" stroke="#15101a" stroke-width="1.3"/>
    </g>
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
    <g class="motion" clip-path="url(#grid-window)" aria-hidden="true">
      <g class="scan">
        <rect x="{GRID_X}" y="78" width="{grid_width}" height="137" fill="#1e1528" opacity=".77"/>
        <path d="M{GRID_X} 79v133" stroke="#aeefca" stroke-width="2"/>
      </g>
    </g>
    <g fill="#fff0d5" font-family="Impact, Arial Narrow, Helvetica, sans-serif" font-weight="800">
      <text x="23" y="55" font-size="19">CONTRIBUTION</text>
      <text x="22" y="91" font-size="38">MAP</text>
      <text class="still-total" x="19" y="162" font-size="{counter_size}" letter-spacing="-2">{total:,}</text>
      <g class="motion" clip-path="url(#counter-window)" aria-hidden="true">
        <g class="total-frames" font-size="{counter_size}" letter-spacing="-2">
{counter_frames}
        </g>
      </g>
      <text x="24" y="186" font-size="13" letter-spacing=".5">IN THE LAST YEAR</text>
    </g>
    <g class="motion" transform="translate(24 200)" aria-hidden="true">
      <rect width="139" height="3" rx="1.5" fill="#231727"/>
      <rect class="progress" width="139" height="3" rx="1.5" fill="#fa9870"/>
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
