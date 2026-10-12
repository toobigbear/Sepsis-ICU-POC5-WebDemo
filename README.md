# Sepsis-ICU-POC5-WebDemo

**脓毒症ICU预警AI演示系统 · 第5期工程（科研演示外壳）**

> 【重要提示】本系统仅为科研POC原型演示，全部数据为模拟仿真患者数据；本系统不是医疗器械产品，不提供任何临床诊断、治疗建议；全部临床决策必须由主管医生负责。

把 POC1~POC4 原本只能在 PyCharm 控制台看到的文本输出，转为网页可视化界面，面向临床主任演示。本工程 **不包含任何业务计算**：只做「读取产物文件 + 页面展示 + 触发外部脚本」三件事。

---

## 一、硬性隔离约束（本项目如何与 POC1~POC4 交互）

| 约束 | 本项目执行情况 |
|---|---|
| 不复制 / 不 import / 不重构 POC1~POC4 任何业务 Python 源码 | ✅ 项目内无任何 POC1~4 业务代码，仅 `main.py / config.py / core/ / templates/ / static/` |
| 只读取外部工程运行后落盘的产物文件 | ✅ `core/readers.py` 只读解析 sim_icu_data.json、预警卡片、agent_trace*.jsonl、湖仓快照/融合报告 JSON |
| 可用 subprocess 调用外部入口脚本 | ✅ `core/runner.py` 仅发起子进程并等待落盘，不含业务逻辑；调用点见 `main.py` 的 `/run-agent` 路由注释 |
| 业务计算全部由外部工程完成 | ✅ 风险引擎、RAG 检索、LLM 转译、JEV 自检、护栏均在 POC3/4 内部 |

## 二、项目目录树

```
Sepsis-ICU-POC5-WebDemo/
├── main.py                    # FastAPI 入口：5 个页面路由 + /run-agent 触发路由
├── config.py                  # ★ 唯一需要用户修改的文件：外部 POC 工程路径配置
├── requirements.txt           # pip 依赖清单（仅 4 个包）
├── README.md                  # 本文档
├── core/
│   ├── __init__.py
│   ├── readers.py             # 只读产物解析层：患者/预警卡片/审计trace/湖仓
│   └── runner.py              # subprocess 触发外部 POC 工程（仅调用，无业务逻辑）
├── templates/                 # Jinja2 模板（原生 HTML，无 Vue/React）
│   ├── base.html              # 布局：顶部固定免责声明 + 导航
│   ├── index.html             # 页面1：首页 /index
│   ├── patients.html          # 页面2：模拟患者选择 /patients
│   ├── agent_result.html      # 页面3：Agent预警结果 /agent-result
│   ├── lakehouse.html         # 页面4：湖仓一体化浏览 /lakehouse
│   ├── audit_log.html         # 页面5：审计总览 /audit-log
│   └── audit_detail.html      # 审计详情 /audit-log/detail
├── static/
│   └── style.css              # 医疗浅色风格（L3橙红 / L2黄 / L1灰）
└── sample_data/               # 自带示例产物（外部工程未配置时的预览数据）
    ├── README.md              #   示例产物来源与使用说明
    ├── poc_agent/
    │   ├── sim_icu_data.json          # 真实产物副本（用户提供）
    │   ├── alert_cards/
    │   │   ├── his_alert_card_SIM_P001.txt   # 真实产物副本（L3）
    │   │   └── his_alert_card_SIM_P002.txt   # 真实产物副本（L2）
    │   └── agent_trace.jsonl          # 格式示例（带 _origin 标记）
    └── lakehouse/
        ├── snapshots_metadata.json    # 格式示例（带 _origin 标记）
        └── fusion_report.json         # 格式示例（带 _origin 标记）
```

## 三、环境与启动

**环境要求**：Windows 笔记本 + Python 3.10（无需 Docker、无需数据库、无需登录鉴权、无需公网）。

```bash
# 1. 进入项目目录
cd Sepsis-ICU-POC5-WebDemo

# 2. 安装依赖（建议先建虚拟环境，可选）
pip install -r requirements.txt

# 3. 启动
uvicorn main:app --host 127.0.0.1 --port 8000

# 4. 浏览器访问
http://127.0.0.1:8000/
```

未配置任何外部路径时也能启动：系统自动回退读取 `sample_data/` 示例产物，页面带黄色【自带示例产物】徽标。

## 四、config.py 配置说明（正式演示前必做）

| 配置项 | 含义 | 已按你的本机路径预填 |
|---|---|---|
| `POC_AGENT_OUTPUT_DIR` | Agent 工程产物目录（预警卡片、agent_trace.jsonl） | `D:\PythonProject\sepsis_agent_poc\output` |
| `POC_AGENT_MAIN_SCRIPT` | Agent 入口脚本（网页按钮 subprocess 调用） | `D:\PythonProject\sepsis_agent_poc\main_poc.py` |
| `POC_AGENT_ARGS_TEMPLATE` | 调用脚本的参数模板；你的 main_poc.py 无参跑全量 → `[]` | `[]` |
| `POC_AGENT_PYTHON` | 运行外部脚本的解释器（用该工程自带 .venv） | `D:\PythonProject\sepsis_agent_poc\.venv\Scripts\python.exe` |
| `RUN_TIMEOUT_SECONDS` | 子进程超时秒数 | `300` |
| `POC2_LAKEHOUSE_OUTPUT_DIR` | 湖仓产物目录（递归扫描 Iceberg 表元数据与融合报告 JSON） | `D:\PythonProject\iceberg-demo-wsl\sepsis_lakehouse` |
| `USE_SAMPLE_FALLBACK` | 外部路径不存在时回退到自带示例产物；接线确认后建议改 `False` | `True` |

> 说明：`sim_icu_data.json` 无论放在 `sepsis_agent_poc\` 根目录、`data\` 还是 `output\` 子目录都能被自动找到；
> 预警卡片与 trace 文件会在产物目录和工程根目录下递归搜索（自动跳过 .venv/.git）。

改完保存，重启 uvicorn 即可，无需改动其他任何代码。

## 五、页面清单与产物依赖

| 页面 | 路由 | 读取的产物文件 |
|---|---|---|
| 首页 | `/index` | 无（展示数据源连接状态诊断） |
| 模拟患者管理 | `/patients` | `sim_icu_data.json` |
| Agent预警演示 | `/agent-result?pid=SIM_P001` | `*alert_card*SIM_P00*.(json/txt)` + `agent_trace*.jsonl` |
| 湖仓数据浏览 | `/lakehouse` | 快照元数据 JSON（含 `snapshots` 列表）、融合报告 JSON（含 `match_rate`） |
| 审计日志查看 | `/audit-log` | 全部 `agent_trace*.jsonl` + 预警卡片文件清单 |

**预警卡片解析是容错的**：
- JSON 版（优先）：自动识别 `risk_probability / probability`、`risk_score / score`、`drivers`、`checklist`、`evidence / citations`、`jev / self_check`、`risk_level` 等常见字段名；
- 文本版：自动解析「风险概率：0.98」「【风险概率】47%」两种排版，驱动因子支持列表行和整段顿号分隔两种格式；
- 分级阈值仅用于页面配色（≥0.8→L3 橙红，≥0.4→L2 黄，否则 L1 灰），阈值在 `config.py` 可调；
- 找不到卡片 → 页面展示【L1 低危静默】面板（符合 POC3/4 低危不输出卡片的设计）。

## 六、文件归属：POC-5 新增 vs 外部 POC1~4

| 归属 | 文件 | 本项目态度 |
|---|---|---|
| **POC-5 新增（本项目）** | `main.py`、`config.py`、`core/`、`templates/`、`static/`、`requirements.txt`、`README.md`、`sample_data/` | 全部新写，可随意修改 |
| **外部 POC1~4（本项目完全不触碰）** | POC1 sepsis_cardio_test 全部文件；POC2 iceberg-demo-wsl 全部文件；POC3/4 sepsis_agent_poc 全部源码与产物 | 不复制、不导入、不修改；仅【读取】其落盘产物、仅【subprocess 调用】其入口脚本 |

## 七、常见问题

1. **点击【运行Agent评估】提示"未配置入口脚本"？**
   正常。`config.py` 的 `POC_AGENT_MAIN_SCRIPT` 指向你本机真实脚本后即可在线触发；不配也不影响演示——系统会直接读取磁盘上已有产物。

2. **SIM_P003 为什么没有预警卡片？**
   设计如此：L1 低危静默，不输出临床预警卡片，仅留审计日志。结果页会显示灰色 L1 面板。

3. **湖仓页提示"未识别到快照元数据"？**
   POC2 产物需为 JSON：快照元数据含 `snapshots` 列表（每条含 `snapshot_id`、`timestamp_ms` 等），融合报告含 `match_rate`。字段名不同可参考 `core/readers.py` 的 `_norm_snapshot()` 增加别名。

4. **页面上出现黄色【自带示例产物】徽标？**
   说明当前读取的是 `sample_data/` 预览数据。配好外部路径并把 `USE_SAMPLE_FALLBACK` 改为 `False` 即可。

5. **审计日志文件很大？**
   单页最多渲染 `config.TRACE_MAX_LINES` 行（默认 2000），超出自动截断并提示。

---

**再次提示**：本系统仅为科研POC原型演示，全部数据为模拟仿真患者数据，不构成任何临床诊断或治疗建议。
