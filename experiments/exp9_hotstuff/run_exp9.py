#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path
from typing import Dict, List


def parse_int_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def parse_float_list(value: str) -> List[float]:
    return [float(v.strip()) for v in value.split(",") if v.strip()]


def main():
    parser = argparse.ArgumentParser(description='实验九：HotStuff BFT 共识性能建模')
    parser.add_argument('--nodes', type=str, default='4,8,16,32')
    parser.add_argument('--tps', type=str, default='1000,2000,3000')
    parser.add_argument('--tx', type=int, default=3000)
    parser.add_argument('--faulty-ratio', type=str, default='0,0.1,0.2')
    parser.add_argument('--base-latency-ms', type=float, default=1.0)
    parser.add_argument('--jitter-ms', type=float, default=0.5)
    parser.add_argument('--pipeline-depth', type=int, default=3)
    parser.add_argument('--message-bytes', type=int, default=256)
    parser.add_argument('--view-timeout-ms', type=float, default=5000.0)
    parser.add_argument('--timeout-exponent', type=float, default=2.0)
    parser.add_argument('--out', type=str, default='experiments/exp9_hotstuff/report')
    parser.add_argument('--seed', type=int, default=42, help='随机种子，保证可复现')
    args = parser.parse_args()

    random.seed(args.seed)
    project_root = Path(__file__).resolve().parents[3]
    out_path = Path(args.out)
    if out_path.is_absolute():
        output_dir = out_path
    else:
        output_dir = project_root / "hcp-lab" / out_path
    output_dir.mkdir(parents=True, exist_ok=True)

    node_list = parse_int_list(args.nodes)
    tps_list = parse_int_list(args.tps)
    fault_list = parse_float_list(args.faulty_ratio)

    print(f'HotStuff Experiment')
    print(f'Nodes: {node_list}')
    print(f'TPS: {tps_list}')
    print(f'Faulty ratios: {fault_list}')
    print(f'Total txs: {args.tx}')
    print(f'Output: {output_dir}')

    results = []
    for n in node_list:
        for tps in tps_list:
            for f_ratio in fault_list:
                f = (n - 1) // 3
                quorum = 2 * f + 1
                rtt = (args.base_latency_ms + args.jitter_ms) * 2

                # 正常路径：ChainedHotStuff Pipeline 摊薄后 ≈ 1 个消息往返
                block_time = rtt
                messages_per_block = 2 * (n - 1)
                view_changes = 0

                # 概率故障模拟：以 f_ratio 概率遇到拜占庭 leader
                if random.random() < f_ratio:
                    view_changes += 1
                    block_time += args.view_timeout_ms * (args.timeout_exponent ** view_changes)
                    # ViewChange 消息：n*(n-1) 条 timeout 消息广播
                    messages_per_block += n * (n - 1)

                if tps > 0:
                    actual_tps = 1000.0 / block_time if block_time > 0 else tps
                else:
                    actual_tps = 0

                results.append({
                    'nodes': n,
                    'faulty_ratio': f_ratio,
                    'target_tps': tps,
                    'actual_tps': round(actual_tps, 2),
                    'block_time_ms': round(block_time, 4),
                    'prepare_ms': round(rtt / 2, 4),
                    'precommit_ms': round(rtt / 2, 4),
                    'commit_ms': round(rtt / 2, 4),
                    'view_changes': view_changes,
                    'total_messages': messages_per_block,
                    'comm_bytes': messages_per_block * args.message_bytes,
                    'quorum': quorum,
                    'f': f,
                    'base_latency_ms': args.base_latency_ms,
                    'jitter_ms': args.jitter_ms,
                    'pipeline_depth': args.pipeline_depth,
                    'view_timeout_ms': args.view_timeout_ms,
                    'timeout_exponent': args.timeout_exponent,
                    'message_bytes': args.message_bytes,
                })

    with open(output_dir / 'metrics.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f'Results: {len(results)} configurations')
    print(f'Output written to {output_dir / "metrics.json"}')
    print('Experiment completed successfully')


if __name__ == '__main__':
    main()
