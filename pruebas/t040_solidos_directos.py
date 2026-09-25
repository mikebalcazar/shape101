"""Sólidos directos  ·  0.21.8

Mike, 25-sep: *«Necesito los comandos para generar sólidos directo (prisma,
cilindro, pirámide, etc.)»*.

PRISMA, CILINDRO, CONO, ESFERA y PIRAMIDE nacen sin boceto: dos puntos de la
base en la ventana donde se está (con hule, osnap y coordenadas tecleadas,
como RECTANGULO o CIRCULO) y el alto tecleado. Quedan apoyados en el plano de
esa ventana y sus medidas se pueden cambiar en el historial.

Se mide contra el motor (volumen exacto, caras con nombre, plano correcto) y
contra la interfaz (el comando entero tecleado en la Superior y en la Frontal).
"""
from __future__ import annotations

import json
import urllib.request

from pruebas import comun, navegador as N

DESCRIPCION = "PRISMA, CILINDRO, CONO, ESFERA y PIRAMIDE: sólidos directos sobre el plano de la ventana"


def _post(base, ruta, cuerpo):
    req = urllib.request.Request(base + ruta, data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(base, ruta):
    with urllib.request.urlopen(base + ruta, timeout=30) as r:
        return json.loads(r.read())


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, base):
        N.cerrar_inicio(pagina)

        # --- el motor, forma por forma y plano por plano -------------------
        esperado = {
            "caja": ({"ancho": 300, "fondo": 200, "alto": 120}, 300 * 200 * 120, 6),
            "cilindro": ({"radio": 50, "alto": 100}, 3.14159265 * 50 ** 2 * 100, 3),
            "cono": ({"radio": 50, "alto": 100}, 3.14159265 * 50 ** 2 * 100 / 3, 2),
            "esfera": ({"radio": 40}, 4 / 3 * 3.14159265 * 40 ** 3, 1),
            "piramide": ({"ancho": 100, "fondo": 80, "alto": 90}, 100 * 80 * 90 / 3, 5),
        }
        for forma, (medidas, vol, ncaras) in esperado.items():
            for plano in ("XY", "XZ", "YZ"):
                st, m = _post(base, "/api/cuerpo/primitiva", {"forma": forma, "plano": plano, "base": [100, 50], **medidas})
                r.cierto(st == 200 and abs(m["volumen_mm3"] - vol) / vol < 1e-3 and len(m["caras"]) == ncaras,
                         f"{forma} en {plano}: volumen {vol:.0f} mm³ y {ncaras} caras", f"{st} {str(m)[:120]}")
        st, _ = _post(base, "/api/cuerpo/primitiva", {"forma": "toro", "radio": 10})
        r.igual(st, 400, "una forma que no existe se rechaza con 400")
        st, _ = _post(base, "/api/cuerpo/primitiva", {"forma": "caja", "ancho": 0, "fondo": 10, "alto": 10})
        r.igual(st, 400, "un prisma con lado cero se rechaza con 400")

        # La caja XZ está apoyada en la pared frontal y crece hacia -Y (hacia quien mira).
        st, m = _post(base, "/api/cuerpo/primitiva", {"forma": "caja", "plano": "XZ", "base": [0, 0], "ancho": 10, "fondo": 10, "alto": 10})
        ys = [m["caras"][i]["v"][1::3] for i in range(len(m["caras"]))]
        r.cierto(min(min(y) for y in ys) == -10 and max(max(y) for y in ys) == 0,
                 "en XZ la caja va de y=0 a y=−10: apoyada en la pared y crece hacia quien mira, como EXTRUIR", str(ys[:2]))

        h = _get(base, f"/api/cuerpo/{m['id']}/historial")
        campos = [c["clave"] for c in h["pasos"][0]["campos"]]
        r.igual(campos, ["ancho", "fondo", "alto"], "el historial ofrece ancho, fondo y alto para cambiarlos")

        # --- la interfaz: el comando tecleado --------------------------------
        pagina.evaluate("async () => { estado.prefs.rejilla = false; Ventanas.activar(0); pintar(); }")
        antes = len(_get(base, "/api/cuerpo/lista")["ids"])
        pagina.keyboard.type("PRISMA", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        pagina.keyboard.type("100,100", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(250)
        pagina.keyboard.type("400,300", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(250)
        pagina.keyboard.type("150", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(900)
        ids = _get(base, "/api/cuerpo/lista")["ids"]
        r.igual(len(ids), antes + 1, "PRISMA tecleado en la Superior hace una pieza")
        st, m = _post(base, "/api/entidades/varias", {"ids": [ids[-1]]})
        ent = m["entidades"][0]
        op = ent["operaciones"][0]
        r.cierto(op["op"] == "primitiva" and op["forma"] == "caja" and op["plano"] == "XY"
                 and op["ancho"] == 300 and op["fondo"] == 200 and op["alto"] == 150 and op["base"] == [100, 100],
                 "de 300 × 200 × 150 con la esquina en (100, 100), sobre XY", str(op))

        # Desde la Frontal el cilindro nace en XZ.
        pagina.evaluate("() => { Ventanas.activar(2); pintar(); }")
        antes = len(ids)
        pagina.keyboard.type("CILINDRO", delay=12); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(400)
        pagina.keyboard.type("500,200", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(250)
        pagina.keyboard.type("60", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(250)
        pagina.keyboard.type("80", delay=10); pagina.keyboard.press("Enter"); pagina.wait_for_timeout(900)
        ids = _get(base, "/api/cuerpo/lista")["ids"]
        r.igual(len(ids), antes + 1, "CILINDRO tecleado en la Frontal hace una pieza")
        st, m = _post(base, "/api/entidades/varias", {"ids": [ids[-1]]})
        op = m["entidades"][0]["operaciones"][0]
        r.cierto(op["op"] == "primitiva" and op["forma"] == "cilindro" and op["plano"] == "XZ"
                 and abs(op["radio"] - 60) < 1e-6 and op["alto"] == 80 and op["base"] == [500, 200],
                 "cilindro r60 × 80 con el centro en (500, 200) del plano XZ", str(op))

        r.cierto(pagina.evaluate("() => Comandos.existe ? Comandos.existe('PIRAMIDE') : true"), "PIRAMIDE está registrado")
        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
