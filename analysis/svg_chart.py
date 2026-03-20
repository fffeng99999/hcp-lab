from typing import List, Tuple


def line_chart_svg(
    x_values: List[float],
    y_values: List[float],
    title: str,
    x_label: str,
    y_label: str,
    width: int = 800,
    height: int = 480,
) -> str:
    if not x_values or not y_values or len(x_values) != len(y_values):
        return ""
    padding_left = 70
    padding_right = 30
    padding_top = 50
    padding_bottom = 60
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    def scale_x(value: float) -> float:
        return padding_left + (value - x_min) / (x_max - x_min) * chart_width

    def scale_y(value: float) -> float:
        return padding_top + (y_max - value) / (y_max - y_min) * chart_height

    points = " ".join(f"{scale_x(x):.2f},{scale_y(y):.2f}" for x, y in zip(x_values, y_values))
    ticks = 5
    x_ticks = []
    y_ticks = []
    for i in range(ticks + 1):
        xv = x_min + (x_max - x_min) * i / ticks
        yv = y_min + (y_max - y_min) * i / ticks
        x_ticks.append((xv, scale_x(xv)))
        y_ticks.append((yv, scale_y(yv)))

    labels = []
    for value, x_pos in x_ticks:
        labels.append(f'<text x="{x_pos:.2f}" y="{padding_top + chart_height + 20}" font-size="12" text-anchor="middle">{value:.2f}</text>')
    for value, y_pos in y_ticks:
        labels.append(f'<text x="{padding_left - 10}" y="{y_pos + 4:.2f}" font-size="12" text-anchor="end">{value:.2f}</text>')

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="none"/>
  <text x="{width / 2}" y="24" font-size="16" text-anchor="middle">{title}</text>
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" stroke="#333" />
  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" stroke="#333" />
  <polyline fill="none" stroke="#1976d2" stroke-width="2" points="{points}" />
  {"".join(labels)}
  <text x="{width / 2}" y="{height - 12}" font-size="12" text-anchor="middle">{x_label}</text>
  <text x="16" y="{height / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 16 {height / 2})">{y_label}</text>
</svg>
""".strip()


def multi_line_chart_svg(
    x_values: List[float],
    series: List[Tuple[str, List[float]]],
    title: str,
    x_label: str,
    y_label: str,
    width: int = 900,
    height: int = 520,
) -> str:
    if not x_values or not series:
        return ""
    for _, ys in series:
        if not ys or len(ys) != len(x_values):
            return ""

    padding_left = 80
    padding_right = 170
    padding_top = 60
    padding_bottom = 70
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom

    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(min(ys) for _, ys in series)
    y_max = max(max(ys) for _, ys in series)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    def scale_x(value: float) -> float:
        return padding_left + (value - x_min) / (x_max - x_min) * chart_width

    def scale_y(value: float) -> float:
        return padding_top + (y_max - value) / (y_max - y_min) * chart_height

    ticks = 5
    x_ticks = []
    y_ticks = []
    for i in range(ticks + 1):
        xv = x_min + (x_max - x_min) * i / ticks
        yv = y_min + (y_max - y_min) * i / ticks
        x_ticks.append((xv, scale_x(xv)))
        y_ticks.append((yv, scale_y(yv)))

    labels = []
    for value, x_pos in x_ticks:
        labels.append(
            f'<text x="{x_pos:.2f}" y="{padding_top + chart_height + 24}" font-size="12" text-anchor="middle">{value:.2f}</text>'
        )
    for value, y_pos in y_ticks:
        labels.append(
            f'<text x="{padding_left - 12}" y="{y_pos + 4:.2f}" font-size="12" text-anchor="end">{value:.2f}</text>'
        )

    palette = ["#1976d2", "#d32f2f", "#388e3c", "#f57c00", "#7b1fa2", "#00796b"]

    polylines = []
    legend = []
    legend_x = padding_left + chart_width + 20
    legend_y = padding_top + 10
    for idx, (name, ys) in enumerate(series):
        color = palette[idx % len(palette)]
        points = " ".join(
            f"{scale_x(x):.2f},{scale_y(y):.2f}" for x, y in zip(x_values, ys)
        )
        polylines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}" />'
        )
        ly = legend_y + idx * 18
        legend.append(f'<rect x="{legend_x}" y="{ly - 10}" width="12" height="12" fill="{color}" />')
        legend.append(
            f'<text x="{legend_x + 18}" y="{ly}" font-size="12" text-anchor="start">{name}</text>'
        )

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="none"/>
  <text x="{width / 2}" y="28" font-size="16" text-anchor="middle">{title}</text>
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" stroke="#333" />
  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" stroke="#333" />
  {"".join(polylines)}
  {"".join(labels)}
  <text x="{width / 2}" y="{height - 14}" font-size="12" text-anchor="middle">{x_label}</text>
  <text x="18" y="{height / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 18 {height / 2})">{y_label}</text>
  {"".join(legend)}
</svg>
""".strip()
