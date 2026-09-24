#!/usr/bin/env python3
"""Validate a normalized episode story contract.

This file never edits ArcReel. It checks a derived planning/QA view only.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def _number(value, name, errors):
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"{name} 必须是数字")
        return 0.0


def _required_text(value, name, errors):
    if not str(value or "").strip():
        errors.append(f"{name} 缺失")


def validate(data):
    errors, warnings = [], []
    if data.get("template_only") is True:
        errors.append("这是模板文件；复制到项目、填写实际证据并将 template_only 设为 false")

    duration = _number(data.get("duration_seconds"), "duration_seconds", errors)
    if duration <= 0:
        errors.append("duration_seconds 必须大于 0")

    for key in ("project", "episode"):
        _required_text(data.get(key), key, errors)
    if not str(data.get("source_revision") or "").strip():
        warnings.append("source_revision 为空：新集可暂空，已有正式剧本应填写 canonical revision")

    hook = data.get("hook") or {}
    conflict_at = _number(hook.get("conflict_at_seconds"), "hook.conflict_at_seconds", errors)
    if conflict_at < 0 or conflict_at > 3:
        errors.append(f"前 3 秒激烈冲突未达标：冲突点为 {conflict_at:g}s")
    _required_text(hook.get("type"), "hook.type", errors)
    _required_text(hook.get("evidence"), "hook.evidence", errors)

    voices = data.get("voice_landings") or []
    if len(voices) < 6:
        errors.append(f"有效话语落点仅 {len(voices)} 个，至少需要 6 个")
    voice_times = []
    for i, item in enumerate(voices, 1):
        at = _number((item or {}).get("at_seconds"), f"voice_landings[{i}].at_seconds", errors)
        voice_times.append(at)
        for key in ("speaker", "kind", "text", "function"):
            _required_text((item or {}).get(key), f"voice_landings[{i}].{key}", errors)
    if voice_times and min(voice_times) > 3:
        errors.append(f"第一处有效话语落点为 {min(voice_times):g}s，必须落在前 3 秒")

    beats = data.get("beats") or []
    if not beats:
        errors.append("beats 为空")
    beat_times = []
    for i, item in enumerate(beats, 1):
        at = _number((item or {}).get("at_seconds"), f"beats[{i}].at_seconds", errors)
        if duration > 0 and not (0 <= at <= duration):
            errors.append(f"beats[{i}] 时间 {at:g}s 超出本集范围")
        beat_times.append(at)
        for key in ("type", "change", "shot_id"):
            _required_text((item or {}).get(key), f"beats[{i}].{key}", errors)
    if duration > 0 and beat_times:
        timeline = [0.0] + sorted(set(beat_times)) + [duration]
        gaps = [(a, b, b-a) for a, b in zip(timeline, timeline[1:])]
        bad = [g for g in gaps if g[2] > 20.000001]
        if bad:
            desc = ", ".join(f"{a:g}-{b:g}s({gap:g}s)" for a,b,gap in bad)
            errors.append("爆点间隔超过 20 秒：" + desc)
        dense = [g for g in gaps[1:-1] if 0 < g[2] < 8]
        if len(dense) >= 3:
            warnings.append("存在多段小于 8 秒的爆点间隔，复核是否过密或重复叫喊")

    reversal = data.get("reversal") or {}
    reversal_at = _number(reversal.get("at_seconds"), "reversal.at_seconds", errors)
    if duration > 0 and reversal_at + 1e-9 < duration * 2 / 3:
        errors.append(f"反转过早：{reversal_at:g}s；本集后 1/3 起点为 {duration*2/3:g}s")
    if duration > 0 and reversal_at > duration:
        errors.append("reversal.at_seconds 超出本集时长")
    for key in ("type", "motivation", "change", "consequence"):
        _required_text(reversal.get(key), f"reversal.{key}", errors)
    if not isinstance(reversal.get("foreshadow"), list) or not [x for x in reversal.get("foreshadow", []) if str(x).strip()]:
        errors.append("reversal.foreshadow 至少需要一条可回溯依据")

    pp = data.get("pressure_payoff") or {}
    pressure_at = _number(pp.get("pressure_start_seconds"), "pressure_payoff.pressure_start_seconds", errors)
    payoff_at = _number(pp.get("payoff_at_seconds"), "pressure_payoff.payoff_at_seconds", errors)
    escalations = pp.get("escalations") or []
    if not isinstance(escalations, list) or not [x for x in escalations if str(x).strip()]:
        errors.append("pressure_payoff.escalations 至少需要一次压力升级")
    for key in ("payoff", "result"):
        _required_text(pp.get(key), f"pressure_payoff.{key}", errors)
    if payoff_at <= pressure_at:
        errors.append("压→爆顺序错误：payoff_at_seconds 必须晚于 pressure_start_seconds")
    if duration > 0 and payoff_at > duration:
        errors.append("pressure_payoff.payoff_at_seconds 超出本集时长")

    silences = data.get("silence_segments")
    if silences is None:
        errors.append("silence_segments 缺失；无静默段时填写 []")
        silences = []
    for i, item in enumerate(silences, 1):
        start = _number((item or {}).get("start_seconds"), f"silence_segments[{i}].start_seconds", errors)
        end = _number((item or {}).get("end_seconds"), f"silence_segments[{i}].end_seconds", errors)
        if end < start:
            errors.append(f"silence_segments[{i}] 结束早于开始")
        if end - start > 8.000001:
            errors.append(f"连续静默超过 8 秒：silence_segments[{i}] 为 {end-start:g}s")
        if duration > 0 and (start < 0 or end > duration):
            errors.append(f"silence_segments[{i}] 超出本集范围")
        _required_text((item or {}).get("purpose"), f"silence_segments[{i}].purpose", errors)

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description="校验分集强钩子叙事契约")
    ap.add_argument("contract", help="分集叙事契约 JSON")
    ap.add_argument("--json", action="store_true", help="输出结构化结果")
    args = ap.parse_args()
    path = Path(args.contract)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        result = {"ok": False, "errors": [f"读取失败：{exc}"], "warnings": []}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["errors"][0])
        return 2
    errors, warnings = validate(data)
    result = {"ok": not errors, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("[PASS] 分集叙事契约通过" if not errors else "[FAIL] 分集叙事契约未通过")
        for item in errors:
            print("ERROR:", item)
        for item in warnings:
            print("WARN:", item)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
