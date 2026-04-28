#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path
from typing import List


def parse_int_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def main():
    parser = argparse.ArgumentParser(description='实验十：Raft CFT 共识性能建模')
    parser.add_argument('--nodes', type=str, default='4,8,16,32')
    parser.add_argument('--tps', type=str, default='1000,2000,3000')
    parser.add_argument('--tx', type=int, default=3000)
    parser.add_argument('--election-timeout-ms', type=float, default=150.0)
    parser.add_argument('--heartbeat-interval-ms', type=float, default=50.0)
    parser.add_argument('--election-timeout-range-ms', type=float, default=150.0)
    parser.add_argument('--snapshot-distance', type=int, default=10000)
    parser.add_argument('--max-log-entries', type=int, default=500)
    parser.add_argument('--message-bytes', type=int, default=256)
    parser.add_argument('--base-latency-ms', type=float, default=1.0)
    parser.add_argument('--jitter-ms', type=float, default=0.5)
    parser.add_argument('--faulty-ratio', type=float, default=0)
    parser.add_argument('--out', type=str, default='experiments/exp10_raft/report')
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

    print(f'Raft Experiment')
    print(f'Nodes: {node_list}')
    print(f'TPS: {tps_list}')
    print(f'Total txs: {args.tx}')
    print(f'Output: {output_dir}')

    results = []
    for n in node_list:
        for tps in tps_list:
            quorum = n // 2 + 1
            base_latency = args.base_latency_ms
            jitter = args.jitter_ms
            append_entries_latency = (base_latency + jitter) * 2

            # 正常路径：Leader AppendEntries + Followers 回复
            block_time_ms = append_entries_latency
            messages_per_block = 2 * (n - 1)
            heartbeat_messages = 0
            elections = 0
            election_ms = 0.0

            # 概率故障模拟：以 faulty_ratio 概率触发 Leader 崩溃选举
            if random.random() < args.faulty_ratio:
                elections += 1
                # 随机选举超时 [T, T+Range]
                election_timeout = args.election_timeout_ms + random.random() * args.election_timeout_range_ms
                vote_latency = base_latency + jitter
                election_ms = election_timeout + vote_latency
                block_time_ms += election_ms
                # RequestVote 广播 + 收集 Majority 投票回复
                messages_per_block += (n - 1) + (quorum - 1)

            # 心跳：Leader 每 HeartbeatInterval 广播一次
            # 假设每块间隔 = block_time_ms，期间的心跳轮数
            if block_time_ms > 0 and args.heartbeat_interval_ms > 0:
                heartbeats_per_block = max(0, int(block_time_ms / args.heartbeat_interval_ms))
            else:
                heartbeats_per_block = 0
            heartbeat_messages = heartbeats_per_block * (n - 1)
            total_messages = messages_per_block + heartbeat_messages

            if tps > 0:
                actual_tps = 1000.0 / block_time_ms if block_time_ms > 0 else tps
            else:
                actual_tps = 0

            results.append({
                'nodes': n,
                'target_tps': tps,
                'actual_tps': round(actual_tps, 2),
                'block_time_ms': round(block_time_ms, 4),
                'append_entries_ms': round(append_entries_latency / 2, 4),
                'replication_ms': round(append_entries_latency / 2, 4),
                'election_ms': round(election_ms, 4),
                'elections': elections,
                'heartbeat_messages': heartbeat_messages,
                'total_messages': total_messages,
                'comm_bytes': total_messages * args.message_bytes,
                'quorum': quorum,
                'election_timeout_ms': args.election_timeout_ms,
                'heartbeat_interval_ms': args.heartbeat_interval_ms,
                'snapshot_distance': args.snapshot_distance,
                'max_log_entries': args.max_log_entries,
                'message_bytes': args.message_bytes,
                'base_latency_ms': args.base_latency_ms,
                'jitter_ms': args.jitter_ms,
                'faulty_ratio': args.faulty_ratio,
            })

    with open(output_dir / 'metrics.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f'Results: {len(results)} configurations')
    print(f'Output written to {output_dir / "metrics.json"}')
    print('Experiment completed successfully')


if __name__ == '__main__':
    main()
