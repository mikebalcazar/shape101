"""La Perspectiva anclada a su mira  ·  0.21.4

Mike, 24-sep: *«El paneo en la perspectiva hace un zoom involuntario. Deja fijo
el punto de referencia cuando paneo, no importa si se sale un poco de pantalla
los objetos. Pero haz un botón de extents donde recentres la pantalla en el
objeto seleccionado. Así se puede anclar en un nuevo punto el eje de rotación.»*

Lo que él llama paneo ahí es el giro con el botón central. Medido en main: el
pivote era el punto bajo el cursor **sobre el suelo** —lejos de la pieza si el
ratón no está encima— y el punto de fuga era el centro de la ventana; girando,
el centro de la pieza se iba de (703, 174) a (534, 74) y a (719, 265) en dos
arrastres. Eso es lo que se ve como zoom.

Ahora la Perspectiva tiene una **mira**: un punto del mundo que fija Extents
(el centro de lo seleccionado, o de todo). Es el pivote de orbitar y el punto
de fuga de la perspectiva. Girar la deja clavada en su píxel; panear corre la
imagen entera sin deformarla; Extents con algo seleccionado la mueve ahí.
"""
from __future__ import annotations

from pruebas import comun, navegador as N

DESCRIPCION = "la Perspectiva orbita alrededor de su mira, panea sin deformar, y Extents la ancla en lo seleccionado"

_MEDIR = """() => {
  const v = Ventanas.la(1); const g = estado.vista; estado.vista = v;
  const esq = []; for (const X of [0, 600]) for (const Y of [0, 400]) for (const Z of [0, 300]) esq.push(aPX(X, Y, Z));
  const mira = v.mira ? aPX(v.mira[0], v.mira[1], v.mira[2]) : null;
  const centro = aPX(300, 200, 150);
  estado.vista = g;
  return { rz: v.rz, rx: v.rx, mira: v.mira, miraPX: mira, centroPX: centro, esq, ox: v.ox, oy: v.oy, w: v.w, h: v.h };
}"""


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def correr(r: comun.Reporte) -> None:
    if not N.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with N.programa() as (pagina, _base):
        N.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        pagina.evaluate("""async () => {
          const id = await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY',
            puntos: [[0,0,0],[600,0,0],[600,400,0],[0,400,0]] }, 'base');
          Seleccion.alternar(id, false);
          await Comandos.correr('EXTRUIR 300');
          await new Promise((k) => setTimeout(k, 1200));
          estado.sel.clear(); encuadrar();
          await new Promise((k) => setTimeout(k, 400));
        }""")
        caja = pagina.evaluate("() => { const r = lienzo.getBoundingClientRect(); return {x: r.x, y: r.y}; }")
        m0 = pagina.evaluate(_MEDIR)
        r.cierto(m0["mira"] is not None and all(abs(a - b) < 1e-6 for a, b in zip(m0["mira"], [300, 200, 150])),
                 "Extents deja la mira en el centro de la pieza (300, 200, 150)", str(m0["mira"]))
        r.cierto(_dist(m0["miraPX"], m0["centroPX"]) < 0.01,
                 "y la mira se proyecta exactamente donde se proyecta ese centro")

        # --- girar: la mira no se mueve de su píxel ---------------------------
        # El ratón en una esquina de la ventana, lejos de la pieza: en main el
        # pivote era el punto bajo el cursor, y por eso la pieza se iba.
        x = caja["x"] + m0["ox"] + 40
        y = caja["y"] + m0["oy"] + m0["h"] - 40
        pagina.mouse.move(x, y, steps=3); pagina.mouse.down(button="middle")
        pagina.mouse.move(x + 120, y + 30, steps=8); pagina.mouse.up(button="middle")
        pagina.wait_for_timeout(300)
        m1 = pagina.evaluate(_MEDIR)
        r.cierto(abs(m1["rz"] - m0["rz"]) > 0.3, "el botón central gira la Perspectiva", f"rz {m0['rz']:.2f} → {m1['rz']:.2f}")
        r.cierto(_dist(m1["miraPX"], m0["miraPX"]) < 1,
                 f"y la mira se queda clavada en su píxel (se movió {_dist(m1['miraPX'], m0['miraPX']):.2f} px; en main, ~200)")
        pagina.mouse.move(x, y, steps=3); pagina.mouse.down(button="middle")
        pagina.mouse.move(x - 240, y - 60, steps=8); pagina.mouse.up(button="middle")
        pagina.wait_for_timeout(300)
        m2 = pagina.evaluate(_MEDIR)
        r.cierto(_dist(m2["miraPX"], m0["miraPX"]) < 1,
                 f"también girando para el otro lado ({_dist(m2['miraPX'], m0['miraPX']):.2f} px)")

        # --- panear: la imagen se corre entera, sin deformarse ----------------
        # Shift + botón central es pan en la Perspectiva.
        pagina.keyboard.down("Shift")
        pagina.mouse.move(x, y, steps=3); pagina.mouse.down(button="middle")
        pagina.mouse.move(x + 150, y + 40, steps=8); pagina.mouse.up(button="middle")
        pagina.keyboard.up("Shift")
        pagina.wait_for_timeout(300)
        m3 = pagina.evaluate(_MEDIR)
        r.cierto(abs(m3["rz"] - m2["rz"]) < 1e-9, "Shift + central panea (no gira)")
        desplaz = [[b[0] - a[0], b[1] - a[1]] for a, b in zip(m2["esq"], m3["esq"])]
        d0 = desplaz[0]
        peor = max(_dist(d, d0) for d in desplaz)
        r.cierto(_dist(d0, [0, 0]) > 50, f"la pieza se corrió ({d0[0]:.0f}, {d0[1]:.0f}) px")
        r.cierto(peor < 0.5,
                 f"y las ocho esquinas se corrieron lo mismo: panear no deforma (la que más, {peor:.2f} px de diferencia)")
        r.cierto(m3["mira"] == m2["mira"], "panear no mueve la mira del mundo: el pivote sigue donde estaba")

        # --- aMM deshace a aPX con la mira fuera del centro --------------------
        ida = pagina.evaluate("""() => {
          const v = Ventanas.la(1); const g = estado.vista; estado.vista = v;
          const peor = [[0, 0], [600, 0], [600, 400], [0, 400], [300, 200]].map((p) => {
            const q = aPX(p[0], p[1], 0); const b = aMM(q[0], q[1]);
            return Math.hypot(b[0] - p[0], b[1] - p[1]); });
          estado.vista = g; return Math.max(...peor); }""")
        r.cierto(ida < 1e-6, f"aMM deshace a aPX sobre el suelo con la mira descentrada (peor: {ida:.2e} mm)")

        # --- Extents con selección: la mira se va a lo seleccionado -----------
        pagina.evaluate("""async () => {
          const id = await crearEntidad({ tipo: 'circulo', centro: [2000, 1500], radio: 100, plano: 'XY' }, 'lejos');
          Seleccion.alternar(id, false);
          encuadrar();
          await new Promise((k) => setTimeout(k, 400));
        }""")
        m4 = pagina.evaluate(_MEDIR)
        r.cierto(all(abs(a - b) < 0.5 for a, b in zip(m4["mira"], [2000, 1500, 0])),   # el círculo va a trazos
                 "Extents con un círculo seleccionado ancla la mira en su centro (2000, 1500, 0)", str(m4["mira"]))
        enc = pagina.evaluate("""() => Ventanas.ventanas.filter((v) => v.w > 0).map((v) => {
          const g = estado.vista; estado.vista = v; const q = aPX(2000, 1500, 0); estado.vista = g;
          return Math.abs(q[0] - (v.ox + v.w / 2)) < v.w * 0.1 && Math.abs(q[1] - (v.oy + (v.h + 18) / 2)) < v.h * 0.1; })""")
        r.cierto(all(enc), "y las cuatro ventanas lo tienen al centro", str(enc))

        r.igual(pagina.errores, [], "y sin errores en la consola del navegador")
