# -*- coding: utf-8 -*-
"""
main.py — Sepsis-ICU-POC5-WebDemo FastAPI 入口
=================================================
科研演示外壳（第5期工程）：
  - 只读取 POC1~POC4 运行后落盘的产物文件并渲染页面；
  - 唯一与外部工程的在线交互：core/runner.py 以 subprocess 调用外部入口脚本；
  - 不 import、不复制 POC1~POC4 的任何业务源码，不含任何业务计算。

本地启动（Windows 笔记本单机，无需 Docker、无需鉴权）：
    pip install -r requirements.txt
    uvicorn main:app --host 127.0.0.1 --port 8000
浏览器访问：http://127.0.0.1:8000/
"""

import os
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from core import readers, runner

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Sepsis-ICU-POC5-WebDemo", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def render(request: Request, template: str, active: str, **ctx):
    """统一渲染入口：注入导航高亮与全站强制免责声明。"""
    ctx.update({
        "active": active,
        "disclaimer": config.DISCLAIMER,
        "msg": request.query_params.get("msg", ""),
    })
    return templates.TemplateResponse(request, template, ctx)


# ---------------------------------------------------------------------
# 页面1：首页 /index
# ---------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/index")


@app.get("/index")
def index(request: Request):
    agent_dir, agent_is_sample = readers.agent_output_dir()
    lake_dir, lake_is_sample = readers.lakehouse_dir()
    return render(
        request, "index.html", "index",
        agent_dir=agent_dir or "(未找到)",
        agent_is_sample=agent_is_sample,
        lake_dir=lake_dir or "(未找到)",
        lake_is_sample=lake_is_sample,
        config_items=readers.config_status(),
        sample_fallback=getattr(config, "USE_SAMPLE_FALLBACK", False),
    )


# ---------------------------------------------------------------------
# 页面2：模拟患者选择 /patients
# ---------------------------------------------------------------------
@app.get("/patients")
def patients(request: Request):
    sim_data, sim_path, is_sample = readers.load_sim_data()
    rows = readers.build_patient_rows(sim_data)
    icu_info = (sim_data or {}).get("icu_info", {})
    script_ready = bool(getattr(config, "POC_AGENT_MAIN_SCRIPT", "")) and \
        os.path.exists(config.POC_AGENT_MAIN_SCRIPT)
    return render(
        request, "patients.html", "patients",
        rows=rows, icu_info=icu_info,
        sim_path=sim_path or "(未找到 sim_icu_data.json)",
        is_sample=is_sample,
        script_ready=script_ready,
        main_script=getattr(config, "POC_AGENT_MAIN_SCRIPT", ""),
    )


@app.post("/run-agent")
async def run_agent(request: Request):
    """
    【选中该患者，运行Agent评估】按钮的处理入口。
    注意：这里【仅通过 subprocess 调用外部 POC3/4 工程入口脚本】（见 core/runner.py），
    业务逻辑（风险引擎、RAG 检索、LLM 转译、JEV 自检、护栏）全部在外部工程中完成；
    子进程结束后页面跳转到预警结果页，由 readers 读取新生成的产物文件渲染。
    """
    form = await request.form()
    pid = (form.get("pid") or "").strip()
    if not pid:
        return RedirectResponse("/patients?msg=" + quote("缺少患者ID，请重新选择。"),
                                status_code=303)
    result = runner.run_external_agent(pid)
    return RedirectResponse(f"/agent-result?pid={quote(pid)}&msg={quote(result['message'])}",
                            status_code=303)


# ---------------------------------------------------------------------
# 页面3：Agent预警结果 /agent-result?pid=SIM_P001
# ---------------------------------------------------------------------
@app.get("/agent-result")
def agent_result(request: Request, pid: str = ""):
    sim_data, _, is_sample = readers.load_sim_data()
    patients = {p.get("patient_id", ""): p for p in (sim_data or {}).get("patients", [])}

    # 未指定患者：展示选择列表
    if not pid:
        rows = readers.build_patient_rows(sim_data)
        return render(request, "agent_result.html", "agent",
                      pid="", patients=patients, rows=rows,
                      patient=None, card=None, is_sample=is_sample)

    patient = patients.get(pid)
    card = readers.load_alert_card(pid)
    trace_lines, trace_truncated, trace_files_n = readers.read_trace_for_patient(pid)
    return render(
        request, "agent_result.html", "agent",
        pid=pid, patients=patients, rows=None,
        patient=patient, card=card,
        is_sample=is_sample,
        trace_lines=trace_lines,
        trace_truncated=trace_truncated,
        trace_files_n=trace_files_n,
    )


# ---------------------------------------------------------------------
# 页面4：湖仓一体化浏览 /lakehouse
# ---------------------------------------------------------------------
@app.get("/lakehouse")
def lakehouse(request: Request, snapshot_id: str = ""):
    info = readers.load_lakehouse()
    snapshots = info["snapshots"]

    selected = None
    if snapshots:
        if snapshot_id:
            for s in snapshots:
                if s["snapshot_id"] == snapshot_id:
                    selected = s
                    break
        if selected is None:
            selected = snapshots[0]  # 默认展示最新快照

    # 融合报告关键指标（容错取字段）
    fusion_stats = []
    if info["fusion"]:
        f = info["fusion"]
        for label, keys in [
            ("患者样本总数", ["total_patients", "patient_count", "num_patients"]),
            ("临床记录数", ["clinical_records", "clinical_count"]),
            ("影像记录数", ["image_records", "image_count"]),
            ("临床-影像成功匹配数", ["matched", "matched_count"]),
            ("临床-影像多模态匹配率", ["match_rate", "multimodal_match_rate", "clin_image_match_rate"]),
        ]:
            val = readers._pick(f, *keys)
            if isinstance(val, float) and "率" in label:
                val = f"{val * 100:.1f}%"
            fusion_stats.append({"label": label, "value": val if val is not None else "—"})

    return render(
        request, "lakehouse.html", "lakehouse",
        info=info, snapshots=snapshots, selected=selected,
        fusion_stats=fusion_stats,
    )


# ---------------------------------------------------------------------
# 页面5：审计总览 /audit-log  +  审计详情 /audit-log/detail
# ---------------------------------------------------------------------
@app.get("/audit-log")
def audit_log(request: Request):
    records = readers.build_audit_records()
    trace_files = [readers.trace_file_summary(p) for p in readers.list_trace_files()]
    _, is_sample = readers.agent_output_dir()
    return render(
        request, "audit_log.html", "audit",
        records=records, trace_files=trace_files, is_sample=is_sample,
    )


@app.get("/audit-log/detail")
def audit_detail(request: Request, pid: str = "", file: str = ""):
    """
    审计详情：查看某次运行的完整原始审计日志。
    - ?pid=SIM_P001  → 该患者的预警卡片原文 + 跨文件筛选出的审计行
    - ?file=xxx.jsonl → 指定审计文件全文（仅限产物目录内发现的文件，防止路径穿越）
    """
    _, is_sample = readers.agent_output_dir()
    card = readers.load_alert_card(pid) if pid else None
    lines, truncated, title = [], False, ""

    if pid:
        lines, truncated, _ = readers.read_trace_for_patient(pid)
        title = f"患者 {pid} 的完整审计追踪"
    elif file:
        # 安全：只允许查看 list_trace_files() 已发现的产物文件
        allowed = {os.path.basename(p): p for p in readers.list_trace_files()}
        real = allowed.get(os.path.basename(file))
        if real:
            lines, truncated = readers.read_trace_lines(real)
            title = f"审计文件 {os.path.basename(real)} 全文"
        else:
            title = "未找到指定审计文件（仅允许查看产物目录内的 trace 文件）"
    else:
        title = "请从审计总览页选择条目进入"

    return render(
        request, "audit_detail.html", "audit",
        pid=pid, card=card, lines=lines, truncated=truncated,
        title=title, is_sample=is_sample,
    )
