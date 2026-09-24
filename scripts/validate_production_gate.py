#!/usr/bin/env python3
"""Check production evidence records, not artistic quality or server permission.

Read-only, standard library only. No network calls, generation, or adoption writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


REQUIRED = {
    "script": {
        "prepare": {"story_brief"},
        "accept": {"story_contract", "continuity"},
    },
    "assets": {
        "prepare": {"visual_contract", "prompt_scope", "reference_binding", "sample_gate"},
        "accept": {"identity_state", "style_consistency"},
    },
    "storyboards": {
        "prepare": {"visual_contract", "prompt_scope", "reference_binding", "shot_plan"},
        "accept": {"identity_state", "style_consistency", "spatial_continuity", "shot_coverage"},
    },
    "roughcut": {
        "prepare": {"shot_plan", "sound_plan"},
        "accept": {"story_contract", "timing_sound", "spatial_continuity"},
    },
    "audio": {
        "prepare": {"sound_plan", "voice_binding"},
        "accept": {"voice_binding", "timing_sound"},
    },
    "video": {
        "prepare": {"reference_binding", "shot_plan", "sample_gate", "roughcut_gate"},
        "accept": {"identity_state", "spatial_continuity", "motion_quality", "timing_sound"},
    },
    "delivery": {
        "prepare": {"adoption_map", "export_spec"},
        "accept": {"story_contract", "timing_sound", "spatial_continuity", "export_spec"},
    },
}
MEDIA = {
    "script": {"text"}, "assets": {"image"}, "storyboards": {"image"},
    "roughcut": {"video"}, "audio": {"audio", "video"},
    "video": {"video"}, "delivery": {"video"},
}
KINDS = {"text", "image", "audio", "video", "record", "prompt"}


def required_checks(stage, phase):
    common = {"scope_authority", "source_alignment", "execution_config"} if phase == "prepare" else {"source_alignment", "actual_review"}
    return common | REQUIRED[stage][phase]


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(data, current, base_dir):
    errors = []
    if not isinstance(data, dict) or not isinstance(current, dict):
        return ["检查记录与当前状态必须是 JSON 对象"]
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        errors.append("schema_version 必须为 1")
    if data.get("template_only") is not False:
        errors.append("需填写实际记录并显式设置 template_only=false")
    stage, phase = data.get("stage"), data.get("phase")
    if not isinstance(stage, str) or stage not in REQUIRED or phase not in ("prepare", "accept"):
        return errors + ["stage 或 phase 无效"]
    for key in ("project", "episode", "source_revision"):
        if (key == "source_revision" and stage == "script" and phase == "prepare"
                and key in data and key in current and data[key] is None and current[key] is None):
            continue  # A genuinely new script has no saved source revision yet.
        if not nonempty(data.get(key)) or data.get(key) != current.get(key):
            errors.append(f"{key} 缺失或与当前状态不符")

    dependencies = data.get("dependencies")
    live = current.get("dependencies")
    if not isinstance(dependencies, dict) or not isinstance(live, dict):
        errors.append("记录与当前状态均需 dependencies 对象")
    else:
        if stage != "script" and not dependencies:
            errors.append("此阶段需列出采用基线依赖，禁止空依赖放行")
        for key, version in dependencies.items():
            item = live.get(key)
            if not nonempty(version) or not isinstance(item, dict) or item.get("version") != version:
                errors.append(f"依赖 {key} 缺失或版本过期")
            elif item.get("adoption") != "accepted":
                errors.append(f"依赖 {key} 尚未采用；技术 current/succeeded 不等于 accepted")

    targets = data.get("targets")
    if not isinstance(targets, list) or not targets or not all(nonempty(x) for x in targets):
        errors.append("targets 必须是非空目标 ID 列表")
        targets = []
    elif len(set(targets)) != len(targets):
        errors.append("targets 存在重复 ID")
    if data.get("blockers") != []:
        errors.append("blockers 缺失或存在未解决阻断")

    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("缺少实际 evidence")
        evidence = []
    index = {}
    for i, item in enumerate(evidence):
        label = f"evidence[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        if not all(nonempty(item.get(k)) for k in ("id", "uri", "version", "kind")):
            errors.append(f"{label} 缺少 id/uri/version/kind")
            continue
        eid = item["id"]
        if eid in index:
            errors.append(f"证据 ID 重复：{eid}")
        index[eid] = item
        if item["kind"] not in KINDS:
            errors.append(f"{label}.kind 无效")
        uri = item["uri"]
        if uri.lower().startswith(("https://", "http://")):
            if not urlparse(uri).netloc:
                errors.append(f"证据地址无效：{eid}")
        else:
            path = Path(uri)
            if not path.is_absolute():
                path = Path(base_dir) / path
            if not path.is_file():
                errors.append(f"本地证据文件不存在：{eid}")

    def inspect_record(item, label):
        if not isinstance(item, dict):
            errors.append(f"{label} 缺失或格式错误")
            return []
        if item.get("status") != "pass":
            errors.append(f"{label} 未通过")
        if not nonempty(item.get("findings")):
            errors.append(f"{label} 缺少具体审查发现")
        refs = item.get("evidence")
        if not isinstance(refs, list) or not refs or not all(nonempty(x) for x in refs):
            errors.append(f"{label} 缺少证据引用")
            return []
        for ref in refs:
            if ref not in index:
                errors.append(f"{label} 引用了不存在的证据 {ref}")
        return refs

    if stage in {"assets", "storyboards", "video"}:
        visual = data.get("visual_contract")
        if not isinstance(visual, dict):
            errors.append("视觉阶段缺少结构化 visual_contract，不以通过标签代替具体画风")
        else:
            for key in ("version", "medium", "shape_language", "line_and_material", "light_and_color", "exclude"):
                if not nonempty(visual.get(key)):
                    errors.append(f"visual_contract.{key} 缺少具体定义")
            if not isinstance(dependencies, dict) or dependencies.get("visual_contract") != visual.get("version"):
                errors.append("visual_contract.version 必须绑定到同名版本依赖")
            basis = visual.get("decision_evidence")
            if not isinstance(basis, str) or basis not in index:
                errors.append("visual_contract 缺少方向决定来源证据")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        checks = {}
        errors.append("checks 必须是对象")
    for key in sorted(required_checks(stage, phase)):
        inspect_record(checks.get(key), f"checks.{key}")
    # Additional declared checks must not conceal unresolved failures either.
    for key in set(checks) - required_checks(stage, phase):
        inspect_record(checks[key], f"checks.{key}")

    if phase == "accept":
        results = data.get("results")
        if not isinstance(results, list):
            results = []
            errors.append("accept 需要逐目标 results")
        seen = []
        for i, item in enumerate(results):
            label = f"results[{i}]"
            if not isinstance(item, dict):
                errors.append(f"{label} 必须是对象")
                continue
            target = item.get("target")
            if not nonempty(target):
                errors.append(f"{label}.target 无效")
            else:
                seen.append(target)
            aid = item.get("artifact")
            artifact = index.get(aid) if isinstance(aid, str) else None
            refs = inspect_record(item.get("inspection"), f"{label}.inspection")
            if not artifact or artifact["kind"] not in MEDIA[stage]:
                errors.append(f"{label} 未引用本阶段实际产物类型；日志/提示词不是产物")
            elif not nonempty(item.get("version")) or item["version"] != artifact["version"]:
                errors.append(f"{label} 验收版本与产物版本不符")
            if aid not in refs:
                errors.append(f"{label} 检查未引用该实际产物")
        if set(seen) != set(targets) or len(seen) != len(targets):
            errors.append("results 必须完整且无重复地覆盖 targets")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--current", type=Path, required=True, help="调用前从事实源读取的当前状态快照")
    args = parser.parse_args()
    try:
        data = json.loads(args.record.read_text(encoding="utf-8-sig"))
        current = json.loads(args.current.read_text(encoding="utf-8-sig"))
        errors = validate(data, current, args.record.resolve().parent)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": not errors, "errors": errors,
                      "scope": "记录完整性与版本检查；不代表自动视觉/声音验收或服务器强制拦截"},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
