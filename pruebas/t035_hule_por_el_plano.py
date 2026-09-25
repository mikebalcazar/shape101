"""El trazo en curso se pinta acostado en su plano  ·  0.21.2

Mike, 24-sep, con el rectángulo a medio trazar en la Perspectiva: *«debería
estarse trazando sobre el plano xy VISUALMENTE, ir representando el dibujo real
sobre el XY de la perspectiva»* — y una foto de Rhino de cómo debe verse: un
paralelogramo acostado en el suelo, y de canto, una raya, en la Frontal.

La línea ya iba bien desde la 0.21.1. Pero el rectángulo se pintaba con
`c.rect` entre dos esquinas proyectadas, y `c.rect` sólo sabe hacer cuadros
derechos de pantalla: en la Perspectiva salía flotando. El círculo y el arco
igual, con `c.arc` y un radio en píxeles: un círculo sobre el suelo, visto en
perspectiva, es una elipse.

Se comprueba con tinta, no con estado: se leen los píxeles del lienzo de
encima —donde vive el hule— a la mitad de cada lado del paralelogramo que le
toca al rectángulo sobre el suelo. Contra main, los cuatro salen en blanco.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "el trazo en curso se pinta acostado en su plano, también en perspectiva"

# Lo que corre en la página para leer tinta en el lienzo de encima, alrededor de
# un punto (6 × 6 px). Sin rejilla: la única tinta que hay es la del hule y la
# cruz del cursor.
_TINTA = """
  const c = encima.getContext('2d'); const dpr = encima.width / encima.clientWidth;
  const tinta = (x, y) => {
    const d = c.getImageData(Math.round((x - 3) * dpr), Math.round((y - 3) * dpr),
                             Math.round(6 * dpr), Math.round(6 * dpr)).data;
    let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 40) n++;
    return n;
  };
  const enPersp = (f) => { const g = estado.vista; estado.vista = Ventanas.la(1); const r = f(); estado.vista = g; return r; };
  const P = (plano, x, y) => { const m = Planos.aMundo(plano || "XY", x, y, 0); return aPX(m[0], m[1], m[2]); };
"""


def _preparar(pagina):
    N.cerrar_inicio(pagina)
    pagina.set_viewport_size({"width": 1280, "height": 820})
    pagina.wait_for_timeout(400)
    pagina.evaluate("() => { estado.prefs.rejilla = false; invalidarPlano(); pintar(); }")
    caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")
    v = pagina.evaluate("() => { const v = Ventanas.la(1); return {x: v.ox + v.w / 2, y: v.oy + v.h / 2 + 30}; }")
    return caja, v


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        caja, v = _preparar(pagina)
        ox, oy = caja["x"] + v["x"], caja["y"] + v["y"]

        # --- el rectángulo: un paralelogramo acostado en el suelo -----------
        N.comando(pagina, "RECTANGULO")
        pagina.mouse.move(ox, oy); pagina.wait_for_timeout(150)
        pagina.mouse.click(ox, oy); pagina.wait_for_timeout(150)
        pagina.mouse.move(ox + 90, oy - 30); pagina.wait_for_timeout(250)

        d = pagina.evaluate("() => {" + _TINTA + """
          pintarYa();
          const h = estado.hule;
          const esq = enPersp(() => [[h.a[0], h.a[1]], [h.b[0], h.a[1]], [h.b[0], h.b[1]], [h.a[0], h.b[1]]]
                                     .map(([x, y]) => P(h.plano, x, y)));
          const medio = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
          const lados = [0, 1, 2, 3].map((i) => medio(esq[i], esq[(i + 1) % 4]));
          // el cuadro derecho que abarca las cuatro esquinas: arriba y abajo,
          // lejos de la cruz del cursor
          const xs = esq.map((p) => p[0]), ys = esq.map((p) => p[1]);
          const xm = (Math.min(...xs) + Math.max(...xs)) / 2;
          const derecho = [[xm, Math.min(...ys)], [xm, Math.max(...ys)]];
          const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
          return { tipo: h.tipo, plano: h.plano,
                   lados: lados.map((p) => tinta(p[0], p[1])),
                   derecho: derecho.map((p) => tinta(p[0], p[1])),
                   aparte: Math.min(...derecho.map((p) => Math.min(...lados.map((l) => dist(p, l))))),
                   inclinado: Math.abs(esq[0][1] - esq[1][1]) };
        }""")
        r.igual(d["tipo"], "caja", "el hule del rectángulo es una caja")
        r.igual(d["plano"], "XY", "y lleva el plano del suelo")
        r.cierto(d["inclinado"] > 5,
                 f"en la Perspectiva el lado de arriba sale inclinado ({d['inclinado']:.1f} px): es un paralelogramo",
                 "las esquinas quedaron alineadas en pantalla")
        r.cierto(all(n > 0 for n in d["lados"]),
                 f"hay tinta a la mitad de los cuatro lados del paralelogramo ({d['lados']})",
                 f"lados sin tinta: {d['lados']}")
        r.cierto(d["aparte"] > 8 and all(n == 0 for n in d["derecho"]),
                 f"y ninguna en el cuadro derecho de pantalla, a {d['aparte']:.0f} px de ahí ({d['derecho']})",
                 f"derecho: {d['derecho']}, a {d['aparte']:.0f} px")
        pagina.keyboard.press("Escape"); pagina.wait_for_timeout(150)

        # --- el círculo: una elipse, no un círculo de pantalla ---------------
        N.comando(pagina, "CIRCULO")
        # En pasos: con un solo salto la cajita de coordenadas, que se quedó
        # donde acabó el rectángulo, no alcanza a seguir al ratón y se traga
        # el clic. Un ratón de verdad nunca salta.
        pagina.mouse.move(ox, oy, steps=6); pagina.wait_for_timeout(150)
        pagina.mouse.click(ox, oy); pagina.wait_for_timeout(150)
        pagina.mouse.move(ox + 70, oy - 40); pagina.wait_for_timeout(250)

        e = pagina.evaluate("() => {" + _TINTA + """
          pintarYa();
          const h = estado.hule;
          if (!h || h.tipo !== "circulo") return { tipo: h && h.tipo };
          const ang = [30, 120, 210, 300];   // lejos de la cruz del cursor
          const sobreElipse = enPersp(() => ang.map((a) => {
            const t = a * Math.PI / 180;
            return P(h.plano, h.c[0] + h.r * Math.cos(t), h.c[1] + h.r * Math.sin(t)); }));
          // el círculo de pantalla que se pintaba antes: centro proyectado y
          // radio en píxeles, en los mismos ángulos
          const cen = enPersp(() => P(h.plano, h.c[0], h.c[1]));
          const rpx = h.r * Ventanas.la(1).escala;
          const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
          const pantalla = ang.map((a) => { const t = a * Math.PI / 180;
            return [cen[0] + rpx * Math.cos(t), cen[1] - rpx * Math.sin(t)]; })
            .filter((p) => Math.min(...sobreElipse.map((q) => dist(p, q))) > 10);
          const radios = sobreElipse.map((p) => dist(p, cen));
          return { tipo: h.tipo, plano: h.plano,
                   elipse: sobreElipse.map((p) => tinta(p[0], p[1])),
                   pantalla: pantalla.map((p) => tinta(p[0], p[1])),
                   achatado: Math.max(...radios) / Math.min(...radios) };
        }""")
        r.igual(e.get("tipo"), "circulo", "el hule del círculo es un círculo")
        r.cierto(e.get("achatado", 1) > 1.15,
                 f"en la Perspectiva se ve achatado ({e.get('achatado', 1):.2f} a 1): es una elipse",
                 "salió redondo, como un círculo de pantalla")
        r.cierto(all(n > 0 for n in e.get("elipse", [])),
                 f"hay tinta sobre la elipse en cuatro ángulos ({e.get('elipse')})",
                 f"elipse sin tinta: {e.get('elipse')}")
        r.cierto(all(n == 0 for n in e.get("pantalla", [])),
                 f"y ninguna sobre el círculo de pantalla de antes ({e.get('pantalla')})",
                 f"pantalla: {e.get('pantalla')}")
        pagina.keyboard.press("Escape")

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
