#!/usr/bin/env python3
"""汇总 experiments/exp1~exp6 的最终报告数据。"""
import json
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENTS_DIR.parent.parent
OUT_DIR = EXPERIMENTS_DIR / "report"
OUT_MD = OUT_DIR / "summary_all.md"


def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def append_file(lines, path: Path, title: str) -> None:
    if not path.exists():
        return
    lines.append(f"\n## {title}\n")
    lines.extend(path.read_text(encoding="utf-8").strip().splitlines())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HCP 论文第四章实验总汇报告",
        "",
        f"项目根目录: `{PROJECT_ROOT}`",
        "",
        "> 最终实验数据位于 `hcp-lab/experiments/exp*/report/`；二进制、日志、nodeN 状态、loadgen CSV 等中间文件位于项目根目录 `tests/`。",
    ]
    append_file(lines, EXPERIMENTS_DIR / "exp0_cometbft_compare" / "report" / "table3_3.md", "EXP0 CometBFT 原版对比")
    append_file(lines, EXPERIMENTS_DIR / "exp1_benchmark" / "report" / "table3_4.md", "EXP1 基准对比")
    append_file(lines, EXPERIMENTS_DIR / "exp2_degradation" / "report" / "table4_3.md", "EXP2 规模退化")
    append_file(lines, EXPERIMENTS_DIR / "exp3_saturation" / "report" / "table4_4.md", "EXP3 饱和边界")
    append_file(lines, EXPERIMENTS_DIR / "exp4_group_scan" / "report" / "table4_5.md", "EXP4 分组扫描")
    append_file(lines, EXPERIMENTS_DIR / "exp4_group_scan" / "report" / "table4_6.md", "EXP4 理论复杂度")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table4_7.md", "EXP5 消融实验")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table4_8.md", "EXP5 信任评分贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table4_9.md", "EXP5 分层结构贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table4_10.md", "EXP5 轻量子层贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table4_12.md", "EXP6 吞吐边界")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table4_13.md", "EXP6 尾延迟模型")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table4_14.md", "EXP6 统计验证")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[汇总] 总报告已生成: {OUT_MD}")


if __name__ == "__main__":
    main()
