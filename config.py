# -*- coding: utf-8 -*-
"""
config.py — POC-5 唯一需要用户修改的文件
=================================================
这里只配置【外部 POC1~POC4 工程的本地磁盘路径】。
本项目（POC-5）不包含、不导入、不复制 POC1~POC4 的任何业务源码；
Web 层只读取外部工程运行后落盘的产物文件（JSON / JSONL / TXT），
或通过 subprocess 调用外部工程入口脚本（由 core/runner.py 完成）。

【使用方法】把下面的路径改成你自己电脑上 POC 工程的真实路径即可，
改完保存，重启 uvicorn 生效，其他代码一律不用动。
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# 一、外部 POC 工程路径配置（★ 用户按本机实际情况修改这里 ★）
# =====================================================================

# ---- 脓毒症预警 Agent 工程（sepsis_agent_poc，提供患者/预警卡片/审计日志）----

# Agent 工程的产物输出目录：
# 目录下应有 agent_trace.jsonl、预警卡片文件（his_alert_card_SIM_P001.txt 等）
POC_AGENT_OUTPUT_DIR = r"D:\PythonProject\sepsis_agent_poc\output"

# Agent 工程入口脚本（点击网页【运行Agent评估】按钮时被 subprocess 调用）
POC_AGENT_MAIN_SCRIPT = r"D:\PythonProject\sepsis_agent_poc\main_poc.py"

# 调用入口脚本时附加的命令行参数模板，{pid} 会被替换为患者ID。
# 你的 main_poc.py 是一次跑完全部三名患者的演示脚本，不需要命令行参数 → 保持 [] 即可；
# 若将来脚本支持 `python main_poc.py --patient SIM_P001` 这种用法，再改成 ["--patient", "{pid}"]。
POC_AGENT_ARGS_TEMPLATE = []

# 运行外部脚本所用的 Python 解释器：
# 你的 sepsis_agent_poc 工程自带 .venv 虚拟环境，必须用它（依赖都装在里面）
POC_AGENT_PYTHON = r"D:\PythonProject\sepsis_agent_poc\.venv\Scripts\python.exe"

# subprocess 调用外部脚本的最长等待时间（秒），超时自动放弃并改为读取已有产物
RUN_TIMEOUT_SECONDS = 300

# ---- Iceberg 湖仓工程（iceberg-demo-wsl，提供湖仓快照元数据）----

# 湖仓产物目录：直接指向 sepsis_lakehouse 仓库目录。
# 程序会递归扫描其中的 Iceberg 表元数据（metadata/*.metadata.json，内含 snapshots 快照列表）
# 以及多模态融合统计报告 JSON（含 match_rate 字段，若有）。
POC2_LAKEHOUSE_OUTPUT_DIR = r"D:\PythonProject\iceberg-demo-wsl\sepsis_lakehouse"

# =====================================================================
# 二、自带示例产物（sample_data）回退开关
# =====================================================================
# 当上面的外部路径不存在时，是否回退读取项目自带 sample_data 目录中的
# 示例产物（保证没有外部工程时也能打开页面预览效果）。
# 正式对外演示前，建议把外部路径配好，并将本开关改为 False。
USE_SAMPLE_FALLBACK = True
SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")

# =====================================================================
# 三、展示参数（一般不用改）
# =====================================================================

# 风险分级阈值（仅用于页面展示分级颜色，与外部引擎无关）：
# 风险概率 >= 0.8 → L3 高危（橙红）；>= 0.4 → L2 中危（黄）；其余 → L1 低危（灰）
RISK_L3_THRESHOLD = 0.8
RISK_L2_THRESHOLD = 0.4

# 审计原始日志单页最多渲染行数（防止超大文件拖慢页面）
TRACE_MAX_LINES = 2000

# 全站强制免责声明（所有页面顶部固定展示，请勿删除或修改）
DISCLAIMER = (
    "【重要提示】本系统仅为科研POC原型演示，全部数据为模拟仿真患者数据；"
    "本系统不是医疗器械产品，不提供任何临床诊断、治疗建议；"
    "全部临床决策必须由主管医生负责。"
)
