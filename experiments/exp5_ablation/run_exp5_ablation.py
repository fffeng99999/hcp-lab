#!/usr/bin/env python3
"""实验5：关键机制消融实验。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    aggregate_runs,
    clean_report,
    ensure_dirs,
    env_int,
    env_list_int,
    run_engine_loadgen_point,
    save_json,
    save_md,
    stage_binaries,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP_NAME = "exp5_ablation"


def pct_delta(new: float, old: float) -> float:
    return (new - old) / old * 100.0 if old else 0.0


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    configs = [
        ("A_Baseline", "pbft", 0),
        ("B_tPBFT", "tpbft", 0),
        ("C_Hierarchical", "hierarchical_tpbft", 4),
        ("D_Lightweight", "hierarchical_lightweight_tpbft", 4),
        ("E_HotStuff", "hotstuff", 0),
        ("F_Raft", "raft", 0),
    ]
    nodes_list = env_list_int("EXP5_NODES", [16, 32])
    tx_count = env_int("EXP5_TXS", 1000)
    target_tps = env_int("EXP5_TARGET_TPS", 100)
    repeat = env_int("EXP_REPEAT", env_int("EXP5_REPEAT", 5))

    print(f"[EXP5] 消融实验 repeat={repeat}", flush=True)
    results = {}
    for name, engine, default_groups in configs:
        results[name] = {}
        for nodes in nodes_list:
            groups = min(default_groups, nodes) if default_groups else 0
            runs = []
            for r in range(1, repeat + 1):
                point = f"{name}_{engine}_n{nodes}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME, REPORT_DIR, point, engine, nodes, tx_count, target_tps,
                        groups=groups, binaries=binaries, paths=paths,
                    )
                )
            results[name][str(nodes)] = aggregate_runs(runs)

    save_json(results, REPORT_DIR / "summary.json")
    md7 = [
        "## 表4-7 消融实验组设计",
        "",
        "| 组 | 配置 | 16节点TPS | 16节点P99 | 32节点TPS | 32节点P99 |",
        "|----|------|-----------|-----------|-----------|-----------|",
    ]
    for name, engine, _ in configs:
        row = [name, engine]
        for nodes in [16, 32]:
            d = results.get(name, {}).get(str(nodes), {})
            row.append(f"{d.get('tps_mean', 0):.2f}±{d.get('tps_std', 0):.2f}")
            row.append(f"{d.get('p99_mean', 0):.2f}±{d.get('p99_std', 0):.2f}")
        md7.append("| " + " | ".join(row) + " |")
    save_md(md7, REPORT_DIR / "table4_7.md")

    a32 = results.get("A_Baseline", {}).get("32", {})
    b32 = results.get("B_tPBFT", {}).get("32", {})
    c32 = results.get("C_Hierarchical", {}).get("32", {})
    d32 = results.get("D_Lightweight", {}).get("32", {})

    md8 = ["## 表4-8 信任评分筛选贡献", ""]
    if a32 and b32:
        md8.extend([
            f"消息变化: {pct_delta(b32['msgs_mean'], a32['msgs_mean']):.1f}%",
            f"P99变化: {pct_delta(b32['p99_mean'], a32['p99_mean']):.1f}%",
            f"TPS变化: {pct_delta(b32['tps_mean'], a32['tps_mean']):.1f}%",
        ])
    save_md(md8, REPORT_DIR / "table4_8.md")

    md9 = ["## 表4-9 分层结构贡献", ""]
    if b32 and c32:
        md9.extend([
            f"消息变化: {pct_delta(c32['msgs_mean'], b32['msgs_mean']):.1f}%",
            f"P99变化: {pct_delta(c32['p99_mean'], b32['p99_mean']):.1f}%",
            f"TPS变化: {pct_delta(c32['tps_mean'], b32['tps_mean']):.1f}%",
        ])
    save_md(md9, REPORT_DIR / "table4_9.md")

    md10 = ["## 表4-10 轻量子层贡献", ""]
    if c32 and d32:
        md10.extend([
            f"消息变化: {pct_delta(d32['msgs_mean'], c32['msgs_mean']):.1f}%",
            f"P99变化: {pct_delta(d32['p99_mean'], c32['p99_mean']):.1f}%",
            f"TPS变化: {pct_delta(d32['tps_mean'], c32['tps_mean']):.1f}%",
        ])
    save_md(md10, REPORT_DIR / "table4_10.md")

    md11 = [
        "## 表4-11 瓶颈转移分析",
        "",
        "| 优化阶段 | 网络广播层 | CPU签名验证层 | 状态/负载层 |",
        "|----------|------------|---------------|-------------|",
        "| A->B | 验证信任筛选对消息量与延迟的影响 | 未单独优化 | loadgen/DB 保持一致 |",
        "| B->C | 验证分层结构对广播范围的压缩 | 组内/组间阶段分离 | loadgen/DB 保持一致 |",
        "| C->D | 网络层进一步受限 | 子层采用轻量 Raft 路径 | loadgen/DB 保持一致 |",
    ]
    save_md(md11, REPORT_DIR / "table4_11.md")
    print("[EXP5] 完成", flush=True)


if __name__ == "__main__":
    main()
