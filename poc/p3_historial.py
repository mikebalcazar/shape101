"""P3 · Historial regenerable y referencias estables.

1. Un documento de cinco operaciones (boceto, extruir, restar barreno,
   redondear cuatro aristas verticales, empujar la cara de arriba) se
   regenera desde cero y da las medidas de la fórmula.
2. Se cambia una cota del boceto de abajo (ancho 900 → 1000) y se regenera:
   las referencias por nombre («lado[1]», «arriba», «lado[0]|lado[1]») tienen
   que seguir señalando la misma cara o arista, ahora en su sitio nuevo. Se
   mide también la alternativa del documento (centro + normal + área con
   tolerancia) para decir con números si sobrevive al cambio.
3. Tiempo de regeneración con 10, 30 y 60 operaciones (umbral: < 1 s con 30).
"""
from __future__ import annotations

import math

from poc import comun
from app.motor import historial, nombres

DESCRIPCION = "historial JSON, regenerar tras cambiar una cota, nombres estables"
W, H, T, RB, RE, EMPUJE = 900.0, 600.0, 18.0, 80.0, 20.0, 10.0


def rect(w, h):
    return [{"tipo": "polilinea", "cerrada": True, "puntos": [[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0]]}]


def circ(x, y, r):
    return [{"tipo": "circulo", "centro": [x, y], "radio": r}]


def documento(w=W):
    return [
        {"op": "boceto", "entidades": rect(w, H)},
        {"op": "extruir", "mm": T},
        {"op": "restar", "entidades": circ(w / 2, H / 2, RB), "mm": T},
        {"op": "redondear", "aristas": ["lado[0]|lado[1]", "lado[1]|lado[2]", "lado[2]|lado[3]", "lado[3]|lado[0]"], "r": RE},
        {"op": "empujar_cara", "cara": "arriba", "mm": EMPUJE},
    ]


def volumen(w):
    return (w * H - (4 - math.pi) * RE ** 2 - math.pi * RB ** 2) * (T + EMPUJE)


def _largo(n_ops):
    """Un historial de n operaciones: base + barrenos y empujes alternados."""
    ops = [{"op": "boceto", "entidades": rect(W, H)}, {"op": "extruir", "mm": T}]
    k = 0
    while len(ops) < n_ops:
        if k % 3 == 2:
            ops.append({"op": "empujar_cara", "cara": "arriba", "mm": 1.0})
        else:
            x = 60 + (k * 97) % (W - 120)
            y = 60 + (k * 61) % (H - 120)
            ops.append({"op": "restar", "entidades": circ(x, y, 12), "mm": T + 200})
        k += 1
    return ops[:n_ops]


def correr(r: comun.Reporte):
    # 1 · regenerar y medir
    reg = historial.regenerar(documento())
    bb = reg.solido.bounding_box()
    r.casi(bb.size.X, W, "el sólido regenerado mide 900 de ancho", 1e-6)
    r.casi(bb.size.Z, T + EMPUJE, "la cara de arriba empujada 10 deja 28 de espesor", 1e-6)
    r.casi(reg.solido.volume, volumen(W), "el volumen es el de la fórmula (tablero − esquinas − barreno) × 28", 1e-2)
    r.igual(len(reg.nombrador.caras), len(reg.solido.faces()), "todas las caras del sólido tienen nombre")
    r.cierto(not any(n.startswith("anonima") for n in reg.nombrador.caras), "ninguna cara quedó sin nombre")
    r.cierto({"arriba", "abajo", "lado[0]", "lado[1]", "lado[2]", "lado[3]", "restar[2]/lado[0]"} <= set(reg.nombrador.caras),
             "están arriba, abajo, los 4 lados y el barreno")
    r.igual(sum(1 for n in reg.nombrador.caras if n.startswith("redondeo[3]/") and "~" not in n), 4, "los 4 redondeos tienen nombre propio")
    r.numero("P3 caras extra tras empujar «arriba» (misma superficie que un redondeo, el kernel no las funde)",
             sum(1 for n in reg.nombrador.caras if "~" in n), "")
    r.numero("P3 regenerar 5 operaciones", round(reg.ms, 1), "ms")

    # 2 · cambiar una cota de abajo y ver quién sobrevive
    huella_lado1 = nombres.huella(reg.nombrador.cara("lado[1]"))
    huella_arriba = nombres.huella(reg.nombrador.cara("arriba"))
    reg2 = historial.regenerar(documento(w=1000))
    bb2 = reg2.solido.bounding_box()
    r.casi(bb2.size.X, 1000, "tras cambiar la cota, el sólido mide 1000 de ancho", 1e-6)
    r.casi(reg2.solido.volume, volumen(1000), "tras cambiar la cota, el volumen sigue la fórmula (redondeos y empuje siguen ahí)", 1e-2)
    lado1 = reg2.nombrador.cara("lado[1]")
    r.casi(lado1.center().X, 1000, "«lado[1]» sigue siendo el lado derecho, ahora en x = 1000", 1e-6)
    r.casi(reg2.nombrador.cara("arriba").center().Z, T + EMPUJE, "«arriba» sigue siendo la cara de arriba, a z = 28", 1e-6)
    aristas2 = reg2.nombrador.aristas(reg2.solido)
    r.cierto("lado[0]|lado[1]" not in aristas2, "la arista «lado[0]|lado[1]» ya no existe como tal: la sustituyó su redondeo")
    r.cierto("lado[1]|redondeo[3]/lado[0]|lado[1]" in aristas2 or "redondeo[3]/lado[0]|lado[1]|lado[1]" in aristas2,
             "la arista entre el lado derecho y su redondeo se nombra sola")
    caras2 = list(reg2.solido.faces())
    r.cierto(nombres.por_huella(caras2, huella_lado1) is None,
             "la huella geométrica (centro+normal+área) NO encuentra el lado derecho tras el cambio: se movió 100 mm")
    r.cierto(nombres.por_huella(caras2, huella_arriba) is None,
             "la huella geométrica tampoco encuentra «arriba»: cambió su centro y su área")
    r.numero("P3 nombres por derivación sobreviven a cambiar una cota de abajo", "sí", "", umbral="sí/no", cumple=True)
    r.numero("P3 huella geométrica (centro+normal+área) sobrevive al cambio", "no (0 de 2 caras)", "", umbral="sí/no", cumple=None)

    # una referencia que no existe se rechaza con la lista de las que hay
    try:
        reg2.nombrador.cara("lado[9]")
        r.cierto(False, "pedir una cara que no existe levanta un error claro")
    except KeyError as e:
        r.cierto("hay:" in str(e), "pedir una cara que no existe levanta un error claro con la lista de nombres")

    # 3 · tiempos con historiales largos (regeneración completa, sin caché)
    for n, umbral in ((10, ""), (30, "< 1 s"), (60, "")):
        ops = _largo(n)
        reg_n = historial.regenerar(ops)
        r.cierto(reg_n.solido.is_valid, f"el sólido de {n} operaciones es válido")
        r.igual(len(reg_n.tiempos), n, f"se ejecutaron las {n} operaciones")
        r.numero(f"P3 regenerar {n} operaciones ({sum(1 for o in ops if o['op']=='restar')} barrenos, "
                 f"{sum(1 for o in ops if o['op']=='empujar_cara')} empujes)", round(reg_n.ms), "ms",
                 umbral=umbral, cumple=(reg_n.ms < 1000) if umbral else None)
        peor = max(reg_n.tiempos, key=lambda t: t["ms"])
        r.numero(f"P3 la operación más lenta con {n}", f"{peor['op']} {peor['ms']:.0f}", "ms")
