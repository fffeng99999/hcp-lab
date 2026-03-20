from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analysis.svg_chart import multi_line_chart_svg


def parse_bool_flag(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _extract(point: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if isinstance(point, dict):
        return point.get("params", {}) or {}, point.get("metrics", {}) or {}
    return getattr(point, "params", {}) or {}, getattr(point, "metrics", {}) or {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_series(points: List[Any]) -> Tuple[List[int], List[Tuple[str, List[float]]]]:
    grouped: Dict[Tuple[int, int], List[float]] = {}
    nodes_set = set()
    tx_set = set()
    for point in points:
        params, metrics = _extract(point)
        nodes = _to_int(params.get("nodes"), 0)
        tx = _to_int(params.get("tx"), 0)
        if nodes <= 0 or tx <= 0:
            continue
        tps = _to_float(metrics.get("tps"), 0.0)
        if tps <= 0:
            duration_s = _to_float(metrics.get("duration_s"), 0.0)
            if duration_s > 0:
                tps = tx / duration_s
        if tps <= 0:
            block_time_ms = _to_float(metrics.get("block_time_ms", metrics.get("block_time_avg_ms", 0.0)), 0.0)
            if block_time_ms > 0:
                tps = tx * 1000.0 / block_time_ms
        if tps <= 0:
            continue
        grouped.setdefault((nodes, tx), []).append(tps)
        nodes_set.add(nodes)
        tx_set.add(tx)
    tx_values = sorted(tx_set)
    node_values = sorted(nodes_set)
    series: List[Tuple[str, List[float]]] = []
    for nodes in node_values:
        ys: List[float] = []
        for tx in tx_values:
            samples = grouped.get((nodes, tx), [])
            ys.append(sum(samples) / len(samples) if samples else 0.0)
        series.append((f"nodes={nodes}", ys))
    return tx_values, series


def _grouped_bar_chart_svg(
    x_values: List[int],
    series: List[Tuple[str, List[float]]],
    title: str,
    x_label: str,
    y_label: str,
    width: int = 960,
    height: int = 560,
) -> str:
    if not x_values or not series:
        return ""
    if any(len(ys) != len(x_values) for _, ys in series):
        return ""
    y_max = max(max(ys) for _, ys in series)
    if y_max <= 0:
        y_max = 1.0
    y_min = 0.0
    padding_left = 80
    padding_right = 210
    padding_top = 60
    padding_bottom = 78
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    n_groups = len(x_values)
    n_series = len(series)
    if n_groups == 0 or n_series == 0:
        return ""
    group_w = chart_width / n_groups
    inner_margin = min(16.0, group_w * 0.2)
    usable_w = max(group_w - inner_margin * 2, group_w * 0.4)
    gap = min(4.0, usable_w * 0.08)
    bar_w = (usable_w - gap * (n_series - 1)) / n_series if n_series > 1 else usable_w * 0.6
    if bar_w < 1:
        bar_w = 1

    def scale_y(v: float) -> float:
        return padding_top + (y_max - v) / (y_max - y_min) * chart_height

    ticks = 5
    y_ticks = []
    for i in range(ticks + 1):
        yv = y_min + (y_max - y_min) * i / ticks
        y_ticks.append((yv, scale_y(yv)))

    labels = []
    for idx, x_val in enumerate(x_values):
        cx = padding_left + idx * group_w + group_w / 2
        labels.append(
            f'<text x="{cx:.2f}" y="{padding_top + chart_height + 28}" font-size="12" text-anchor="middle">{x_val}</text>'
        )
    for yv, y_pos in y_ticks:
        labels.append(
            f'<text x="{padding_left - 12}" y="{y_pos + 4:.2f}" font-size="12" text-anchor="end">{yv:.2f}</text>'
        )

    palette = ["#1976d2", "#d32f2f", "#388e3c", "#f57c00", "#7b1fa2", "#00796b", "#5d4037", "#455a64"]
    bars = []
    legend = []
    legend_x = padding_left + chart_width + 20
    legend_y = padding_top + 12
    for s_idx, (name, ys) in enumerate(series):
        color = palette[s_idx % len(palette)]
        for g_idx, y in enumerate(ys):
            x0 = padding_left + g_idx * group_w + inner_margin + s_idx * (bar_w + gap)
            y0 = scale_y(y)
            h = padding_top + chart_height - y0
            bars.append(
                f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}" />'
            )
        ly = legend_y + s_idx * 18
        legend.append(f'<rect x="{legend_x}" y="{ly - 10}" width="12" height="12" fill="{color}" />')
        legend.append(f'<text x="{legend_x + 18}" y="{ly}" font-size="12" text-anchor="start">{name}</text>')

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="none"/>
  <text x="{width / 2}" y="30" font-size="16" text-anchor="middle">{title}</text>
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" stroke="#333" />
  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" stroke="#333" />
  {"".join(bars)}
  {"".join(labels)}
  <text x="{width / 2}" y="{height - 16}" font-size="12" text-anchor="middle">{x_label}</text>
  <text x="20" y="{height / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 20 {height / 2})">{y_label}</text>
  {"".join(legend)}
</svg>
""".strip()


def append_tps_vs_tx_by_nodes_chart(
    figures: List[str],
    points: List[Any],
    output_dir: Path,
    figures_dir: Optional[Path] = None,
    line_figure_name: str = "exp_tps_vs_tx_by_nodes_line.svg",
    bar_figure_name: str = "exp_tps_vs_tx_by_nodes_bar.svg",
    title: str = "性能曲线（TPS）",
    line_chart: bool = True,
    bar_chart: bool = True,
) -> None:
    target_figures_dir = figures_dir or (output_dir / "figures")
    target_figures_dir.mkdir(parents=True, exist_ok=True)
    tx_values, series = _build_series(points)
    if not tx_values or not series:
        return
    if line_chart:
        line_svg = multi_line_chart_svg([float(tx) for tx in tx_values], series, title, "交易数量", "性能(TPS)")
        if line_svg:
            line_path = target_figures_dir / line_figure_name
            line_path.write_text(line_svg, encoding="utf-8")
            rel = str(line_path.relative_to(output_dir))
            if rel not in figures:
                figures.append(rel)
    if bar_chart:
        bar_svg = _grouped_bar_chart_svg(tx_values, series, title.replace("曲线", "柱状图"), "交易数量", "性能(TPS)")
        if bar_svg:
            bar_path = target_figures_dir / bar_figure_name
            bar_path.write_text(bar_svg, encoding="utf-8")
            rel = str(bar_path.relative_to(output_dir))
            if rel not in figures:
                figures.append(rel)
