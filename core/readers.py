# -*- coding: utf-8 -*-
"""
core/readers.py — 只读产物解析层
=================================================
本模块只做【读取 + 解析】POC1~POC4 运行后落盘的输出产物文件：
  - sim_icu_data.json          模拟 ICU 患者基线/当前生命体征（POC3/4 Agent 工程）
  - *alert_card*SIM_P00*.json  结构化预警卡片（若外部工程输出 JSON 版）
  - his_alert_card_SIM_P00*.txt 文本版预警卡片（容错解析）
  - agent_trace*.jsonl         Agent 九步闭环审计追踪日志
  - POC2 湖仓产物              Iceberg 快照元数据 JSON、多模态融合统计报告 JSON

解析逻辑对文件名和字段名做了【容错适配】（多种命名习惯都能识别），
但绝不修改、不重建任何产物；找不到产物时返回空结果，由页面提示用户。
"""

import glob
import json
import os
import re
from datetime import datetime

import config


# =====================================================================
# 通用小工具
# =====================================================================

def _read_json(path):
    """安全读取 JSON 文件，失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception:
        return None


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _fmt_mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _pick(obj: dict, *keys, default=None):
    """从 dict 中按多个候选键名取值（容错字段命名差异）。"""
    if not isinstance(obj, dict):
        return default
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return default


# =====================================================================
# 一、产物目录解析（外部路径优先，可回退到自带示例产物）
# =====================================================================

def agent_output_dir():
    """
    返回 (目录路径, 是否为自带示例)。
    优先使用 config.POC_AGENT_OUTPUT_DIR；不存在且允许回退时使用 sample_data/poc_agent。
    """
    d = getattr(config, "POC_AGENT_OUTPUT_DIR", "")
    if d and os.path.isdir(d):
        return d, False
    if getattr(config, "USE_SAMPLE_FALLBACK", False):
        sd = os.path.join(getattr(config, "SAMPLE_DATA_DIR", ""), "poc_agent")
        if os.path.isdir(sd):
            return sd, True
    return None, False


def lakehouse_dir():
    """POC2 湖仓产物目录，返回 (目录路径, 是否为自带示例)。"""
    d = getattr(config, "POC2_LAKEHOUSE_OUTPUT_DIR", "")
    if d and os.path.isdir(d):
        return d, False
    if getattr(config, "USE_SAMPLE_FALLBACK", False):
        sd = os.path.join(getattr(config, "SAMPLE_DATA_DIR", ""), "lakehouse")
        if os.path.isdir(sd):
            return sd, True
    return None, False


def config_status() -> list:
    """首页诊断面板用：列出各外部路径的配置与存在状态。"""
    items = [
        ("POC3/4 Agent 产物目录", getattr(config, "POC_AGENT_OUTPUT_DIR", "")),
        ("POC3/4 Agent 入口脚本", getattr(config, "POC_AGENT_MAIN_SCRIPT", "")),
        ("POC2 湖仓产物目录", getattr(config, "POC2_LAKEHOUSE_OUTPUT_DIR", "")),
    ]
    out = []
    for label, path in items:
        out.append({
            "label": label,
            "path": path or "(未配置)",
            "exists": bool(path) and os.path.exists(path),
        })
    return out


# =====================================================================
# 二、模拟患者数据（sim_icu_data.json）
# =====================================================================

def _agent_scan_roots():
    """
    Agent 工程的扫描根目录列表（去重）：
      1. 配置的产物输出目录（或示例回退目录）；
      2. 入口脚本所在的工程根目录（覆盖 sim_icu_data.json 放在 data/ 子目录等情况）。
    返回 [(目录, 是否示例), ...]
    """
    roots = []
    d, is_sample = agent_output_dir()
    if d:
        roots.append((d, is_sample))
    script = getattr(config, "POC_AGENT_MAIN_SCRIPT", "")
    if script and os.path.exists(script):
        proj = os.path.dirname(os.path.abspath(script))
        if all(os.path.abspath(r) != proj for r, _ in roots):
            roots.append((proj, False))
    return roots


# 扫描时排除的目录名（防止误遍历虚拟环境/版本库）
_EXCLUDE_DIRS = {".venv", "venv", ".git", ".idea", "__pycache__", "node_modules"}


def _walk_files(root: str):
    """安全遍历目录（跳过 .venv/.git 等），产出文件绝对路径。"""
    for cur, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in _EXCLUDE_DIRS]
        for f in files:
            yield os.path.join(cur, f)


def load_sim_data():
    """
    读取 sim_icu_data.json。按以下顺序搜索：
      产物目录/、产物目录/data/、工程根目录/、工程根目录/data/、工程根目录/output/
    返回 (数据dict|None, 文件路径|None, 是否示例)。
    """
    cands = []
    for root, is_sample in _agent_scan_roots():
        cands += [(os.path.join(root, "sim_icu_data.json"), is_sample),
                  (os.path.join(root, "data", "sim_icu_data.json"), is_sample),
                  (os.path.join(root, "output", "sim_icu_data.json"), is_sample)]
    for cand, is_sample in cands:
        if os.path.exists(cand):
            return _read_json(cand), cand, is_sample
    is_sample = any(s for _, s in _agent_scan_roots())
    return None, None, is_sample


# 页面展示用的关键生命体征（字段名, 中文名, 单位）
VITAL_FIELDS = [
    ("hr",          "心率 HR",      "次/分"),
    ("map",         "平均动脉压 MAP", "mmHg"),
    ("resp_rate",   "呼吸频率 RR",   "次/分"),
    ("spo2",        "指氧 SpO2",     "%"),
    ("lactate",     "血乳酸",        "mmol/L"),
    ("urine_4h",    "4小时尿量",     "mL"),
    ("norepi_dose", "去甲肾上腺素",  "μg/kg/min"),
]


def build_patient_rows(sim_data: dict) -> list:
    """把 sim_icu_data.json 解析为患者表格行（含基线→当前对比与趋势箭头）。"""
    rows = []
    if not sim_data:
        return rows
    for p in sim_data.get("patients", []):
        pid = p.get("patient_id", "")
        vitals = []
        base, cur = p.get("baseline", {}), p.get("current", {})
        for key, label, unit in VITAL_FIELDS:
            b, c = base.get(key), cur.get(key)
            trend = "flat"
            try:
                if c is not None and b is not None:
                    trend = "up" if float(c) > float(b) else ("down" if float(c) < float(b) else "flat")
            except (TypeError, ValueError):
                pass
            vitals.append({"key": key, "label": label, "unit": unit,
                           "base": b, "cur": c, "trend": trend})
        card = load_alert_card(pid)
        rows.append({
            "patient_id": pid,
            "name": p.get("name", ""),
            "diagnosis": p.get("diagnosis", ""),
            "vitals": vitals,
            "has_card": card is not None,
            "level": card["level"] if card else None,
        })
    return rows


# =====================================================================
# 三、预警卡片（alert card）解析
# =====================================================================

def _find_card_file(pid: str):
    """
    在 Agent 产物目录（及工程根目录）中查找指定患者的预警卡片文件。
    支持 JSON 版（优先）与文本版；兼容常见命名：
      alert_card_SIM_P001.json / alert_card_SIM_P001.txt
      his_alert_card_SIM_P001.txt / SIM_P001_alert_card.json ...
    返回 (文件路径, 是否示例) 或 (None, is_sample)。
    """
    json_hits, txt_hits = [], []
    is_sample_out = False
    for root, is_sample in _agent_scan_roots():
        for f in _walk_files(root):
            name = os.path.basename(f).lower()
            if "alert_card" not in name or pid.lower() not in name:
                continue
            is_sample_out = is_sample
            if name.endswith(".json"):
                json_hits.append(f)
            elif name.endswith(".txt"):
                txt_hits.append(f)
    if json_hits:
        return sorted(json_hits)[0], is_sample_out
    if txt_hits:
        return sorted(txt_hits)[0], is_sample_out
    return None, any(s for _, s in _agent_scan_roots())


def _parse_card_text(text: str) -> dict:
    """
    容错解析文本版预警卡片，兼容两种排版：
      排版A：「风险概率：0.98 / 风险评分：7.275 / 驱动因子：- xxx - xxx」
      排版B：「【风险概率】47% 【风险评分】3.908 【驱动因子变化趋势】xxx、xxx」
    """
    info = {"probability": None, "score": None, "drivers": []}

    m = re.search(r"【患者】\s*(\S+?)（(.*?)）\s*(.*)", text)
    if m:
        info["patient_id"] = m.group(1).strip()
        info["name"] = m.group(2).strip()
        info["diagnosis"] = m.group(3).strip()

    m = re.search(r"风险概率[】\s：:]*([0-9]+(?:\.[0-9]+)?)\s*(%)?", text)
    if m:
        v = float(m.group(1))
        if m.group(2) == "%" or v > 1:
            v = v / 100.0
        info["probability"] = round(v, 4)

    m = re.search(r"风险评分[】\s：:]*([0-9]+(?:\.[0-9]+)?)", text)
    if m:
        info["score"] = float(m.group(1))

    # 驱动因子：优先识别「- 」开头的列表行；否则取“驱动因子”标题后的整段按顿号/逗号切分
    drivers = [ln.strip().lstrip("-·• ").strip()
               for ln in text.splitlines()
               if ln.strip().startswith(("- ", "-", "·", "•"))]
    if not drivers:
        m = re.search(r"驱动因子[^】\n]*[】：:]?\s*(.+?)(?:\n\s*\n|本提示|$)", text, re.S)
        if m:
            seg = re.sub(r"\s+", "", m.group(1)).rstrip("。")
            drivers = [s for s in re.split(r"[、，,；;]", seg) if s]
    info["drivers"] = drivers
    return info


def _normalize_card_json(obj: dict) -> dict:
    """把 JSON 版预警卡片归一化为统一字段（容错不同工程的字段命名）。"""
    prob = _pick(obj, "risk_probability", "probability", "risk_prob", "prob")
    try:
        prob = float(prob)
        if prob > 1:
            prob = prob / 100.0
    except (TypeError, ValueError):
        prob = None
    score = _pick(obj, "risk_score", "score")
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = None
    return {
        "patient_id": _pick(obj, "patient_id", "pid", default=""),
        "probability": prob,
        "score": score,
        "drivers": _pick(obj, "drivers", "driving_factors", "risk_drivers", default=[]) or [],
        "checklist": _pick(obj, "checklist", "recheck_list", "review_checklist", default=[]) or [],
        "evidence": _pick(obj, "evidence", "rag_evidence", "citations", "evidence_snippets", default=[]) or [],
        "jev": _pick(obj, "jev", "jev_check", "self_check", default=None),
        "explicit_level": _pick(obj, "risk_level", "level", default=None),
        "card_text": _pick(obj, "card_text", "alert_text", "message", default=""),
    }


def derive_level(probability):
    """按 config 阈值把风险概率映射为 L1/L2/L3（仅用于页面分级配色）。"""
    if probability is None:
        return None
    if probability >= getattr(config, "RISK_L3_THRESHOLD", 0.8):
        return "L3"
    if probability >= getattr(config, "RISK_L2_THRESHOLD", 0.4):
        return "L2"
    return "L1"


def load_alert_card(pid: str):
    """
    读取指定患者的预警卡片并归一化。
    返回 dict：{kind, path, is_sample, level, probability, score, drivers,
                checklist, evidence, jev, card_text, raw_text}
    找不到卡片（例如低危静默）返回 None。
    """
    path, is_sample = _find_card_file(pid)
    if not path:
        return None

    if path.lower().endswith(".json"):
        obj = _read_json(path)
        if not isinstance(obj, dict):
            return None
        info = _normalize_card_json(obj)
        kind = "json"
        raw_text = json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        text = _read_text(path)
        info = _parse_card_text(text)
        info.update({"checklist": [], "evidence": [], "jev": None,
                     "explicit_level": None, "card_text": text})
        kind = "txt"
        raw_text = text

    level = info.get("explicit_level") or derive_level(info.get("probability"))
    return {
        "kind": kind,
        "path": path,
        "is_sample": is_sample,
        "level": level,
        "probability": info.get("probability"),
        "score": info.get("score"),
        "drivers": info.get("drivers") or [],
        "checklist": info.get("checklist") or [],
        "evidence": info.get("evidence") or [],
        "jev": info.get("jev"),
        "card_text": info.get("card_text") or "",
        "raw_text": raw_text,
        "mtime": _fmt_mtime(path),
    }


# =====================================================================
# 四、审计追踪日志（agent_trace*.jsonl）
# =====================================================================

def list_trace_files() -> list:
    """列出 Agent 产物目录（及工程根目录）下全部 *trace*.jsonl 审计文件。"""
    files = []
    for root, _ in _agent_scan_roots():
        for f in _walk_files(root):
            name = os.path.basename(f).lower()
            if name.endswith(".jsonl") and "trace" in name:
                files.append(f)
    # 去重并排序（最新的排前面）
    files = sorted(set(files), key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def read_trace_lines(path: str, pid: str = "", max_lines: int = None):
    """
    读取一个 jsonl 审计文件；给定 pid 时只保留包含该患者ID的行。
    返回 (行列表[{no, raw, obj}], 是否被截断)。
    """
    max_lines = max_lines or getattr(config, "TRACE_MAX_LINES", 2000)
    lines, truncated = [], False
    if not path or not os.path.exists(path):
        return lines, truncated
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for no, ln in enumerate(f, 1):
            raw = ln.rstrip("\n")
            if not raw.strip():
                continue
            if pid and pid not in raw:
                continue
            obj = None
            try:
                obj = json.loads(raw)
            except Exception:
                pass
            lines.append({"no": no, "raw": raw, "obj": obj})
            if len(lines) >= max_lines:
                truncated = True
                break
    return lines, truncated


def read_trace_for_patient(pid: str, max_lines: int = None):
    """跨全部 trace 文件汇总某个患者的审计行。返回 (行列表, 截断标志, 涉及文件数)。"""
    merged, truncated, used_files = [], False, 0
    for path in list_trace_files():
        lines, tr = read_trace_lines(path, pid=pid, max_lines=max_lines)
        if lines:
            used_files += 1
            for item in lines:
                item["file"] = os.path.basename(path)
            merged.extend(lines)
        truncated = truncated or tr
    return merged, truncated, used_files


def trace_file_summary(path: str) -> dict:
    """审计总览页用：统计一个 trace 文件的行数与时间范围。"""
    n, first_ts, last_ts = 0, "", ""
    events = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                n += 1
                try:
                    obj = json.loads(ln)
                    ts = obj.get("ts") or obj.get("time") or obj.get("timestamp") or ""
                    if ts:
                        if not first_ts:
                            first_ts = str(ts)
                        last_ts = str(ts)
                    ev = obj.get("event") or obj.get("step") or ""
                    if ev:
                        events.add(str(ev))
                except Exception:
                    pass
    return {
        "path": path,
        "name": os.path.basename(path),
        "lines": n,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "events": sorted(events),
        "size_kb": round(os.path.getsize(path) / 1024, 1) if os.path.exists(path) else 0,
    }


def build_audit_records() -> list:
    """
    审计总览页主表：以患者为维度汇总每一次 Agent 运行记录。
    规则（只读推断，不做任何业务计算）：
      - 有预警卡片产物 → 状态「输出预警卡片」（L3 且含复查清单时标注）
      - 无卡片但在患者清单中 → 「低危静默 · 仅审计留痕（或无卡片产物）」
    """
    records = []
    sim_data, _, _ = load_sim_data()
    patients = sim_data.get("patients", []) if sim_data else []

    seen = set()
    for p in patients:
        pid = p.get("patient_id", "")
        if not pid:
            continue
        seen.add(pid)
        card = load_alert_card(pid)
        if card:
            status = "输出预警卡片"
            if card["level"] == "L3":
                status = "输出预警卡片" + ("（含复查清单）" if card["checklist"] else "")
            records.append({
                "pid": pid, "name": p.get("name", ""),
                "time": card["mtime"], "level": card["level"],
                "status": status, "card_path": card["path"],
            })
        else:
            records.append({
                "pid": pid, "name": p.get("name", ""),
                "time": "", "level": None,
                "status": "低危静默 · 仅审计留痕（未发现预警卡片产物）",
                "card_path": "",
            })

    # 兜底：患者清单缺失时，从卡片文件名反查患者ID
    for root, _ in _agent_scan_roots():
        for f in _walk_files(root):
            if "alert_card" not in os.path.basename(f).lower():
                continue
            m = re.search(r"(SIM[_A-Za-z0-9]+)", os.path.basename(f))
            if m and m.group(1) not in seen:
                pid = m.group(1)
                seen.add(pid)
                card = load_alert_card(pid)
                records.append({
                    "pid": pid, "name": "",
                    "time": card["mtime"] if card else _fmt_mtime(f),
                    "level": card["level"] if card else None,
                    "status": "输出预警卡片", "card_path": f,
                })
    return records


# =====================================================================
# 五、POC2 湖仓产物（Iceberg 快照元数据 / 多模态融合报告）
# =====================================================================

def _norm_snapshot(s: dict) -> dict:
    """
    把一条快照记录归一化。兼容：
      - Iceberg 官方表元数据（.metadata.json）：snapshot-id / timestamp-ms / summary.operation / summary.total-records（连字符键名）
      - 自定义统计 JSON：snapshot_id / timestamp_ms / patient_count / match_rate（下划线键名）
    """
    summary = s.get("summary") if isinstance(s.get("summary"), dict) else {}
    ts = _pick(s, "timestamp_ms", "timestamp-ms", "timestamp", "ts", "committed_at")
    ts_str = ""
    if ts is not None:
        try:
            tsv = float(ts)
            if tsv > 1e12:   # 毫秒时间戳
                ts_str = datetime.fromtimestamp(tsv / 1000).strftime("%Y-%m-%d %H:%M:%S")
            elif tsv > 1e9:  # 秒时间戳
                ts_str = datetime.fromtimestamp(tsv).strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_str = str(ts)
        except (TypeError, ValueError):
            ts_str = str(ts)
    patient_count = _pick(s, "patient_count", "num_patients", "total_patients",
                          default=_pick(summary, "total-records", "total_records",
                                        "added-records", "added_records"))
    match_rate = _pick(s, "multimodal_match_rate", "match_rate", "clin_image_match_rate")
    operation = _pick(s, "operation", default=_pick(summary, "operation", default=""))
    return {
        "snapshot_id": str(_pick(s, "snapshot_id", "snapshot-id", "id", default="")),
        "ts": ts_str,
        "operation": operation,
        "patient_count": patient_count,
        "match_rate": match_rate,
        "raw": s,
    }


def load_lakehouse() -> dict:
    """
    扫描 POC2 湖仓产物目录：
      - 快照元数据：含 "snapshots" 列表的 JSON，或本身就是快照列表；
      - 融合统计报告：含 match_rate / 多模态匹配等字段的 JSON。
    返回 {dir, is_sample, snapshots[], fusion, files[], notes[]}
    """
    d, is_sample = lakehouse_dir()
    out = {"dir": d, "is_sample": is_sample, "snapshots": [],
           "fusion": None, "fusion_path": None, "files": [], "notes": []}
    if not d:
        out["notes"].append("未找到 POC2 湖仓产物目录。请在 config.py 中配置 POC2_LAKEHOUSE_OUTPUT_DIR。")
        return out

    json_files = sorted(f for f in _walk_files(d) if f.lower().endswith(".json"))
    out["files"] = [os.path.relpath(p, d) for p in json_files]

    snap_candidates = []  # [(文件修改时间, 路径, snapshots列表)]
    fusion_obj, fusion_path = None, None
    for p in json_files:
        obj = _read_json(p)
        if obj is None:
            continue
        name = os.path.basename(p).lower()
        # 快照元数据识别：dict 内含非空 snapshots 列表（Iceberg 官方 .metadata.json 即此结构）
        if isinstance(obj, dict) and isinstance(obj.get("snapshots"), list) and obj["snapshots"]:
            snap_candidates.append((os.path.getmtime(p), p, obj["snapshots"]))
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict) and \
                any("snapshot_id" in x or "snapshot-id" in x for x in obj) and "snapshot" in name:
            snap_candidates.append((os.path.getmtime(p), p, obj))
        # 融合统计报告识别
        if fusion_obj is None and isinstance(obj, dict):
            keys = set(obj.keys())
            if keys & {"match_rate", "multimodal_match_rate", "clin_image_match_rate",
                       "fusion", "matched", "matched_count"} or "fusion" in name or "融合" in name:
                fusion_obj, fusion_path = obj, p

    if snap_candidates:
        # 多张表时的选择策略：优先 ADS 应用层/多模态融合表，其次 DWD，再次其他；
        # 同优先级取最近更新的元数据（页面会展示实际读取的文件路径，透明可查）
        def _rank(item):
            mtime, path, _lst = item
            p = path.lower()
            pri = 2 if ("ads" in p or "multimodal" in p) else (1 if "dwd" in p else 0)
            return (pri, mtime)

        snap_candidates.sort(key=_rank, reverse=True)
        _, snap_path, snap_list = snap_candidates[0]
        out["snapshots"] = [_norm_snapshot(s) for s in snap_list if isinstance(s, dict)]
        out["snapshots"].sort(key=lambda x: x["ts"], reverse=True)
        out["snap_path"] = snap_path
        if len(snap_candidates) > 1:
            out["notes"].append(
                f"共发现 {len(snap_candidates)} 份含快照的表元数据，已按「ADS/多模态优先、其次最新」"
                f"选择：{os.path.relpath(snap_path, d)}")
    else:
        out["notes"].append("未在产物目录中识别到 Iceberg 快照元数据 JSON（期望包含 snapshots 列表）。")

    if fusion_obj:
        out["fusion"], out["fusion_path"] = fusion_obj, fusion_path
    else:
        out["notes"].append("未在产物目录中识别到多模态融合统计报告 JSON（期望含 match_rate 等字段）。")
    return out
