#!/usr/bin/env python3
"""Collect final Chapter 3 experiment tables into one markdown report."""
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


def append_file(lines: list[str], path: Path, title: str) -> None:
    if not path.exists():
        lines.extend([f"\n## {title}\n", f"> 未生成：`{path}`"])
        return
    lines.append(f"\n## {title}\n")
    lines.extend(path.read_text(encoding="utf-8").strip().splitlines())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HCP 第三章实验汇总报告",
        "",
        f"项目根目录：`{PROJECT_ROOT}`",
        "",
        "> 最终实验数据位于 `hcp-lab/experiments/exp*/report/`；二进制、日志、nodeN 数据、loadgen CSV 等中间文件位于项目根目录 `tests/`。",
    ]
    append_file(lines, EXPERIMENTS_DIR / "exp4_load_pattern" / "report" / "table3_3.md", "EXP4 Uniform与Zipf负载模式敏感性对比")
    append_file(lines, EXPERIMENTS_DIR / "exp0_cometbft_compare" / "report" / "table3_4.md", "EXP0 CometBFT 与 CometBFT-light 对比")
    append_file(lines, EXPERIMENTS_DIR / "exp1_benchmark" / "report" / "table3_5.md", "EXP1 基准对比")
    append_file(lines, EXPERIMENTS_DIR / "exp2_degradation" / "report" / "table3_6.md", "EXP2 规模退化率")
    append_file(lines, EXPERIMENTS_DIR / "exp3_saturation" / "report" / "table3_7.md", "EXP3 饱和点扫描")
    append_file(lines, EXPERIMENTS_DIR / "exp4_group_scan" / "report" / "table3_8.md", "EXP4 分组参数扫描")
    append_file(lines, EXPERIMENTS_DIR / "exp4_group_scan" / "report" / "table3_9.md", "EXP4 分层复杂度验证")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table3_10.md", "EXP5 消融实验组设计")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table3_11.md", "EXP5 信任评分贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table3_12.md", "EXP5 分层结构贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table3_13.md", "EXP5 Raft轻量子层贡献")
    append_file(lines, EXPERIMENTS_DIR / "exp5_ablation" / "report" / "table3_14.md", "EXP5 瓶颈转移记录")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_15.md", "EXP6 吞吐量饱和边界")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_16.md", "EXP6 尾延迟退化模型")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_17.md", "EXP6 ANOVA统计验证")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_18.md", "EXP6 PB-CPBQ综合评分权重")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_19.md", "EXP6 算法配置维度PB-CPBQ边界向量")
    append_file(lines, EXPERIMENTS_DIR / "exp6_modeling" / "report" / "table3_20.md", "EXP6 优化组件维度PB-CPBQ边界向量")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[SUMMARY] wrote {OUT_MD}")


if __name__ == "__main__":
    main()
