"""Dibujar en la ventana donde está el ratón, sobre su plano  ·  0.21.1

Mike lo reportó el 23-sep: *«cuando quiero dibujar en la vista de perspectiva no
se dibuja sobre el plano xy, se dibuja como si estuviera en una vista frontal […]
el dibujo final sí se dibuja sobre el plano xy pero ya aparece en un lugar que no
tienes control»*. Y el 24-sep, sobre la 0.21.0: *«sigue sin dibujarse en
perspectiva de manera real sobre el plano xy cuando estás trazando»*.

Seguía porque el arreglo se escribió y **nunca llegó a main**. Esta prueba existe
para que eso no vuelva a poder pasar en silencio: si el arreglo desaparece, la
suite se cae.

Eran dos defectos que se ven como uno. Los dos, medidos aquí el 24-sep **antes**
de tocar nada:

1. **El punto se leía con la cámara de la ventana activa**, no con la de la
   ventana bajo el cursor. Apuntando al centro de la Perspectiva con la Superior
   activa, el programa tomaba un punto a **558 mm** del que se estaba señalando.
   Eso es «un lugar que no tienes control».

2. **El hule no recordaba su plano**, así que cada ventana lo pintaba con el
   suyo. El mismo punto salía en `[76.2, -62.3, 0]` en la Superior y en
   `[76.2, 0, -62.3]` en la Frontal: por eso lo trazado sobre el suelo se veía
   parado, «como en vista frontal».

Y la regla que protege la geometría: una vez tomado el primer punto, una ventana
de **otro** plano ya no adopta el trazo. Una línea no puede tener un extremo en
el suelo y el otro en la pared, así que el hule se queda quieto.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "dibujar en la ventana donde está el ratón, sobre su plano"

#: Lo que se medía antes del arreglo. Está aquí para que el fallo se lea solo.
DESVIO_DE_ANTES_MM = 558


def _caja(pagina):
    return pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")


def _centro(pagina, i: int):
    """El centro de la ventana i, en coordenadas del lienzo y bajo su título."""
    return pagina.evaluate(
        "(i) => { const v = Ventanas.ventanas[i];"
        "  return {x: v.ox + v.w / 2, y: v.oy + v.h / 2 + 30,"
        "          plano: v.plano, nombre: v.nombre}; }", i)


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        caja = _caja(pagina)
        persp = _centro(pagina, 1)        # 1 · Perspectiva
        frontal = _centro(pagina, 2)      # 2 · Frontal

        r.igual(persp["nombre"], "Perspectiva", "la ventana 1 es la Perspectiva")
        r.igual(persp["plano"], "XY", "y la Perspectiva dibuja sobre el suelo (XY)")

        # --- 1 · el trazo se toma donde apunta el ratón --------------------
        pagina.evaluate("() => { Ventanas.activar(0); pintar(); }")   # activa: Superior
        N.comando(pagina, "LINEA")
        pagina.mouse.move(caja["x"] + persp["x"], caja["y"] + persp["y"])
        pagina.wait_for_timeout(200)

        d = pagina.evaluate("""(p) => {
          // lo que el programa se quedó, con la cámara de la ventana activa
          const guardado = [estado.cursor.x, estado.cursor.y];
          // lo que el usuario señaló, leído con la cámara de la Perspectiva
          const g = estado.vista; estado.vista = Ventanas.la(1);
          const apuntado = aMM(p.x, p.y);
          estado.vista = g;
          return { activa: Ventanas.laActiva().nombre, guardado, apuntado };
        }""", persp)
        r.igual(d["activa"], "Perspectiva",
                "con el ratón dentro de la Perspectiva, manda la Perspectiva")
        lejos = max(abs(a - b) for a, b in zip(d["guardado"], d["apuntado"]))
        r.cierto(lejos < 5,
                 f"y el punto que se toma es el que señalaste (a {lejos:.1f} mm; "
                 f"antes del arreglo eran {DESVIO_DE_ANTES_MM})",
                 f"señalado {d['apuntado']}, tomado {d['guardado']}")

        # --- 2 · el hule lleva su plano ------------------------------------
        pagina.mouse.click(caja["x"] + persp["x"], caja["y"] + persp["y"])
        pagina.wait_for_timeout(200)
        pagina.mouse.move(caja["x"] + persp["x"] + 80, caja["y"] + persp["y"] - 40)
        pagina.wait_for_timeout(200)

        h = pagina.evaluate("() => estado.hule")
        r.igual(h and h.get("plano"), "XY",
                "el hule nace con el plano en el que se está trazando")

        mundos = pagina.evaluate("""() => {
          const h = estado.hule;
          return Ventanas.ventanas.filter((v) => v.w > 0).map((v) =>
            Planos.aMundo(h.plano || v.plano, h.b[0], h.b[1], 0));
        }""")
        iguales = all(max(abs(a - b) for a, b in zip(m, mundos[0])) < 1e-9 for m in mundos)
        r.cierto(iguales,
                 "y las cuatro ventanas lo pintan en el **mismo** punto del mundo",
                 f"salió en {[[round(k, 1) for k in m] for m in mundos]}")

        # --- 3 · el plano del comando protege la geometría ------------------
        antes = pagina.evaluate("() => [estado.hule.b[0], estado.hule.b[1]]")
        pagina.mouse.move(caja["x"] + frontal["x"], caja["y"] + frontal["y"])
        pagina.wait_for_timeout(200)
        despues = pagina.evaluate("""() => ({
          b: [estado.hule.b[0], estado.hule.b[1]],
          activa: Ventanas.laActiva().nombre })""")
        r.igual(despues["activa"], "Perspectiva",
                "con la línea ya empezada, una ventana de otro plano no se la lleva")
        quieto = (abs(antes[0] - despues["b"][0]) < 1e-9
                  and abs(antes[1] - despues["b"][1]) < 1e-9)
        r.cierto(quieto,
                 "y el hule se queda quieto en vez de saltar de plano a media línea",
                 f"de {antes} a {despues['b']}")

        # --- 4 · el control: sin punto tomado, la de abajo sí manda ---------
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(150)
        pagina.evaluate("() => { Ventanas.activar(1); pintar(); }")   # activa: Perspectiva
        N.comando(pagina, "LINEA")
        sup = _centro(pagina, 0)
        pagina.mouse.move(caja["x"] + sup["x"], caja["y"] + sup["y"])
        pagina.wait_for_timeout(200)
        r.igual(pagina.evaluate("() => Ventanas.laActiva().nombre"), "Superior",
                "sin punto tomado todavía, la ventana bajo el cursor manda (el control)")
        pagina.keyboard.press("Escape")

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
