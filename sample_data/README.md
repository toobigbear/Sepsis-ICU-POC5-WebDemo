# sample_data/ 目录说明

本目录是 **POC-5 自带的示例产物**，作用只有一个：
在外部 POC1~POC4 工程路径尚未配置好时，让 Web 页面可以正常打开、预览渲染效果。

## 内容清单

| 文件 | 来源 | 说明 |
|---|---|---|
| `poc_agent/sim_icu_data.json` | 用户提供的真实产物副本 | 三名模拟患者（SIM_P001/002/003）基线与当前生命体征 |
| `poc_agent/alert_cards/his_alert_card_SIM_P001.txt` | 用户提供的真实产物副本 | SIM_P001 文本版预警卡片（L3 高危） |
| `poc_agent/alert_cards/his_alert_card_SIM_P002.txt` | 用户提供的真实产物副本 | SIM_P002 文本版预警卡片（L2 中危） |
| `poc_agent/agent_trace.jsonl` | **POC-5 构造的格式示例** | 每行带 `"_origin": "poc5_sample"` 标记，按需求文档描述的九步闭环流程构造，仅用于演示审计页渲染 |
| `lakehouse/snapshots_metadata.json` | **POC-5 构造的格式示例** | 带 `_origin: poc5_sample_format_example` 标记，演示 Iceberg 快照元数据的识别格式 |
| `lakehouse/fusion_report.json` | **POC-5 构造的格式示例** | 同上，演示多模态融合统计报告的识别格式 |

## 重要提醒

1. 正式对外演示时，请在项目根目录 `config.py` 中：
   - 把 `POC_AGENT_OUTPUT_DIR` 指向你本机 POC3/4 Agent 工程的真实产物目录；
   - 把 `POC2_LAKEHOUSE_OUTPUT_DIR` 指向你本机 POC2 湖仓工程的真实产物目录；
   - 把 `USE_SAMPLE_FALLBACK` 改为 `False`（禁用示例回退，避免误用示例数据）。
2. 页面读取示例产物时，页面上会显示黄色【自带示例产物】徽标并标注实际读取的文件路径，一目了然。
3. SIM_P003 按设计为低危静默，没有预警卡片文件，预警结果页会展示【L1 低危静默】面板——这是正常行为。
