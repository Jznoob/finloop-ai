from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def _passport(run: dict[str, Any]) -> dict[str, Any]:
    value = run.get("evidence_passport")
    return value if isinstance(value, dict) else {}


def _source_map(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(source.get("id")): source
        for source in _passport(run).get("sources", [])
        if isinstance(source, dict) and source.get("id")
    }


def _actual_variant(run: dict[str, Any]) -> str:
    execution = run.get("execution") or {}
    return str(execution.get("variant") or run.get("request", {}).get("variant") or "unknown")


def _dimension(key: str, label: str, left: Any, right: Any) -> dict[str, Any]:
    return {"key": key, "label": label, "left": left, "right": right, "changed": left != right}


def compare_runs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, read-only diff between two saved decisions."""

    left_request = left.get("request") or {}
    right_request = right.get("request") or {}
    left_passport, right_passport = _passport(left), _passport(right)
    left_sources, right_sources = _source_map(left), _source_map(right)

    left_ids, right_ids = set(left_sources), set(right_sources)
    added = [
        {"id": source_id, "title": right_sources[source_id].get("title", source_id)}
        for source_id in sorted(right_ids - left_ids)
    ]
    removed = [
        {"id": source_id, "title": left_sources[source_id].get("title", source_id)}
        for source_id in sorted(left_ids - right_ids)
    ]
    version_changed = [
        {
            "id": source_id,
            "title": right_sources[source_id].get("title", source_id),
            "left_hash": left_sources[source_id].get("content_hash", ""),
            "right_hash": right_sources[source_id].get("content_hash", ""),
        }
        for source_id in sorted(left_ids & right_ids)
        if left_sources[source_id].get("content_hash")
        != right_sources[source_id].get("content_hash")
    ]
    unchanged = sorted(
        source_id
        for source_id in left_ids & right_ids
        if left_sources[source_id].get("content_hash")
        == right_sources[source_id].get("content_hash")
    )
    evidence_same = not added and not removed and not version_changed

    prompt_left = left_passport.get("prompt_versions") or {}
    prompt_right = right_passport.get("prompt_versions") or {}
    prompt_known = bool(prompt_left) and bool(prompt_right)
    prompt_same = prompt_known and prompt_left == prompt_right
    simulator_same = bool(left_passport.get("simulator")) and (
        left_passport.get("simulator") == right_passport.get("simulator")
    )
    core_same = all(
        left_request.get(key) == right_request.get(key)
        for key in ("segment_id", "objective", "market_signal", "seed")
    )

    if core_same and evidence_same and prompt_same and simulator_same:
        quality = {
            "level": "strong",
            "label": "强可比",
            "detail": (
                "核心输入、随机种子、证据版本、提示词版本和模拟器版本一致。"
                "适合比较策略差异；远程模型输出仍可能存在非确定性。"
            ),
        }
    elif core_same:
        quality = {
            "level": "partial",
            "label": "部分可比",
            "detail": (
                "核心输入和随机种子一致，但证据或版本信息并非完全一致。"
                "差异可能不只来自策略。"
            ),
        }
    else:
        quality = {
            "level": "contextual",
            "label": "情境对照",
            "detail": "核心输入或随机种子不同，只能用于复盘变化，不能归因于单一策略。",
        }

    left_execution, right_execution = left.get("execution") or {}, right.get("execution") or {}

    def metric(key: str, label: str, unit: str = "count") -> dict[str, Any]:
        left_value, right_value = left_execution.get(key), right_execution.get(key)
        delta = None
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            delta = right_value - left_value
        return {
            "key": key,
            "label": label,
            "left": left_value,
            "right": right_value,
            "delta": delta,
            "unit": unit,
        }

    left_copy = str((left.get("compliance") or {}).get("final_copy") or "")
    right_copy = str((right.get("compliance") or {}).get("final_copy") or "")
    similarity = SequenceMatcher(None, left_copy, right_copy, autojunk=False).ratio()
    left_calls = [call.get("outcome", "unknown") for call in left.get("model_calls") or []]
    right_calls = [call.get("outcome", "unknown") for call in right.get("model_calls") or []]

    dimensions = [
        _dimension(
            "segment",
            "目标客群",
            (left.get("segment") or {}).get("name"),
            (right.get("segment") or {}).get("name"),
        ),
        _dimension(
            "objective",
            "业务目标",
            left_request.get("objective"),
            right_request.get("objective"),
        ),
        _dimension(
            "market_signal",
            "市场信号",
            left_request.get("market_signal"),
            right_request.get("market_signal"),
        ),
        _dimension("seed", "随机种子", left_request.get("seed"), right_request.get("seed")),
        _dimension("variant", "实际策略", _actual_variant(left), _actual_variant(right)),
        _dimension(
            "product",
            "选择产品",
            (left.get("selected_product") or {}).get("name"),
            (right.get("selected_product") or {}).get("name"),
        ),
        _dimension(
            "compliance",
            "规则结果",
            (left.get("compliance") or {}).get("status"),
            (right.get("compliance") or {}).get("status"),
        ),
        _dimension(
            "provider",
            "模型提供方",
            left.get("model_provider"),
            right.get("model_provider"),
        ),
        _dimension("model_calls", "模型调用", " / ".join(left_calls), " / ".join(right_calls)),
        _dimension(
            "prompt_versions",
            "提示词版本",
            " / ".join(f"{key}:{value}" for key, value in sorted(prompt_left.items()))
            or "旧记录未保存",
            " / ".join(f"{key}:{value}" for key, value in sorted(prompt_right.items()))
            or "旧记录未保存",
        ),
    ]

    interpretation = [quality["detail"]]
    if version_changed:
        interpretation.append(f"有 {len(version_changed)} 篇相同编号证据的内容版本发生变化。")
    if added or removed:
        interpretation.append(f"证据集合新增 {len(added)} 篇、移除 {len(removed)} 篇。")
    if _actual_variant(left) != _actual_variant(right) and core_same:
        interpretation.append("两次运行采用不同策略，可结合漏斗差异观察模拟敏感性。")
    if left_calls != right_calls:
        interpretation.append("模型调用结果不同，生成差异可能包含模型或降级路径影响。")
    if similarity < 0.7:
        interpretation.append("最终内容变化较大，建议逐项复核规则、证据和模型轨迹。")

    return {
        "left": {
            "run_id": left.get("run_id"),
            "created_at": left.get("created_at"),
            "status": left.get("status"),
        },
        "right": {
            "run_id": right.get("run_id"),
            "created_at": right.get("created_at"),
            "status": right.get("status"),
        },
        "quality": quality,
        "dimensions": dimensions,
        "evidence": {
            "same": evidence_same,
            "added": added,
            "removed": removed,
            "version_changed": version_changed,
            "unchanged_ids": unchanged,
        },
        "funnel": [
            metric("audience_size", "样本"),
            metric("delivered", "送达"),
            metric("opened", "打开"),
            metric("converted", "响应"),
            metric("open_rate", "打开率", "rate"),
            metric("conversion_rate", "送达响应率", "rate"),
        ],
        "content": {
            "left_characters": len(left_copy),
            "right_characters": len(right_copy),
            "similarity": round(similarity, 4),
            "changed": left_copy != right_copy,
        },
        "interpretation": interpretation,
        "boundaries": (
            "差异视图用于复盘保存结果。即使标记为强可比，也只是同种子模拟对照，"
            "不构成真实因果实验或业务效果证明。"
        ),
    }
