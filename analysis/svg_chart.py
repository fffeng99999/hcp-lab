from typing import List


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
