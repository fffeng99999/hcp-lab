# HCP Lab AI实验生成规则

## 系统架构概述

HCP Lab是一个分布式共识算法实验平台，支持多种共识算法的性能测试和验证。系统采用可扩展架构，通过统一的实验接口规范，使AI能够生成符合标准的新实验。

## 核心设计原则

### 1. 可扩展性
- 所有实验必须遵循统一的接口规范
- 通用参数通过标准接口传递
- 实验特定参数通过扩展接口传递
- 实验脚本必须能够独立运行

### 2. 参数分类

#### 通用参数（所有实验共享）
| 参数名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| NODE_COUNT | int | 节点数量 | 32 |
| TX_COUNT | int | 交易数量 | 10000 |
| PORT_OFFSET | int | 端口偏移量 | 1000 |
| CHAIN_ID | string | 链ID | hcp-exp |
| REPEAT | int | 重复次数 | 3 |
| LOADGEN_DB_ISOLATION | bool | 数据库隔离 | true |
| LOADGEN_DB_RESET | bool | 数据库重置 | true |
| LOADGEN_DB_SCHEMA_PREFIX | string | 数据库前缀 | exp |

#### 实验特定参数
每个实验可以定义自己的特定参数，但必须遵循以下类型规范：
- int: 整数
- float: 浮点数
- string: 字符串
- bool: 布尔值
- list_int: 逗号分隔的整数列表

### 3. 实验结构规范

每个实验必须包含以下文件：
```
experiments/expX_name/
├── run_expX_name.sh          # 环境变量配置脚本
├── test_expX_name.sh         # 实验执行脚本
├── run_expX.py               # Python实验逻辑
├── README.md                 # 实验说明
└── report/                   # 实验结果目录
    ├── figures/              # 图表目录
    ├── result.json           # 实验结果数据
    └── report.md             # 实验报告
```

### 4. 脚本规范

#### run_expX_name.sh
- 设置环境变量（实验参数）
- 调用test_expX_name.sh
- 所有参数必须有默认值

#### test_expX_name.sh
- 构建项目（hcp-loadgen）
- 设置实验路径
- 调用Python实验脚本
- 传递参数和loadgen参数

### 5. Python实验规范

- 使用argparse接收参数
- 支持--out指定输出目录
- 生成result.json包含实验指标
- 生成SVG图表
- 生成report.md实验报告

### 6. 结果数据规范

#### result.json格式
```json
{
  "experiment_id": "expX_name",
  "duration_s": 120.5,
  "tps": 1500.0,
  "avg_confirm_time_ms": 250.0,
  "p99_confirm_time_ms": 500.0,
  "block_count": 100,
  "tx_count": 10000,
  "node_count": 32,
  "metrics": {
    "custom_metric_1": 100,
    "custom_metric_2": 200
  }
}
```

## AI生成实验要求

### 输入格式
AI接收以下输入：
1. 实验名称和描述
2. 实验类型（共识算法/存储/网络/其他）
3. 实验特定参数列表
4. 实验目标指标

### 输出格式
AI必须输出符合以下JSON格式的实验配置：
```json
{
  "id": "expX_name",
  "name": "实验X：实验名称",
  "description": "实验描述",
  "type": "consensus|storage|network|other",
  "params": [
    {
      "name": "PARAM_NAME",
      "type": "int|float|string|bool|list_int",
      "default": "默认值",
      "description": "参数说明",
      "required": true
    }
  ],
  "common_params": {
    "NODE_COUNT": 32,
    "TX_COUNT": 10000,
    "PORT_OFFSET": 1000,
    "CHAIN_ID": "hcp-expX",
    "REPEAT": 3
  },
  "metrics": [
    {
      "name": "tps",
      "description": "每秒交易处理数",
      "unit": "tx/s"
    }
  ]
}
```

## 实验生成流程

1. 用户通过前端输入实验需求
2. 后端调用AI API生成实验配置
3. AI返回符合规范的实验JSON
4. 后端验证实验配置
5. 注册到实验列表
6. 用户可以在实验列表中配置和运行

## 验证规则

生成的实验必须通过以下验证：
1. 实验ID唯一
2. 参数类型正确
3. 脚本路径有效
4. 结果目录存在
5. 指标定义完整
