#!/usr/bin/env python3
"""
Parse LP input document and generate structured artifacts.

Outputs:
1) <stem>_parsed.json
2) <stem>_problem_description.md
3) <stem>_variable_name_map_cn.json
4) <stem>_report_requirements.md
5) <stem>_report_template.md
6) <stem>_parse_output.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ParseValidationError(Exception):
    """Raised when parsed content fails validation."""


@dataclass
class ParseResult:
    model_json_file: Path
    problem_description_md_file: Path
    variable_name_map_cn_file: Path
    report_requirements_md_file: Path
    report_template_md_file: Path
    parse_output_json_file: Path


def _extract_first(text: str, pattern: str, default: str = "") -> str:
    m = re.search(pattern, text, re.S)
    return m.group(1).strip() if m else default


def _extract_section(text: str, section_header: str) -> str:
    """Extract markdown section content after a '## ...' header."""
    pat = rf"(?ms)^##\s+{re.escape(section_header)}\s*\n(.*?)(?=^##\s+|\Z)"
    m = re.search(pat, text)
    return m.group(1).strip() if m else ""


def _extract_subsection(section_text: str, subsection_header: str) -> str:
    """Extract markdown subsection content after a '### ...' header."""
    pat = rf"(?ms)^###\s+{re.escape(subsection_header)}\s*\n(.*?)(?=^###\s+|\Z)"
    m = re.search(pat, section_text)
    return m.group(1).strip() if m else ""


def _parse_assets(lines: list[str]) -> list[dict[str, Any]]:
    row_re = re.compile(
        r"^\|\s*(A\d{2})\s*\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*$"
    )
    out: list[dict[str, Any]] = []
    for line in lines:
        m = row_re.match(line)
        if not m:
            continue
        out.append(
            {
                "id": m.group(1),
                "name": m.group(2).strip(),
                "long_rate": float(m.group(3)),
                "liq_w": float(m.group(4)),
                "dur": float(m.group(5)),
                "lb": float(m.group(6)),
                "ub": float(m.group(7)),
            }
        )
    if len(out) != 15:
        raise ParseValidationError(f"Expected 15 assets, got {len(out)}")
    return out


def _parse_liabilities(lines: list[str]) -> list[dict[str, Any]]:
    row_re = re.compile(
        r"^\|\s*(L\d{2})\s*\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*$"
    )
    out: list[dict[str, Any]] = []
    for line in lines:
        m = row_re.match(line)
        if not m:
            continue
        out.append(
            {
                "id": m.group(1),
                "name": m.group(2).strip(),
                "long_cost": float(m.group(3)),
                "lb": float(m.group(4)),
                "ub": float(m.group(5)),
            }
        )
    if len(out) != 8:
        raise ParseValidationError(f"Expected 8 liabilities, got {len(out)}")
    return out


def _parse_daily_rates(lines: list[str], asset_ids: list[str], liab_ids: list[str], horizon: int) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    row_re = re.compile(r"^\|\s*D(\d{2})\s*\|\s*(\[[^\]]+\])\s*\|\s*(\[[^\]]+\])\s*\|\s*$")
    rates: dict[str, dict[str, float]] = {}
    costs: dict[str, dict[str, float]] = {}
    for line in lines:
        m = row_re.match(line)
        if not m:
            continue
        day = f"D{int(m.group(1)):02d}"
        asset_vec = [float(x) for x in ast.literal_eval(m.group(2))]
        liab_vec = [float(x) for x in ast.literal_eval(m.group(3))]
        if len(asset_vec) != len(asset_ids):
            raise ParseValidationError(f"{day}: asset vector length mismatch")
        if len(liab_vec) != len(liab_ids):
            raise ParseValidationError(f"{day}: liability vector length mismatch")
        rates[day] = {asset_ids[i]: asset_vec[i] for i in range(len(asset_ids))}
        costs[day] = {liab_ids[i]: liab_vec[i] for i in range(len(liab_ids))}
    if len(rates) != horizon:
        raise ParseValidationError(f"Expected {horizon} daily rows, got {len(rates)}")
    return rates, costs


def _parse_strategy_params(lines: list[str]) -> dict[str, float]:
    raw_to_key = {
        "总资产目标": "total_assets_target",
        "最低流动性覆盖阈值": "liquidity_threshold",
        "久期暴露上限": "duration_exposure_cap",
        "高波动资产组合上限": "high_vol_assets_cap",
        "批发融资上限（L06+L07+L08）": "wholesale_funding_cap",
        "零售存款最低占比": "retail_deposit_min_ratio",
    }
    out: dict[str, float] = {}
    row_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")
    for line in lines:
        m = row_re.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        if name not in raw_to_key:
            continue
        val_raw = m.group(2).strip().replace("%", "")
        val = float(val_raw)
        if name == "零售存款最低占比":
            val /= 100.0
        out[raw_to_key[name]] = val

    # Defaults / constants used in document.
    out.setdefault("single_asset_a15_cap", 90.0)
    out.setdefault("term_structure_buffer", 120.0)
    out["penalty_s_liq"] = 0.40
    out["penalty_s_dur"] = 0.25
    out["daily_rate_denominator"] = 365.0
    return out


def _parse_turnover_limits(lines: list[str], asset_ids: list[str], liab_ids: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    row_re = re.compile(r"^\|\s*(资产|负债)\s*\|\s*([AL]\d{2})\s*\|\s*([0-9.]+)\s*\|\s*.*\|\s*$")
    dx: dict[str, float] = {}
    dy: dict[str, float] = {}
    for line in lines:
        m = row_re.match(line)
        if not m:
            continue
        typ, sid, val = m.group(1), m.group(2), float(m.group(3))
        if typ == "资产":
            dx[sid] = val
        else:
            dy[sid] = val
    if set(dx.keys()) != set(asset_ids):
        raise ParseValidationError("Asset turnover limits are incomplete.")
    if set(dy.keys()) != set(liab_ids):
        raise ParseValidationError("Liability turnover limits are incomplete.")
    return dx, dy


def _build_model(
    source_path: Path,
    case_id: str,
    case_name: str,
    currency: str,
    horizon: int,
    assets: list[dict[str, Any]],
    liabilities: list[dict[str, Any]],
    rates: dict[str, dict[str, float]],
    costs: dict[str, dict[str, float]],
    strategy: dict[str, float],
    dx: dict[str, float],
    dy: dict[str, float],
) -> dict[str, Any]:
    ai = [a["id"] for a in assets]
    lj = [l["id"] for l in liabilities]

    model = {
        "variables": [
            {
                "name": "x[t,Ai]",
                "role": "decision",
                "index_sets": {"t": f"1..{horizon}", "Ai": ai},
                "bounds": {
                    "lower_by_Ai": {a["id"]: a["lb"] for a in assets},
                    "upper_by_Ai": {a["id"]: a["ub"] for a in assets},
                },
                "unit": "million CNY",
            },
            {
                "name": "y[t,Lj]",
                "role": "decision",
                "index_sets": {"t": f"1..{horizon}", "Lj": lj},
                "bounds": {
                    "lower_by_Lj": {l["id"]: l["lb"] for l in liabilities},
                    "upper_by_Lj": {l["id"]: l["ub"] for l in liabilities},
                },
                "unit": "million CNY",
            },
            {
                "name": "s_liq[t]",
                "role": "slack",
                "index_sets": {"t": f"1..{horizon}"},
                "bounds": {"lower": 0.0, "upper": None},
            },
            {
                "name": "s_dur[t]",
                "role": "slack",
                "index_sets": {"t": f"1..{horizon}"},
                "bounds": {"lower": 0.0, "upper": None},
            },
            {
                "name": "r[t,Ai]",
                "role": "parameter",
                "index_sets": {"t": f"1..{horizon}", "Ai": ai},
                "values": {f"D{i:02d}": rates[f"D{i:02d}"] for i in range(1, horizon + 1)},
                "unit": "annualized rate",
            },
            {
                "name": "c[t,Lj]",
                "role": "parameter",
                "index_sets": {"t": f"1..{horizon}", "Lj": lj},
                "values": {f"D{i:02d}": costs[f"D{i:02d}"] for i in range(1, horizon + 1)},
                "unit": "annualized rate",
            },
            {
                "name": "w[Ai]",
                "role": "parameter",
                "index_sets": {"Ai": ai},
                "values": {a["id"]: a["liq_w"] for a in assets},
            },
            {
                "name": "d[Ai]",
                "role": "parameter",
                "index_sets": {"Ai": ai},
                "values": {a["id"]: a["dur"] for a in assets},
            },
            {
                "name": "delta_x[Ai]",
                "role": "parameter",
                "index_sets": {"Ai": ai},
                "values": {k: dx[k] for k in ai},
                "unit": "million CNY per day",
            },
            {
                "name": "delta_y[Lj]",
                "role": "parameter",
                "index_sets": {"Lj": lj},
                "values": {k: dy[k] for k in lj},
                "unit": "million CNY per day",
            },
            {"name": "total_assets_target", "role": "parameter", "lb": strategy["total_assets_target"], "ub": strategy["total_assets_target"]},
            {"name": "liquidity_threshold", "role": "parameter", "lb": strategy["liquidity_threshold"], "ub": strategy["liquidity_threshold"]},
            {"name": "duration_exposure_cap", "role": "parameter", "lb": strategy["duration_exposure_cap"], "ub": strategy["duration_exposure_cap"]},
            {"name": "wholesale_funding_cap", "role": "parameter", "lb": strategy["wholesale_funding_cap"], "ub": strategy["wholesale_funding_cap"]},
            {"name": "high_vol_assets_cap", "role": "parameter", "lb": strategy["high_vol_assets_cap"], "ub": strategy["high_vol_assets_cap"]},
            {"name": "single_asset_a15_cap", "role": "parameter", "lb": strategy["single_asset_a15_cap"], "ub": strategy["single_asset_a15_cap"]},
            {"name": "term_structure_buffer", "role": "parameter", "lb": strategy["term_structure_buffer"], "ub": strategy["term_structure_buffer"]},
            {"name": "retail_deposit_min_ratio", "role": "parameter", "lb": strategy["retail_deposit_min_ratio"], "ub": strategy["retail_deposit_min_ratio"]},
            {"name": "penalty_s_liq", "role": "parameter", "lb": strategy["penalty_s_liq"], "ub": strategy["penalty_s_liq"]},
            {"name": "penalty_s_dur", "role": "parameter", "lb": strategy["penalty_s_dur"], "ub": strategy["penalty_s_dur"]},
            {"name": "daily_rate_denominator", "role": "parameter", "lb": strategy["daily_rate_denominator"], "ub": strategy["daily_rate_denominator"]},
        ],
        "constraints": [
            {
                "name": "c_total_assets_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": strategy["total_assets_target"],
                "ub": strategy["total_assets_target"],
                "expression": "SUM(Ai, x[t,Ai])",
                "terms": [{"var": "x[t,Ai]", "coef": 1.0, "sum_over": "Ai"}],
            },
            {
                "name": "c_balance_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": 0.0,
                "ub": 0.0,
                "expression": "SUM(Ai, x[t,Ai]) - SUM(Lj, y[t,Lj])",
                "terms": [
                    {"var": "x[t,Ai]", "coef": 1.0, "sum_over": "Ai"},
                    {"var": "y[t,Lj]", "coef": -1.0, "sum_over": "Lj"},
                ],
            },
            {
                "name": "c_liquidity_cover_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": strategy["liquidity_threshold"],
                "ub": None,
                "expression": "SUM(Ai, w[Ai] * x[t,Ai]) + s_liq[t]",
                "terms": [{"var": "x[t,Ai]", "coef": "w[Ai]", "sum_over": "Ai"}, {"var": "s_liq[t]", "coef": 1.0}],
            },
            {
                "name": "c_duration_exposure_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": None,
                "ub": strategy["duration_exposure_cap"],
                "expression": "SUM(Ai, d[Ai] * x[t,Ai]) - s_dur[t]",
                "terms": [{"var": "x[t,Ai]", "coef": "d[Ai]", "sum_over": "Ai"}, {"var": "s_dur[t]", "coef": -1.0}],
            },
            {
                "name": "c_wholesale_funding_cap_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": None,
                "ub": strategy["wholesale_funding_cap"],
                "expression": "y[t,L06] + y[t,L07] + y[t,L08]",
                "terms": [{"var": "y[t,L06]", "coef": 1.0}, {"var": "y[t,L07]", "coef": 1.0}, {"var": "y[t,L08]", "coef": 1.0}],
            },
            {
                "name": "c_high_vol_assets_cap_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": None,
                "ub": strategy["high_vol_assets_cap"],
                "expression": "x[t,A10] + x[t,A11] + x[t,A12] + x[t,A14] + x[t,A15]",
                "terms": [
                    {"var": "x[t,A10]", "coef": 1.0},
                    {"var": "x[t,A11]", "coef": 1.0},
                    {"var": "x[t,A12]", "coef": 1.0},
                    {"var": "x[t,A14]", "coef": 1.0},
                    {"var": "x[t,A15]", "coef": 1.0},
                ],
            },
            {
                "name": "c_single_asset_a15_cap_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": None,
                "ub": strategy["single_asset_a15_cap"],
                "expression": "x[t,A15]",
                "terms": [{"var": "x[t,A15]", "coef": 1.0}],
            },
            {
                "name": "c_term_structure_match_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": None,
                "ub": strategy["term_structure_buffer"],
                "expression": "x[t,A09]+x[t,A10]+x[t,A11]+x[t,A12]-y[t,L01]-y[t,L02]-y[t,L03]-y[t,L04]",
                "terms": [
                    {"var": "x[t,A09]", "coef": 1.0},
                    {"var": "x[t,A10]", "coef": 1.0},
                    {"var": "x[t,A11]", "coef": 1.0},
                    {"var": "x[t,A12]", "coef": 1.0},
                    {"var": "y[t,L01]", "coef": -1.0},
                    {"var": "y[t,L02]", "coef": -1.0},
                    {"var": "y[t,L03]", "coef": -1.0},
                    {"var": "y[t,L04]", "coef": -1.0},
                ],
            },
            {
                "name": "c_retail_deposit_ratio_daily",
                "forall": {"t": f"1..{horizon}"},
                "lb": 0.0,
                "ub": None,
                "expression": "y[t,L01] + y[t,L02] - 0.45 * SUM(Lj, y[t,Lj])",
                "terms": [
                    {"var": "y[t,L01]", "coef": 0.55},
                    {"var": "y[t,L02]", "coef": 0.55},
                    {"var": "y[t,L03]", "coef": -0.45},
                    {"var": "y[t,L04]", "coef": -0.45},
                    {"var": "y[t,L05]", "coef": -0.45},
                    {"var": "y[t,L06]", "coef": -0.45},
                    {"var": "y[t,L07]", "coef": -0.45},
                    {"var": "y[t,L08]", "coef": -0.45},
                ],
            },
            {
                "name": "c_cross_day_holding_change_assets",
                "forall": {"t": "2..90", "Ai": ai},
                "lb": "-delta_x[Ai]",
                "ub": "delta_x[Ai]",
                "expression": "x[t,Ai] - x[t-1,Ai]",
                "terms": [{"var": "x[t,Ai]", "coef": 1.0}, {"var": "x[t-1,Ai]", "coef": -1.0}],
            },
            {
                "name": "c_cross_day_holding_change_liabilities",
                "forall": {"t": "2..90", "Lj": lj},
                "lb": "-delta_y[Lj]",
                "ub": "delta_y[Lj]",
                "expression": "y[t,Lj] - y[t-1,Lj]",
                "terms": [{"var": "y[t,Lj]", "coef": 1.0}, {"var": "y[t-1,Lj]", "coef": -1.0}],
            },
        ],
        "objective": {
            "sense": "max",
            "expression": "SUM(t=1..90, SUM(Ai, (r[t,Ai]/365) * x[t,Ai]) - SUM(Lj, (c[t,Lj]/365) * y[t,Lj]) - 0.40 * s_liq[t] - 0.25 * s_dur[t])",
            "terms": [
                {"var": "x[t,Ai]", "coef": "r[t,Ai]/365", "sum_over": ["t", "Ai"]},
                {"var": "y[t,Lj]", "coef": "-c[t,Lj]/365", "sum_over": ["t", "Lj"]},
                {"var": "s_liq[t]", "coef": -0.4, "sum_over": ["t"]},
                {"var": "s_dur[t]", "coef": -0.25, "sum_over": ["t"]},
            ],
            "constant": 0.0,
        },
        "metadata": {
            "source_document": str(source_path.as_posix()),
            "case_id": case_id,
            "case_name": case_name,
            "currency": currency,
            "horizon_days": horizon,
            "parse_mode": "indexed_compact",
            "index_sets": {"t": f"1..{horizon}", "Ai": ai, "Lj": lj},
            "assumptions": [
                "按parse-lp-input索引策略输出紧凑模型，不做逐日逐标的笛卡尔展开。",
                "仅文档中声明为按日的持仓变量、松弛变量、利率参数使用时间索引。",
                "参数变量（含标量参数）均显式列举在variables中。",
            ],
        },
    }
    return model


def _build_variable_name_map_cn() -> dict[str, str]:
    return {
        "x[t,Ai]": "第t天资产Ai持有量",
        "y[t,Lj]": "第t天负债Lj融资量",
        "s_liq[t]": "第t天流动性松弛变量",
        "s_dur[t]": "第t天久期松弛变量",
        "r[t,Ai]": "第t天资产Ai年化收益率参数",
        "c[t,Lj]": "第t天负债Lj年化成本率参数",
        "w[Ai]": "资产Ai流动性权重参数",
        "d[Ai]": "资产Ai久期参数",
        "delta_x[Ai]": "资产Ai跨日持仓变动上限参数",
        "delta_y[Lj]": "负债Lj跨日持仓变动上限参数",
        "total_assets_target": "每日总资产目标值",
        "liquidity_threshold": "每日最低流动性覆盖阈值",
        "duration_exposure_cap": "每日久期暴露上限",
        "wholesale_funding_cap": "每日批发融资上限",
        "high_vol_assets_cap": "每日高波动资产组合上限",
        "single_asset_a15_cap": "每日A15单一资产集中度上限",
        "term_structure_buffer": "期限结构匹配缓冲参数",
        "retail_deposit_min_ratio": "零售存款最低占比参数",
        "penalty_s_liq": "流动性松弛惩罚系数",
        "penalty_s_dur": "久期松弛惩罚系数",
        "daily_rate_denominator": "日化换算分母参数",
    }


def _extract_report_requirements(report_section: str) -> str:
    """Generate report requirements markdown from section-7 text."""
    if not report_section:
        return "# 报告要求（自动抽取）\n\n未在输入文档中找到“结果报告撰写指引”章节。\n"

    required_heads = re.findall(r"(?m)^####\s+(.+?)（必须）\s*$", report_section)
    structure_items = re.findall(r"(?m)^\d+\.\s+\*\*([^*]+)\*\*", report_section)

    lines: list[str] = []
    lines.append("# 报告要求（自动抽取）")
    lines.append("")
    lines.append("## 结构要求（来自源文档）")
    if structure_items:
        for item in structure_items:
            lines.append(f"- {item.strip()}")
    else:
        lines.append("- 未识别到结构清单。")
    lines.append("")
    lines.append("## 必备图表（必须）")
    if required_heads:
        for h in required_heads:
            lines.append(f"- {h.strip()}")
    else:
        lines.append("- 未识别到“必须”图表条目。")
    lines.append("")
    lines.append("## 原文摘录（结果报告章节）")
    lines.append("")
    lines.append(report_section.strip())
    lines.append("")
    return "\n".join(lines)


def _extract_report_template(report_section: str) -> str:
    """Extract reusable report template block."""
    if not report_section:
        return (
            "# 报告模板（自动抽取）\n\n"
            "未找到报告模板章节。可使用以下占位模板：\n\n"
            "```text\n"
            "在90天优化窗口内，方案实现累计净收益 <填入数值>，日均净收益 <填入数值>。\n"
            "硬约束满足率为 <填入百分比>，软约束触发主要集中在 <填入区间/场景>。\n"
            "资产结构方面，<填入资产类别> 份额提升显著，主要贡献来自 <原因>；\n"
            "负债结构方面，<填入负债类别> 占比变化显示资金稳定性 <提升/下降>。\n"
            "综合收益、风险与可执行性评估，建议 <继续执行/局部调参后执行> 当前优化方案。\n"
            "```\n"
        )

    template_sub = _extract_subsection(report_section, "7.5 结论写作模板（可直接复用）")
    if template_sub:
        block_match = re.search(r"```(?:text)?\n([\s\S]*?)```", template_sub)
        if block_match:
            body = block_match.group(1).strip("\n")
            return "# 报告模板（自动抽取）\n\n```text\n" + body + "\n```\n"

    # fallback: no code block found
    return (
        "# 报告模板（自动抽取）\n\n"
        "未识别到明确代码块模板，以下为章节内容摘录：\n\n"
        + template_sub.strip()
        + "\n"
    )


def _build_problem_description(problem_text: str) -> str:
    base = [
        "# ALM 90天优化问题描述（parse-lp-input 输出）",
        "",
        "## 1. 业务背景",
    ]
    if problem_text.strip():
        base.append(problem_text.strip())
    else:
        base.append("未从源文档中定位到“问题描述”章节，使用默认说明。")
    base.extend(
        [
            "",
            "## 2. 优化目标",
            "优化目标为最大化 90 天累计净收益：",
            "- 每日资产收益项：`SUM(Ai, (r[t,Ai]/365) * x[t,Ai])`",
            "- 每日负债成本项：`SUM(Lj, (c[t,Lj]/365) * y[t,Lj])`",
            "- 约束偏离惩罚项：`penalty_s_liq * s_liq[t]` 与 `penalty_s_dur * s_dur[t]`",
            "",
            "## 3. 决策变量与参数",
            "- 决策变量：`x[t,Ai]`、`y[t,Lj]`",
            "- 松弛变量：`s_liq[t]`、`s_dur[t]`",
            "- 输入参数：`r[t,Ai]`、`c[t,Lj]`、`w[Ai]`、`d[Ai]`、`delta_x[Ai]`、`delta_y[Lj]` 及策略参数",
            "",
            "## 4. 关键约束结构",
            "1. 每日总资产目标约束",
            "2. 每日资产负债平衡约束",
            "3. 流动性覆盖、久期暴露、集中度与结构约束",
            "4. 跨日持仓变动约束（逐标的）",
            "",
            "## 5. 输出文件",
            "1. `<stem>_parsed.json`",
            "2. `<stem>_problem_description.md`",
            "3. `<stem>_variable_name_map_cn.json`",
            "4. `<stem>_report_requirements.md`",
            "5. `<stem>_report_template.md`",
        ]
    )
    return "\n".join(base) + "\n"


def _validate_model(model: dict[str, Any], variable_name_map_cn: dict[str, str]) -> None:
    variables = model.get("variables", [])
    constraints = model.get("constraints", [])
    objective = model.get("objective", {})
    var_names = {v.get("name") for v in variables}

    # variable references in constraints/objective must exist
    referenced = set()
    for c in constraints:
        for t in c.get("terms", []):
            if "var" in t:
                referenced.add(t["var"])
    for t in objective.get("terms", []):
        if "var" in t:
            referenced.add(t["var"])
    def _canonical_ref(name: str) -> str:
        if name in var_names:
            return name
        # Canonicalize indexed instances to template variables.
        if re.match(r"^x\[t(?:-1)?,A\d{2}\]$", name):
            return "x[t,Ai]"
        if re.match(r"^y\[t(?:-1)?,L\d{2}\]$", name):
            return "y[t,Lj]"
        if name == "x[t-1,Ai]":
            return "x[t,Ai]"
        if name == "y[t-1,Lj]":
            return "y[t,Lj]"
        return name

    missing = sorted(v for v in referenced if _canonical_ref(v) not in var_names)
    if missing:
        raise ParseValidationError(f"Referenced variables missing from variables list: {missing}")

    # all parameter variables explicitly listed
    required_params = {
        "r[t,Ai]",
        "c[t,Lj]",
        "w[Ai]",
        "d[Ai]",
        "delta_x[Ai]",
        "delta_y[Lj]",
        "total_assets_target",
        "liquidity_threshold",
        "duration_exposure_cap",
        "wholesale_funding_cap",
        "high_vol_assets_cap",
        "single_asset_a15_cap",
        "term_structure_buffer",
        "retail_deposit_min_ratio",
        "penalty_s_liq",
        "penalty_s_dur",
        "daily_rate_denominator",
    }
    missing_params = sorted(p for p in required_params if p not in var_names)
    if missing_params:
        raise ParseValidationError(f"Missing required parameter variables: {missing_params}")

    # each variable should have Chinese mapping
    missing_cn = sorted(v for v in var_names if v not in variable_name_map_cn)
    if missing_cn:
        raise ParseValidationError(f"Variables missing Chinese mapping: {missing_cn}")

    # each constraint has terms and at least one bound
    for c in constraints:
        if not c.get("terms"):
            raise ParseValidationError(f"Constraint has empty terms: {c.get('name')}")
        if c.get("lb") is None and c.get("ub") is None:
            raise ParseValidationError(f"Constraint has neither lb nor ub: {c.get('name')}")


def parse_document(input_path: Path, output_dir: Path, prefix: str | None = None) -> ParseResult:
    text = input_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    case_id = _extract_first(text, r"\|\s*案例编号\s*\|\s*`([^`]+)`\s*\|", "unknown_case")
    case_name = _extract_first(text, r"\|\s*案例名称\s*\|\s*([^|\n]+?)\s*\|", "unknown_case_name")
    currency = _extract_first(text, r"\|\s*币种\s*\|\s*([^|\n]+?)\s*\|", "CNY")
    horizon_raw = _extract_first(text, r"\|\s*规划周期\s*\|\s*([0-9]+)天\s*\|", "90")
    horizon = int(horizon_raw)

    problem_text = _extract_section(text, "1.1 问题描述")
    report_section = _extract_section(text, "7. 结果报告撰写指引（最终交付）")

    assets = _parse_assets(lines)
    liabilities = _parse_liabilities(lines)
    ai = [a["id"] for a in assets]
    lj = [l["id"] for l in liabilities]
    rates, costs = _parse_daily_rates(lines, ai, lj, horizon)
    strategy = _parse_strategy_params(lines)
    dx, dy = _parse_turnover_limits(lines, ai, lj)

    model = _build_model(
        source_path=input_path,
        case_id=case_id,
        case_name=case_name,
        currency=currency,
        horizon=horizon,
        assets=assets,
        liabilities=liabilities,
        rates=rates,
        costs=costs,
        strategy=strategy,
        dx=dx,
        dy=dy,
    )
    variable_name_map_cn = _build_variable_name_map_cn()
    problem_md = _build_problem_description(problem_text)
    report_requirements_md = _extract_report_requirements(report_section)
    report_template_md = _extract_report_template(report_section)

    _validate_model(model, variable_name_map_cn)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = prefix or input_path.stem
    parsed_file = output_dir / f"{stem}_parsed.json"
    problem_file = output_dir / f"{stem}_problem_description.md"
    map_file = output_dir / f"{stem}_variable_name_map_cn.json"
    req_file = output_dir / f"{stem}_report_requirements.md"
    template_file = output_dir / f"{stem}_report_template.md"
    summary_file = output_dir / f"{stem}_parse_output.json"

    parsed_file.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    problem_file.write_text(problem_md, encoding="utf-8")
    map_file.write_text(json.dumps(variable_name_map_cn, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    req_file.write_text(report_requirements_md, encoding="utf-8")
    template_file.write_text(report_template_md, encoding="utf-8")

    summary_payload = {
        "model_json_file": str(parsed_file.relative_to(output_dir.parent) if parsed_file.is_relative_to(output_dir.parent) else parsed_file),
        "problem_description_md_file": str(problem_file.relative_to(output_dir.parent) if problem_file.is_relative_to(output_dir.parent) else problem_file),
        "variable_name_map_cn_file": str(map_file.relative_to(output_dir.parent) if map_file.is_relative_to(output_dir.parent) else map_file),
        "report_requirements_md_file": str(req_file.relative_to(output_dir.parent) if req_file.is_relative_to(output_dir.parent) else req_file),
        "report_template_md_file": str(template_file.relative_to(output_dir.parent) if template_file.is_relative_to(output_dir.parent) else template_file),
        "output_contract": {
            "model_json": "包含 variables / constraints / objective / metadata 的结构化LP定义",
            "problem_description_md": "用文字描述问题背景、目标、变量与约束结构",
            "variable_name_map_cn": "对 model_json.variables 中所有变量名给出中文名称",
            "report_requirements_md": "从输入文档抽取报告撰写要求（结构、必备图表、分析维度）",
            "report_template_md": "从输入文档抽取可直接复用的结论/报告模板",
        },
        "variable_name_map_cn": variable_name_map_cn,
    }
    summary_file.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ParseResult(
        model_json_file=parsed_file,
        problem_description_md_file=problem_file,
        variable_name_map_cn_file=map_file,
        report_requirements_md_file=req_file,
        report_template_md_file=template_file,
        parse_output_json_file=summary_file,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse LP input document into structured artifacts.")
    parser.add_argument("--input", required=True, help="Input document path, e.g. examples/alm_lp_full_test_input.md")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: input parent directory)")
    parser.add_argument("--prefix", default=None, help="Output file prefix (default: input stem)")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(json.dumps({"ok": False, "error": f"Input file not found: {input_path}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_path.parent
    try:
        result = parse_document(input_path=input_path, output_dir=output_dir, prefix=args.prefix)
    except ParseValidationError as exc:
        print(json.dumps({"ok": False, "error_type": "validation", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error_type": "unexpected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "outputs": {
            "model_json_file": str(result.model_json_file),
            "problem_description_md_file": str(result.problem_description_md_file),
            "variable_name_map_cn_file": str(result.variable_name_map_cn_file),
            "report_requirements_md_file": str(result.report_requirements_md_file),
            "report_template_md_file": str(result.report_template_md_file),
            "parse_output_json_file": str(result.parse_output_json_file),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

