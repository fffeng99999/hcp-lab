from pathlib import Path
from typing import List, Tuple


def plot_scaling(points: List[Tuple[float, float]], output: Path, title: str = "Scaling") -> None:
    svg = render_line_chart(points, title, "节点数", "加速比")
    output.write_text(svg, encoding="utf-8")


def render_line_chart(points: List[Tuple[float, float]], title: str, x_label: str, y_label: str) -> str:
    width, height = 800, 480
    padding = 60
    xs = [p[0] for p in points] or [0]
    ys = [p[1] for p in points] or [0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_x == max_x:
        max_x += 1
    if min_y == max_y:
        max_y += 1

    def scale_x(x: float) -> float:
        return padding + (x - min_x) / (max_x - min_x) * (width - 2 * padding)

    def scale_y(y: float) -> float:
        return height - padding - (y - min_y) / (max_y - min_y) * (height - 2 * padding)

    path = " ".join(f"{scale_x(x):.2f},{scale_y(y):.2f}" for x, y in points)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="30" font-size="18" text-anchor="middle">{title}</text>
<line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#333"/>
<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" stroke="#333"/>
<text x="{width/2}" y="{height-15}" font-size="12" text-anchor="middle">{x_label}</text>
<text x="20" y="{height/2}" font-size="12" text-anchor="middle" transform="rotate(-90 20 {height/2})">{y_label}</text>
<polyline fill="none" stroke="#00b894" stroke-width="2" points="{path}"/>
</svg>"""
