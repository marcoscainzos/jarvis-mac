from __future__ import annotations

from datetime import datetime
from html import escape
import json
from pathlib import Path


def build_voice_report(results_path: Path, output_path: Path) -> Path:
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        results = []

    total = len(results)
    passed = sum(bool(item.get("passed")) for item in results)
    latencies = [float(item["latency_seconds"]) for item in results if item.get("latency_seconds") is not None]
    errors = [float(item["word_error_rate"]) for item in results if item.get("word_error_rate") is not None]
    activation_hits = sum(
        bool(item.get("expected_wake")) == bool(item.get("detected_wake"))
        for item in results
    )
    average_latency = sum(latencies) / len(latencies) if latencies else None
    average_error = sum(errors) / len(errors) if errors else None

    def metric(value: str, label: str, note: str) -> str:
        return f'<article class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></article>'

    cards = "".join((
        metric(f"{passed}/{total}" if total else "—", "Pruebas correctas", "Grabaciones evaluadas"),
        metric(f"{average_latency:.2f} s" if average_latency is not None else "—", "Velocidad", "Media de transcripción"),
        metric(f"{(1-average_error)*100:.1f}%" if average_error is not None else "Pendiente", "Precisión", "Requiere texto original"),
        metric(f"{activation_hits}/{total}" if total else "—", "Activación", "Aciertos al despertar"),
    ))

    rows = ""
    for item in results:
        status = "Correcto" if item.get("passed") else "Revisar"
        precision = (
            f"{(1-float(item['word_error_rate']))*100:.1f}%"
            if item.get("word_error_rate") is not None else "Sin referencia"
        )
        rows += (
            f'<tr><td><b>{escape(Path(str(item.get("file", ""))).name)}</b><small>{escape(str(item.get("transcript", "")))}</small></td>'
            f'<td>{float(item.get("latency_seconds", 0)):.2f} s</td><td>{precision}</td>'
            f'<td><span class="pill {"ok" if item.get("passed") else "bad"}">{status}</span></td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="4" class="empty">Todavía no hay grabaciones evaluadas.</td></tr>'

    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Informe de voz · Iris</title>
<style>:root{{--bg:#07121b;--card:#0e202d;--line:#1e3a49;--cyan:#67e8f9;--text:#e8f6fb;--muted:#8eabb8}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 20% 0,#123346,var(--bg) 45%);color:var(--text);font:15px -apple-system,BlinkMacSystemFont,sans-serif;min-height:100vh}}main{{max-width:1080px;margin:auto;padding:64px 28px}}header{{display:flex;justify-content:space-between;align-items:end;margin-bottom:36px}}h1{{font-size:44px;letter-spacing:-2px;margin:8px 0}}.eyebrow{{color:var(--cyan);text-transform:uppercase;letter-spacing:.16em;font-size:11px}}header p,small{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}.metric{{background:#0e202dcc;border:1px solid var(--line);border-radius:18px;padding:22px;display:grid;gap:8px;backdrop-filter:blur(12px)}}.metric span{{color:var(--muted);font-size:12px}}.metric strong{{font-size:29px;color:var(--cyan)}}table{{width:100%;border-collapse:collapse;background:#0b1c27cc;border:1px solid var(--line);border-radius:18px;overflow:hidden}}th,td{{padding:17px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.1em}}td small{{display:block;max-width:620px;margin-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.pill{{padding:7px 10px;border-radius:999px;font-size:12px}}.ok{{background:#123c39;color:#83f1cf}}.bad{{background:#48252b;color:#ff9ba8}}.empty{{text-align:center;color:var(--muted);padding:48px}}footer{{margin-top:22px;color:var(--muted);font-size:12px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}h1{{font-size:34px}}}}</style></head>
<body><main><header><div><div class="eyebrow">I Run Important Shit</div><h1>Informe de voz</h1><p>Precisión, activación y velocidad medidas localmente.</p></div><small>{datetime.now():%d/%m/%Y · %H:%M}</small></header><section class="grid">{cards}</section><table><thead><tr><th>Muestra</th><th>Tiempo</th><th>Precisión</th><th>Resultado</th></tr></thead><tbody>{rows}</tbody></table><footer>El audio y las transcripciones permanecen en este Mac. Ningún dato se envía a GitHub.</footer></main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
