# -*- coding: utf-8 -*-
"""
core/runner.py — 通过 subprocess 触发外部 POC 工程
=================================================
【隔离契约】本模块只做一件事：以子进程方式调用 POC3/POC4 Agent 工程的
入口脚本，等待它在磁盘上产出结果文件。本模块：
  - 不 import 外部工程的任何模块；
  - 不修改外部工程的任何文件；
  - 不包含任何业务逻辑（风险计算、RAG 检索、LLM 转译等全部在外部工程中完成）。
子进程跑完后，页面再由 core/readers.py 读取新生成的产物文件渲染。
"""

import os
import subprocess

import config


def run_external_agent(pid: str) -> dict:
    """
    调用外部 Agent 工程入口脚本，对指定患者执行一次完整 Agent 流程。

    参数:
        pid: 患者ID，如 "SIM_P001"
    返回:
        dict: {
            "ran":    是否真的发起了子进程调用,
            "ok":     子进程是否成功结束(退出码为0),
            "message":给页面展示的中文提示,
            "cmd":    实际执行的命令行(便于排错),
            "stdout_tail" / "stderr_tail": 外部工程控制台输出的末尾片段
        }
    """
    script = getattr(config, "POC_AGENT_MAIN_SCRIPT", "")

    # --- 情况1：未配置外部工程入口脚本（或路径不存在）---
    # 这不是错误：需求允许"直接读取已经生成好的产物文件"。
    # 此时跳过子进程调用，页面读取磁盘上已有产物即可。
    if not script or not os.path.exists(script):
        return {
            "ran": False,
            "ok": False,
            "message": (
                "未配置外部Agent工程入口脚本（或路径不存在），已跳过脚本调用，"
                "正在读取磁盘上已有产物。如需在线触发，请在 config.py 中配置 "
                "POC_AGENT_MAIN_SCRIPT 指向你本机的 main_poc.py。"
            ),
            "cmd": "",
            "stdout_tail": "",
            "stderr_tail": "",
        }

    # --- 情况2：脚本存在，发起 subprocess 调用 ---
    # 仅调用外部入口脚本；业务逻辑全部在外部 POC 工程内部完成。
    args = [a.format(pid=pid) for a in getattr(config, "POC_AGENT_ARGS_TEMPLATE", ["{pid}"])]
    cmd = [getattr(config, "POC_AGENT_PYTHON", "python"), script] + args

    try:
        proc = subprocess.run(
            cmd,
            cwd=os.path.dirname(script),          # 在外部工程目录下运行，保证其相对路径正确
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=getattr(config, "RUN_TIMEOUT_SECONDS", 300),
        )
    except subprocess.TimeoutExpired:
        return {
            "ran": True,
            "ok": False,
            "message": f"外部工程执行超时（>{config.RUN_TIMEOUT_SECONDS}秒），已改为读取已有产物。",
            "cmd": " ".join(cmd),
            "stdout_tail": "",
            "stderr_tail": "",
        }
    except Exception as exc:  # 例如解释器不存在、权限不足等
        return {
            "ran": True,
            "ok": False,
            "message": f"外部工程调用失败：{exc}。已改为读取已有产物。",
            "cmd": " ".join(cmd),
            "stdout_tail": "",
            "stderr_tail": "",
        }

    if proc.returncode == 0:
        message = f"外部Agent工程已对 {pid} 执行完成，产物已刷新，正在读取最新结果。"
    else:
        message = (
            f"外部工程退出码为 {proc.returncode}（详见下方控制台输出），"
            "已改为读取磁盘上已有产物。"
        )
    return {
        "ran": True,
        "ok": proc.returncode == 0,
        "message": message,
        "cmd": " ".join(cmd),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
