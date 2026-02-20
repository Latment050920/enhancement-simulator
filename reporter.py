from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List


def _fmt(v: Any, nd: int = 4) -> str:
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _bar_row(label: str, value: float, max_value: float, color: str = "#4e79a7") -> str:
    width = 0 if max_value <= 0 else max(1.0, value / max_value * 100.0)
    return (
        f"<tr><td>{escape(label)}</td><td>{value:,.2f}</td>"
        f"<td><div style='background:#eee;width:100%;height:18px;border-radius:4px;'>"
        f"<div style='background:{color};width:{width:.2f}%;height:18px;border-radius:4px;'></div>"
        "</div></td></tr>"
    )


def _stacked_row(label: str, parts: Dict[str, float], max_total: float) -> str:
    colors = {
        "enhance_coins": "#4e79a7",
        "clear_coins": "#f28e2b",
        "diamond_coins": "#e15759",
        "tear_coins": "#76b7b2",
    }
    total = sum(parts.values())
    segs = []
    for k in ["enhance_coins", "clear_coins", "diamond_coins", "tear_coins"]:
        v = parts.get(k, 0.0)
        w = 0 if max_total <= 0 else (v / max_total * 100.0)
        segs.append(f"<div title='{k}:{v:,.2f}' style='height:18px;width:{w:.2f}%;background:{colors[k]};display:inline-block;'></div>")
    return f"<tr><td>{escape(label)}</td><td>{total:,.2f}</td><td>{''.join(segs)}</td></tr>"


def write_report(out_dir: Path, run_config: Dict[str, Any], results: List[Dict[str, Any]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_config": run_config,
        "results_count": len(results),
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    import csv

    if results:
        with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)

    top = sorted(results, key=lambda x: x.get("expected_server_coins", float("inf")))[:10]
    max_coins = max((r.get("expected_server_coins", 0.0) for r in top), default=1.0)
    bar_rows = "\n".join(
        _bar_row(r.get("strategy", "N/A"), float(r.get("expected_server_coins", 0.0)), max_coins)
        for r in top
    )

    max_total = max(
        (
            float(r.get("enhance_coins", 0.0))
            + float(r.get("clear_coins", 0.0))
            + float(r.get("diamond_coins", 0.0))
            + float(r.get("tear_coins", 0.0))
            for r in top
        ),
        default=1.0,
    )
    stacked_rows = "\n".join(
        _stacked_row(
            r.get("strategy", "N/A"),
            {
                "enhance_coins": float(r.get("enhance_coins", 0.0)),
                "clear_coins": float(r.get("clear_coins", 0.0)),
                "diamond_coins": float(r.get("diamond_coins", 0.0)),
                "tear_coins": float(r.get("tear_coins", 0.0)),
            },
            max_total,
        )
        for r in top
    )

    card = results[0] if results else {}
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Enhancement Report</title></head>
<body style='font-family:Arial,sans-serif;margin:20px;'>
<h1>Enhancement Simulation Report</h1>
<p>Generated at: {escape(summary['generated_at'])}</p>
<h2>指标卡片</h2>
<div style='display:flex;gap:12px;flex-wrap:wrap;'>
  <div style='padding:10px;border:1px solid #ddd;'>Expected Coins<br><b>{_fmt(card.get('expected_server_coins', 0.0), 2)}</b></div>
  <div style='padding:10px;border:1px solid #ddd;'>Expected Diamonds<br><b>{_fmt(card.get('expected_diamonds', 0.0), 3)}</b></div>
  <div style='padding:10px;border:1px solid #ddd;'>Expected Tears<br><b>{_fmt(card.get('expected_tears', 0.0), 3)}</b></div>
  <div style='padding:10px;border:1px solid #ddd;'>Success Rate(est.)<br><b>{_fmt(card.get('success_rate', 0.0), 4)}</b></div>
  <div style='padding:10px;border:1px solid #ddd;'>Runs N<br><b>{_fmt(run_config.get('N', 'N/A'))}</b></div>
</div>

<h2>Top10 Expected Coins（柱状图）</h2>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr><th>Strategy</th><th>Expected Coins</th><th>Bar</th></tr>
{bar_rows}
</table>

<h2>Coins 分解（堆叠柱）</h2>
<p>颜色: 蓝=强化费, 橙=清除费, 红=钻石折价, 绿=龙泪折价</p>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr><th>Strategy</th><th>Total</th><th>Stack</th></tr>
{stacked_rows}
</table>

<h2>误差条（95% CI）</h2>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>
<tr><th>Strategy</th><th>Mean</th><th>CI Low</th><th>CI High</th><th>StdErr</th></tr>
{''.join(f"<tr><td>{escape(r.get('strategy',''))}</td><td>{_fmt(r.get('expected_server_coins',0.0),2)}</td><td>{_fmt(r.get('ci95_coins_low',0.0),2)}</td><td>{_fmt(r.get('ci95_coins_high',0.0),2)}</td><td>{_fmt(r.get('std_err_coins',0.0),2)}</td></tr>" for r in top)}
</table>

<h2>分组对比</h2>
<p>若本次传入多个 G 或多个概率环境，结果会在 results.csv/summary.json 中按记录分组；可按 group_label 字段筛选。</p>
</body></html>"""
    report_path = out_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path
