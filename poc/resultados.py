"""Escribe poc/RESULTADOS.md a partir de lo que midió la última corrida.

La tabla de números sale de los `r.numero(...)` de cada prueba; el veredicto
por paso y las notas vienen de VEREDICTOS, que se escriben a mano **después**
de mirar los números, nunca antes. Mike decide con este archivo.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent

# paso → (título, veredicto, notas). Se rellena conforme cada paso se mide.
VEREDICTOS: dict[str, tuple[str, str, str]] = {}
_ARCHIVO = RAIZ / "veredictos.json"


def _veredictos() -> dict:
    return json.loads(_ARCHIVO.read_text(encoding="utf-8")) if _ARCHIVO.exists() else {}


def escribir(filas=None) -> pathlib.Path:
    medidas = json.loads((RAIZ / "salida" / "medidas.json").read_text(encoding="utf-8"))
    ver = _veredictos()
    hoy = dt.date.today().isoformat()
    out = ["# shape101 · resultados de la prueba de concepto", "",
           f"*Generado por `python poc/verificar.py --resultados` el {hoy}. Los números son de esa corrida; "
           "el veredicto de cada paso está escrito a mano en `poc/veredictos.json` después de mirarlos.*", ""]
    p0 = RAIZ / "p0.md"
    if p0.exists():
        out += [p0.read_text(encoding="utf-8").rstrip(), ""]
    pasos = ["P1", "P2", "P3", "P4", "P5", "P6"]
    for p in pasos:
        v = ver.get(p, {})
        out.append(f"## {p} · {v.get('titulo', '(sin medir)')}")
        out.append("")
        out.append(f"**Veredicto: {v.get('veredicto', 'sin medir')}.** {v.get('notas', '')}".rstrip())
        out.append("")
        filas_p = [m for m in medidas if str(m['que']).startswith(p + " ") or str(m['que']).startswith(p + ":")]
        if filas_p:
            out.append("| Qué | Valor | Umbral | Cumple |")
            out.append("|---|---:|---|---|")
            for m in filas_p:
                val = f"{m['valor']} {m['unidad']}".strip()
                cumple = "" if m["cumple"] is None else ("sí" if m["cumple"] else "NO")
                out.append(f"| {m['que']} | {val} | {m['umbral']} | {cumple} |")
            out.append("")
    ruta = RAIZ / "RESULTADOS.md"
    ruta.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  {ruta.relative_to(RAIZ.parent)} reescrito")
    return ruta


if __name__ == "__main__":
    escribir()
