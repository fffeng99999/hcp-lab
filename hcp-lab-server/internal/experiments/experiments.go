package experiments

import "path/filepath"

// ParamType defines the data type of an experiment parameter.
type ParamType string

const (
	ParamTypeInt     ParamType = "int"
	ParamTypeFloat   ParamType = "float"
	ParamTypeString  ParamType = "string"
	ParamTypeBool    ParamType = "bool"
	ParamTypeListInt ParamType = "list_int"
)

// ParamSchema describes a single configurable parameter.
type ParamSchema struct {
	Name        string    `json:"name"`
	Type        ParamType `json:"type"`
	Default     any       `json:"default"`
	Description string    `json:"description"`
	Required    bool      `json:"required"`
}

// Experiment defines metadata for an experiment.
type Experiment struct {
	ID          string        `json:"id"`
	Name        string        `json:"name"`
	Description string        `json:"description"`
	RunScript   string        `json:"run_script"` // e.g. experiments/exp1_tx_nodes/run_exp1_tx_nodes.sh
	ReportDir   string        `json:"report_dir"` // e.g. experiments/exp1_tx_nodes/report
	Params      []ParamSchema `json:"params"`
}

// Registry holds all known experiments.
var Registry = []Experiment{
	{
		ID:          "exp1_tx_nodes",
		Name:        "实验一：交易量 × 节点规模",
		Description: "交易量与节点规模组合实验",
		RunScript:   "hcp-lab/experiments/exp1_tx_nodes/run_exp1_tx_nodes.sh",
		ReportDir:   "hcp-lab/experiments/exp1_tx_nodes/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "TX_LIST", Type: ParamTypeListInt, Default: "100,1000,10000", Description: "交易数量列表", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 10, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp1", Description: "链ID", Required: false},
			{Name: "TARGET_TPS", Type: ParamTypeInt, Default: 300, Description: "目标TPS", Required: false},
			{Name: "CONCURRENCY", Type: ParamTypeInt, Default: 128, Description: "并发数", Required: false},
			{Name: "BATCH_SIZE", Type: ParamTypeInt, Default: 8, Description: "批量大小", Required: false},
			{Name: "COMET_TIMEOUT_COMMIT", Type: ParamTypeString, Default: "500ms", Description: "提交超时", Required: false},
			{Name: "COMET_SKIP_TIMEOUT_COMMIT", Type: ParamTypeBool, Default: true, Description: "跳过提交超时", Required: false},
			{Name: "COMET_MEMPOOL_RECHECK", Type: ParamTypeBool, Default: false, Description: "内存池重检查", Required: false},
			{Name: "COMET_TIMEOUT_PROPOSE", Type: ParamTypeString, Default: "3s", Description: "提议超时", Required: false},
			{Name: "COMET_TIMEOUT_PREVOTE", Type: ParamTypeString, Default: "1s", Description: "预投票超时", Required: false},
			{Name: "COMET_TIMEOUT_PRECOMMIT", Type: ParamTypeString, Default: "1s", Description: "预提交超时", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp1", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp2_storage_share",
		Name:        "实验二：存储分片共享",
		Description: "存储分片共享策略性能实验",
		RunScript:   "hcp-lab/experiments/exp2_storage_share/run_exp2_storage_share.sh",
		ReportDir:   "hcp-lab/experiments/exp2_storage_share/report",
		Params: []ParamSchema{
			{Name: "SHARES", Type: ParamTypeListInt, Default: "2,4,8,16", Description: "分片数量列表", Required: true},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 32, Description: "节点数量", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 10000, Description: "交易数量", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 3, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 2000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp2", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp2", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp3_parallel_merkle",
		Name:        "实验三：并行 Merkle 哈希",
		Description: "并行 Merkle 树哈希性能实验",
		RunScript:   "hcp-lab/experiments/exp3_parallel_merkle/run_exp3_parallel_merkle.sh",
		ReportDir:   "hcp-lab/experiments/exp3_parallel_merkle/report",
		Params: []ParamSchema{
			{Name: "K_LIST", Type: ParamTypeListInt, Default: "1,2,4,8", Description: "并行度列表", Required: true},
			{Name: "TX_LIST", Type: ParamTypeListInt, Default: "100,1000,10000", Description: "交易数量列表", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "节点数量", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 3000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp3", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp3", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp4_hierarchical_consensus",
		Name:        "实验四：分层共识",
		Description: "分层共识算法性能实验",
		RunScript:   "hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4_hierarchical.sh",
		ReportDir:   "hcp-lab/experiments/exp4_hierarchical_consensus/report",
		Params: []ParamSchema{
			{Name: "GROUP_LIST", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 32, Description: "节点数量", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 10000, Description: "交易数量", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 4000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp4", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp4", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp5_hierarchical_tpbft",
		Name:        "实验五：分层 tPBFT",
		Description: "分层 tPBFT 共识性能实验",
		RunScript:   "hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5_hierarchical_tpbft.sh",
		ReportDir:   "hcp-lab/experiments/exp5_hierarchical_tpbft/report",
		Params: []ParamSchema{
			{Name: "GROUP_LIST", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "SIG_ALGO_LIST", Type: ParamTypeString, Default: "bls,ed25519", Description: "签名算法列表", Required: false},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "节点数量", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 100, Description: "交易数量", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 5000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp5", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp5", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp6_alpenglow_votor",
		Name:        "实验六：Alpenglow Votor 快速终结",
		Description: "Alpenglow Votor 快速路径与慢速路径实验",
		RunScript:   "hcp-lab/experiments/exp6_alpenglow_votor/run_exp6_alpenglow_votor.sh",
		ReportDir:   "hcp-lab/experiments/exp6_alpenglow_votor/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "验证节点数量列表", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 100, Description: "总交易数", Required: true},
			{Name: "FAULTY_RATIO_LIST", Type: ParamTypeString, Default: "0,0.1,0.2", Description: "故障节点比例列表", Required: true},
			{Name: "FAST_THRESHOLD", Type: ParamTypeFloat, Default: 0.8, Description: "快速路径阈值", Required: false},
			{Name: "SLOW_THRESHOLD", Type: ParamTypeFloat, Default: 0.6, Description: "慢速路径阈值", Required: false},
			{Name: "LOCAL_TIMEOUT_MS", Type: ParamTypeInt, Default: 150, Description: "本地异步超时(ms)", Required: false},
			{Name: "BATCH_SIZE", Type: ParamTypeInt, Default: 200, Description: "每块交易批量", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 6000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp6", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp6", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp7_pow",
		Name:        "实验七：PoW 共识",
		Description: "工作量证明共识性能实验",
		RunScript:   "hcp-lab/experiments/exp7_pow/run_exp7_pow.sh",
		ReportDir:   "hcp-lab/experiments/exp7_pow/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "DURATION", Type: ParamTypeInt, Default: 100, Description: "运行时长(秒)", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "DIFFICULTY", Type: ParamTypeInt, Default: 8, Description: "挖矿难度", Required: false},
			{Name: "TARGET_BLOCK_MS", Type: ParamTypeInt, Default: 2000, Description: "目标出块间隔(ms)", Required: false},
			{Name: "TX_PER_BLOCK", Type: ParamTypeInt, Default: 100, Description: "每块交易数", Required: false},
			{Name: "TARGET_TPS", Type: ParamTypeInt, Default: 10, Description: "目标 TPS", Required: false},
			{Name: "BATCH_SIZE", Type: ParamTypeInt, Default: 100, Description: "批量大小", Required: false},
			{Name: "ORPHAN_BASE_RATE", Type: ParamTypeFloat, Default: 0.01, Description: "孤儿块基础率", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 7000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp7", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp7", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp8_ibft",
		Name:        "实验八：IBFT 共识",
		Description: "IBFT 共识算法性能实验",
		RunScript:   "hcp-lab/experiments/exp8_ibft/run_exp8_ibft.sh",
		ReportDir:   "hcp-lab/experiments/exp8_ibft/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "TARGET_TPS_LIST", Type: ParamTypeListInt, Default: "1000,3000,5000", Description: "TPS 列表", Required: true},
			{Name: "TX_TOTAL", Type: ParamTypeInt, Default: 100, Description: "总交易数", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "FAULTY_RATIO_LIST", Type: ParamTypeString, Default: "0,0.1,0.2", Description: "故障节点比例列表", Required: true},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 80, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp8", Description: "链ID", Required: false},
			{Name: "BATCH_SIZE", Type: ParamTypeInt, Default: 200, Description: "批量大小", Required: false},
			{Name: "IBFT_BASE_LATENCY_MS", Type: ParamTypeFloat, Default: 1.0, Description: "基础延迟(ms)", Required: false},
			{Name: "IBFT_JITTER_MS", Type: ParamTypeFloat, Default: 50.0, Description: "网络抖动(ms)", Required: false},
			{Name: "IBFT_TIMEOUT_MS", Type: ParamTypeFloat, Default: 150.0, Description: "超时时间(ms)", Required: false},
			{Name: "IBFT_MESSAGE_BYTES", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "IBFT_MAX_ROUNDS", Type: ParamTypeInt, Default: 8, Description: "最大轮数", Required: false},
			{Name: "CONCURRENCY", Type: ParamTypeInt, Default: 256, Description: "并发数", Required: false},
			{Name: "COMET_TIMEOUT_COMMIT", Type: ParamTypeString, Default: "500ms", Description: "提交超时", Required: false},
			{Name: "COMET_SKIP_TIMEOUT_COMMIT", Type: ParamTypeBool, Default: true, Description: "跳过提交超时", Required: false},
			{Name: "COMET_MEMPOOL_RECHECK", Type: ParamTypeBool, Default: false, Description: "内存池重检查", Required: false},
			{Name: "COMET_TIMEOUT_PROPOSE", Type: ParamTypeString, Default: "3s", Description: "提议超时", Required: false},
			{Name: "COMET_TIMEOUT_PREVOTE", Type: ParamTypeString, Default: "1s", Description: "预投票超时", Required: false},
			{Name: "COMET_TIMEOUT_PRECOMMIT", Type: ParamTypeString, Default: "1s", Description: "预提交超时", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp8", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp9_hotstuff",
		Name:        "实验九：HotStuff 共识",
		Description: "HotStuff BFT 共识算法性能实验",
		RunScript:   "hcp-lab/experiments/exp9_hotstuff/run_exp9_hotstuff.sh",
		ReportDir:   "hcp-lab/experiments/exp9_hotstuff/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "TX_TOTAL", Type: ParamTypeInt, Default: 100, Description: "总交易数", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "FAULTY_RATIO_LIST", Type: ParamTypeString, Default: "0,0.1,0.2", Description: "故障节点比例列表", Required: true},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 9000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp9", Description: "链ID", Required: false},
			{Name: "HOTSTUFF_NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "HotStuff节点数", Required: false},
			{Name: "HOTSTUFF_FAULTY_RATIO", Type: ParamTypeFloat, Default: 0, Description: "故障比例", Required: false},
			{Name: "HOTSTUFF_VIEW_TIMEOUT_MS", Type: ParamTypeFloat, Default: 5000, Description: "视图超时(ms)", Required: false},
			{Name: "HOTSTUFF_TIMEOUT_EXPONENT", Type: ParamTypeFloat, Default: 2.0, Description: "超时指数", Required: false},
			{Name: "HOTSTUFF_BASE_LATENCY_MS", Type: ParamTypeFloat, Default: 1.0, Description: "基础延迟(ms)", Required: false},
			{Name: "HOTSTUFF_JITTER_MS", Type: ParamTypeFloat, Default: 0.5, Description: "网络抖动(ms)", Required: false},
			{Name: "HOTSTUFF_MESSAGE_BYTES", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "HOTSTUFF_PIPELINE_DEPTH", Type: ParamTypeInt, Default: 3, Description: "流水线深度", Required: false},
			{Name: "HOTSTUFF_ENABLE_THRESHOLD_SIG", Type: ParamTypeBool, Default: false, Description: "启用门限签名", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp9", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp10_raft",
		Name:        "实验十：Raft 共识",
		Description: "Raft CFT 共识算法性能实验",
		RunScript:   "hcp-lab/experiments/exp10_raft/run_exp10_raft.sh",
		ReportDir:   "hcp-lab/experiments/exp10_raft/report",
		Params: []ParamSchema{
			{Name: "NODES_LIST", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "TX_TOTAL", Type: ParamTypeInt, Default: 100, Description: "总交易数", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 10000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp10", Description: "链ID", Required: false},
			{Name: "RAFT_NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "Raft节点数", Required: false},
			{Name: "RAFT_ELECTION_TIMEOUT_MS", Type: ParamTypeFloat, Default: 150, Description: "选举超时(ms)", Required: false},
			{Name: "RAFT_HEARTBEAT_INTERVAL_MS", Type: ParamTypeFloat, Default: 50, Description: "心跳间隔(ms)", Required: false},
			{Name: "RAFT_ELECTION_TIMEOUT_RANGE_MS", Type: ParamTypeFloat, Default: 150, Description: "选举超时随机范围(ms)", Required: false},
			{Name: "RAFT_SNAPSHOT_DISTANCE", Type: ParamTypeInt, Default: 10000, Description: "快照间隔", Required: false},
			{Name: "RAFT_MAX_LOG_ENTRIES_PER_RPC", Type: ParamTypeInt, Default: 500, Description: "每RPC最大日志条目", Required: false},
			{Name: "RAFT_MESSAGE_BYTES", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "RAFT_FAULTY_RATIO", Type: ParamTypeFloat, Default: 0, Description: "节点崩溃比例", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp10", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp12_hotspot_tpbft",
		Name:        "实验十二：热点账户感知分组 TPBFT",
		Description: "热点账户负载下的分层 TPBFT 分组策略对比实验",
		RunScript:   "hcp-lab/experiments/exp12_hotspot_tpbft/run_exp12.sh",
		ReportDir:   "hcp-lab/experiments/exp12_hotspot_tpbft/report",
		Params: []ParamSchema{
			{Name: "GROUP_LIST", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "STRATEGY_LIST", Type: ParamTypeString, Default: "random,hotspot", Description: "分组策略列表", Required: true},
			{Name: "ZIPF_ALPHA_LIST", Type: ParamTypeString, Default: "0.0,1.5,1.8,2.0", Description: "Zipf alpha列表", Required: true},
			{Name: "SIG_ALGO_LIST", Type: ParamTypeString, Default: "bls,ed25519", Description: "签名算法列表", Required: false},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "节点数量", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 100, Description: "交易数量", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 12000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp12", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp12", Description: "数据库前缀", Required: false},
		},
	},
	{
		ID:          "exp11_hierarchical_tpbft_parallel_block",
		Name:        "实验十一：分层 TPBFT + 并行 Merkle 块",
		Description: "分层 TPBFT 共识结合并行 Merkle 块计算的综合性能实验",
		RunScript:   "hcp-lab/experiments/exp11_hierarchical_tpbft_parallel_block/run_exp11.sh",
		ReportDir:   "hcp-lab/experiments/exp11_hierarchical_tpbft_parallel_block/report",
		Params: []ParamSchema{
			{Name: "GROUP_LIST", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "K_LIST", Type: ParamTypeListInt, Default: "1,2,4,8", Description: "并行度列表", Required: true},
			{Name: "SIG_ALGO_LIST", Type: ParamTypeString, Default: "bls,ed25519", Description: "签名算法列表", Required: false},
			{Name: "NODE_COUNT", Type: ParamTypeInt, Default: 4, Description: "节点数量", Required: true},
			{Name: "TX_COUNT", Type: ParamTypeInt, Default: 100, Description: "交易数量", Required: true},
			{Name: "REPEAT", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "PORT_OFFSET", Type: ParamTypeInt, Default: 11000, Description: "端口偏移量", Required: false},
			{Name: "CHAIN_ID", Type: ParamTypeString, Default: "hcp-exp11", Description: "链ID", Required: false},
			{Name: "LOADGEN_DB_ISOLATION", Type: ParamTypeBool, Default: true, Description: "数据库隔离", Required: false},
			{Name: "LOADGEN_DB_RESET", Type: ParamTypeBool, Default: true, Description: "数据库重置", Required: false},
			{Name: "LOADGEN_DB_SCHEMA_PREFIX", Type: ParamTypeString, Default: "exp11", Description: "数据库前缀", Required: false},
		},
	},
}

// FindByID returns an experiment by its ID.
func FindByID(id string) (*Experiment, bool) {
	for i := range Registry {
		if Registry[i].ID == id {
			return &Registry[i], true
		}
	}
	return nil, false
}

// ResolveScriptPath resolves the script path relative to the project root.
func ResolveScriptPath(projectRoot, scriptPath string) string {
	return filepath.Join(projectRoot, scriptPath)
}
