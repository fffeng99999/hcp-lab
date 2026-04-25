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
	ScriptPath  string        `json:"script_path"`
	Params      []ParamSchema `json:"params"`
}

// Registry holds all known experiments.
var Registry = []Experiment{
	{
		ID:          "exp1_tx_nodes",
		Name:        "实验一：交易量 × 节点规模",
		Description: "交易量与节点规模组合实验",
		ScriptPath:  "hcp-lab/experiments/exp1_tx_nodes/run_exp1.py",
		Params: []ParamSchema{
			{Name: "nodes", Type: ParamTypeListInt, Default: "4,8,16", Description: "节点数量列表", Required: true},
			{Name: "tx", Type: ParamTypeListInt, Default: "100", Description: "交易数量列表", Required: true},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp1_tx_nodes/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp2_storage_share",
		Name:        "实验二：存储分片共享",
		Description: "存储分片共享策略性能实验",
		ScriptPath:  "hcp-lab/experiments/exp2_storage_share/run_exp2.py",
		Params: []ParamSchema{
			{Name: "shares", Type: ParamTypeListInt, Default: "2,4,8,16", Description: "分片数量列表", Required: true},
			{Name: "nodes", Type: ParamTypeInt, Default: 32, Description: "节点数量", Required: true},
			{Name: "tx", Type: ParamTypeInt, Default: 10000, Description: "交易数量", Required: true},
			{Name: "repeat", Type: ParamTypeInt, Default: 3, Description: "重复次数", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp2_storage_share/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp3_parallel_merkle",
		Name:        "实验三：并行 Merkle 哈希",
		Description: "并行 Merkle 树哈希性能实验",
		ScriptPath:  "hcp-lab/experiments/exp3_parallel_merkle/run_exp3.py",
		Params: []ParamSchema{
			{Name: "k", Type: ParamTypeListInt, Default: "1,2,4,8", Description: "并行度列表", Required: true},
			{Name: "tx", Type: ParamTypeListInt, Default: "1000,5000,10000", Description: "交易数量列表", Required: true},
			{Name: "size", Type: ParamTypeInt, Default: 512, Description: "交易大小(字节)", Required: false},
			{Name: "repeat", Type: ParamTypeInt, Default: 30, Description: "重复次数", Required: false},
			{Name: "nodes", Type: ParamTypeInt, Default: 1, Description: "节点数量", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp3_parallel_merkle/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp4_hierarchical_consensus",
		Name:        "实验四：分层共识",
		Description: "分层共识算法性能实验",
		ScriptPath:  "hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4.py",
		Params: []ParamSchema{
			{Name: "groups", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "nodes", Type: ParamTypeInt, Default: 32, Description: "节点数量", Required: true},
			{Name: "tx", Type: ParamTypeInt, Default: 10000, Description: "交易数量", Required: true},
			{Name: "repeat", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "message_bytes", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "base_latency_ms", Type: ParamTypeFloat, Default: 1.0, Description: "基础延迟(ms)", Required: false},
			{Name: "phase_weight_inner", Type: ParamTypeFloat, Default: 1.0, Description: "内部阶段权重", Required: false},
			{Name: "phase_weight_outer", Type: ParamTypeFloat, Default: 1.0, Description: "外部阶段权重", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp4_hierarchical_consensus/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp5_hierarchical_tpbft",
		Name:        "实验五：分层 tPBFT",
		Description: "分层 tPBFT 共识性能实验",
		ScriptPath:  "hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5.py",
		Params: []ParamSchema{
			{Name: "groups", Type: ParamTypeListInt, Default: "32,16,8,4,2", Description: "分组数量列表", Required: true},
			{Name: "nodes", Type: ParamTypeInt, Default: 32, Description: "节点数量", Required: true},
			{Name: "tx", Type: ParamTypeInt, Default: 100, Description: "交易数量", Required: true},
			{Name: "repeat", Type: ParamTypeInt, Default: 5, Description: "重复次数", Required: false},
			{Name: "sig_algos", Type: ParamTypeString, Default: "bls,ed25519", Description: "签名算法列表", Required: false},
			{Name: "message_bytes", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "base_latency_ms", Type: ParamTypeFloat, Default: 1.0, Description: "基础延迟(ms)", Required: false},
			{Name: "phase_weight_inner", Type: ParamTypeFloat, Default: 1.0, Description: "内部阶段权重", Required: false},
			{Name: "phase_weight_outer", Type: ParamTypeFloat, Default: 1.0, Description: "外部阶段权重", Required: false},
			{Name: "sig_gen_ms", Type: ParamTypeFloat, Default: 0.0, Description: "签名生成延迟(ms)", Required: false},
			{Name: "sig_verify_ms", Type: ParamTypeFloat, Default: 0.0, Description: "签名验证延迟(ms)", Required: false},
			{Name: "sig_agg_ms", Type: ParamTypeFloat, Default: 0.0, Description: "签名聚合延迟(ms)", Required: false},
			{Name: "outer_mode", Type: ParamTypeString, Default: "ed25519", Description: "外部签名模式", Required: false},
			{Name: "batch_verify", Type: ParamTypeBool, Default: true, Description: "批量验证", Required: false},
			{Name: "batch_size", Type: ParamTypeInt, Default: 200, Description: "批量大小", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp5_hierarchical_tpbft/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp6_alpenglow_votor",
		Name:        "实验六：Alpenglow Votor 快速终结",
		Description: "Alpenglow Votor 快速路径与慢速路径实验",
		ScriptPath:  "hcp-lab/experiments/exp6_alpenglow_votor/run_exp6.py",
		Params: []ParamSchema{
			{Name: "nodes", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "验证节点数量列表", Required: true},
			{Name: "tx", Type: ParamTypeInt, Default: 500, Description: "总交易数", Required: true},
			{Name: "faulty_ratio", Type: ParamTypeString, Default: "0,0.1,0.2", Description: "故障节点比例列表", Required: true},
			{Name: "fast_threshold", Type: ParamTypeFloat, Default: 0.8, Description: "快速路径阈值", Required: false},
			{Name: "slow_threshold", Type: ParamTypeFloat, Default: 0.6, Description: "慢速路径阈值", Required: false},
			{Name: "local_timeout_ms", Type: ParamTypeInt, Default: 150, Description: "本地异步超时(ms)", Required: false},
			{Name: "batch_size", Type: ParamTypeInt, Default: 200, Description: "每块交易批量", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp6_alpenglow_votor/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp7_pow",
		Name:        "实验七：PoW 共识",
		Description: "工作量证明共识性能实验",
		ScriptPath:  "hcp-lab/experiments/exp7_pow/run_exp7.py",
		Params: []ParamSchema{
			{Name: "nodes", Type: ParamTypeListInt, Default: "4,8,16,32", Description: "节点数量列表", Required: true},
			{Name: "duration", Type: ParamTypeInt, Default: 300, Description: "运行时长(秒)", Required: true},
			{Name: "repeat", Type: ParamTypeInt, Default: 1, Description: "重复次数", Required: false},
			{Name: "difficulty", Type: ParamTypeInt, Default: 12, Description: "挖矿难度", Required: false},
			{Name: "target_block_ms", Type: ParamTypeFloat, Default: 12000.0, Description: "目标出块间隔(ms)", Required: false},
			{Name: "tx_per_block", Type: ParamTypeInt, Default: 1000, Description: "每块交易数", Required: false},
			{Name: "target_tps", Type: ParamTypeInt, Default: 200, Description: "目标 TPS", Required: false},
			{Name: "batch_size", Type: ParamTypeInt, Default: 200, Description: "批量大小", Required: false},
			{Name: "orphan_base_rate", Type: ParamTypeFloat, Default: 0.01, Description: "孤儿块基础率", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp7_pow/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
			{Name: "line_chart", Type: ParamTypeString, Default: "true", Description: "生成折线图", Required: false},
			{Name: "bar_chart", Type: ParamTypeString, Default: "true", Description: "生成柱状图", Required: false},
		},
	},
	{
		ID:          "exp8_ibft",
		Name:        "实验八：IBFT 共识",
		Description: "IBFT 共识算法性能实验",
		ScriptPath:  "hcp-lab/experiments/exp8_ibft/run_exp8.py",
		Params: []ParamSchema{
			{Name: "nodes", Type: ParamTypeListInt, Default: "10,20,30,40,50", Description: "节点数量列表", Required: true},
			{Name: "tps", Type: ParamTypeListInt, Default: "1000,3000,5000", Description: "TPS 列表", Required: true},
			{Name: "tx", Type: ParamTypeInt, Default: 5000, Description: "总交易数", Required: true},
			{Name: "faulty_ratio", Type: ParamTypeString, Default: "0,0.1,0.2", Description: "故障节点比例列表", Required: true},
			{Name: "batch_size", Type: ParamTypeInt, Default: 200, Description: "批量大小", Required: false},
			{Name: "base_latency_ms", Type: ParamTypeFloat, Default: 1.0, Description: "基础延迟(ms)", Required: false},
			{Name: "jitter_ms", Type: ParamTypeFloat, Default: 50.0, Description: "网络抖动(ms)", Required: false},
			{Name: "timeout_ms", Type: ParamTypeFloat, Default: 150.0, Description: "超时时间(ms)", Required: false},
			{Name: "message_bytes", Type: ParamTypeInt, Default: 256, Description: "消息大小(字节)", Required: false},
			{Name: "max_rounds", Type: ParamTypeInt, Default: 8, Description: "最大轮数", Required: false},
			{Name: "out", Type: ParamTypeString, Default: "experiments/exp8_ibft/report", Description: "输出目录", Required: false},
			{Name: "loadgen_args", Type: ParamTypeString, Default: "", Description: "额外 loadgen 参数", Required: false},
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
