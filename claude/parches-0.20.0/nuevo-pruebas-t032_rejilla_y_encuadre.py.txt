"""La rejilla y el encuadre de las cuatro ventanas  ·  0.20.0

Mike, 20-sep: *«cuando recién abres shape101, la ventana superior y la de
perspectiva tienen todo descentrado el grid, y la frontal y lateral no tienen
grid… el grid debería ser infinito, es una referencia»*.

Eran cuatro defectos distintos con una misma cara, y esta prueba los fija uno
por uno para que no vuelvan:

1. **El cero al centro de las cuatro.** Las tres ventanas que no eran la
   Superior nacían con el origen del mundo **en su esquina de arriba a la
   izquierda**. No era sólo feo: una pieza levantada después caía fuera de la
   Perspectiva, no se le podía picar una cara, y `JALAR` y `CRECER` se quedaban
   sin cara que mover. Por eso el punto 5 de aquí abajo mide justamente eso.
2. **Cada ventana pinta su plano.** La rejilla iba siempre sobre el suelo (XY);
   desde la Frontal el suelo se ve de canto, así que ahí no se pintaba nada.
3. **El interruptor REJILLA apaga de verdad.** El visor preguntaba por
   `ctx.rejilla` y nadie se lo mandaba nunca: el botón, el comando y F7
   cambiaban la preferencia y la pantalla se quedaba igual.
4. **Infinita.** Era un cuadro fijo de mil milímetros alrededor del cero. Se
   comprueba alejándose y acercándose una barbaridad: a cualquier zoom la
   rejilla tiene que llegar a las cuatro orillas de su ventana.
5. **Se puede picar una cara en la Perspectiva**, que es lo que Mike reportó
   como «CRECER no sirvió» y era este mismo defecto visto desde el otro lado.
"""
from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "la rejilla: por ventana, por plano e infinita; y el cero al centro"

# Las cuatro, con el plano que a cada una le toca pintar.
VENTANAS = [("Superior", "XY"), ("Perspectiva", None), ("Frontal", "XZ"), ("Lateral", "YZ")]


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: esta prueba se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        # La barra a la izquierda, como la tiene Mike: anclada arriba flota
        # encima del lienzo y se come los clics de la prueba.
        pagina.evaluate("""() => { const h = document.getElementById('herramientas');
            if (h) h.dataset.anclaje = 'izquierda'; window.dispatchEvent(new Event('resize')); }""")
        # De limpio: el archivo de preferencias sobrevive entre corridas y una
        # prueba que empieza con lo que dejó la anterior no prueba nada.
        pagina.evaluate("""async () => { await guardarPrefs({ rejilla: true, rejilla_paso: 10,
            rejilla_ventanas: {Superior:true, Perspectiva:true, Frontal:true, Lateral:true},
            rejilla_planos: {XY:true, XZ:true, YZ:true} }); }""")
        pagina.mouse.move(5, 800)
        pagina.wait_for_timeout(500)

        _el_cero_al_centro(r, pagina)
        _el_plano_de_cada_una(r, pagina)
        _los_interruptores(r, pagina)
        _infinita(r, pagina)
        _se_puede_picar_una_cara(r, pagina)


# --- 1. el cero al centro de las cuatro ------------------------------------

def _el_cero_al_centro(r: comun.Reporte, pagina) -> None:
    # Se reencuadra a mano primero: `adoptar` corre en el primer pintado, con el
    # lienzo del tamaño que tuviera entonces, y la prueba lo redimensiona
    # después. Lo que se fija aquí es la regla, no el instante.
    pagina.evaluate("() => { Ventanas.centrarEnOrigen(); invalidarPlano(); pintar(); }")
    pagina.wait_for_timeout(200)
    d = pagina.evaluate("""() => {
      const o = {};
      for (const v of Ventanas.ventanas) {
        const g = estado.vista; estado.vista = v;
        const q = window.aPX(0, 0, 0); estado.vista = g;
        o[v.nombre] = [Math.round(q[0] - (v.ox + v.w / 2)),
                       Math.round(q[1] - (v.oy + v.h / 2))];
      }
      return o; }""")
    for nombre, _ in VENTANAS:
        dx, dy = d[nombre]
        # En Y sobra la mitad de la franja del título: el centro útil de la
        # ventana no es el centro del rectángulo, es el del hueco que queda.
        r.cierto(abs(dx) <= 1 and abs(dy) <= 12,
                 f"al abrir, el cero cae en el centro de la {nombre}",
                 f"se corrió {dx}, {dy} píxeles")


# --- 2. cada ventana pinta el plano que le toca ----------------------------

def _el_plano_de_cada_una(r: comun.Reporte, pagina) -> None:
    d = pagina.evaluate("""() => {
      const o = {};
      for (const v of Ventanas.ventanas) o[v.nombre] = Ventanas.planosRejilla(v);
      return o; }""")
    for nombre, plano in VENTANAS:
        if plano:
            r.igual(d[nombre], [plano],
                    f"la {nombre} pinta su plano {plano}, no siempre el suelo")
    r.igual(sorted(d["Perspectiva"]), ["XY", "XZ", "YZ"],
            "y la Perspectiva pinta los tres, que es como los quiso Mike de fábrica")


# --- 3. los interruptores: el general, el de ventana y el de plano ---------

def _los_interruptores(r: comun.Reporte, pagina) -> None:
    huella = "() => lienzo.toDataURL().length"
    caja = pagina.evaluate("() => { const b = lienzo.getBoundingClientRect(); return [b.left, b.top]; }")

    def picar(b):
        pagina.mouse.click(caja[0] + b["x"], caja[1] + b["y"])
        pagina.wait_for_timeout(400)

    # Dónde quedaron los interruptores del título, preguntándoselo al módulo.
    botones = pagina.evaluate("""() => {
      const fuera = [];
      for (const v of Ventanas.ventanas) for (let x = v.ox; x < v.ox + v.w; x += 2) {
        const b = Ventanas.botonEn(x, v.oy + 9);
        if (b && !fuera.some((k) => k.ventana === b.ventana && k.plano === (b.plano || null)))
          fuera.push({ ventana: b.ventana, plano: b.plano || null, que: b.que,
                       x: Math.round(b.x + b.w / 2), y: Math.round(b.y + b.h / 2) });
      }
      return fuera; }""")
    por_plano = {b["plano"]: b for b in botones if b["que"] == "plano"}
    por_ventana = {b["ventana"]: b for b in botones if b["que"] == "ventana"}
    r.igual(sorted(k for k in por_plano), ["XY", "XZ", "YZ"],
            "la Perspectiva enseña un interruptor por plano en su título")
    r.igual(sorted(por_ventana), [0, 2, 3],
            "y las otras tres, uno cada una")

    # El plano XZ de la Perspectiva.
    antes = pagina.evaluate(huella)
    picar(por_plano["XZ"])
    r.igual(pagina.evaluate("() => estado.prefs.rejilla_planos.XZ"), False,
            "apagar el plano XZ de la Perspectiva lo apaga")
    r.cierto(pagina.evaluate(huella) != antes,
             "y la pantalla lo obedece en el momento")
    picar(por_plano["XZ"])
    r.igual(pagina.evaluate("() => estado.prefs.rejilla_planos.XZ"), True,
            "y volver a picarlo lo devuelve")

    # La rejilla de la Frontal.
    antes = pagina.evaluate(huella)
    picar(por_ventana[2])
    r.igual(pagina.evaluate("() => estado.prefs.rejilla_ventanas.Frontal"), False,
            "apagar la rejilla de la Frontal la apaga")
    r.cierto(pagina.evaluate(huella) != antes, "y también se ve en el momento")
    r.igual(pagina.evaluate("() => Ventanas.planosRejilla(Ventanas.la(0))"), ["XY"],
            "sin tocar a la Superior: cada ventana lleva la suya")

    # El interruptor general, que es el que no hacía nada.
    antes = pagina.evaluate(huella)
    pagina.click("#sw-rejilla")
    pagina.wait_for_timeout(400)
    r.igual(pagina.evaluate("() => estado.prefs.rejilla"), False, "el botón REJILLA la apaga")
    r.cierto(pagina.evaluate(huella) != antes,
             "y **borra la rejilla de la pantalla**, que es lo que no hacía hasta la 0.19.0")
    r.igual(pagina.evaluate("() => Ventanas.planosRejilla(Ventanas.la(1))"), [],
            "con el general apagado no queda ninguna prendida")
    pagina.click("#sw-rejilla")
    pagina.wait_for_timeout(400)
    r.igual(pagina.evaluate("() => estado.prefs.rejilla_ventanas.Frontal"), False,
            "y al volver a prenderlo, la Frontal sigue apagada: el general no borra lo de cada una")
    picar(por_ventana[2])       # se deja como estaba


# --- 4. infinita: llega a las cuatro orillas a cualquier zoom --------------

def _infinita(r: comun.Reporte, pagina) -> None:
    """Se mira el lienzo de verdad, píxel por píxel.

    Es la única manera de comprobar «infinita»: preguntarle al módulo cuántas
    líneas calculó sería preguntarle si hizo lo que cree que hizo. Lo que
    importa es si en la orilla de la ventana hay rejilla pintada.
    """
    sonda = """(nombre, escala) => {
      const v = Ventanas.ventanas.find((q) => q.nombre === nombre);
      v.escala = escala;
      Ventanas.centrarEnOrigen();
      invalidarPlano(); pintarYa();
      const c = lienzo.getContext('2d');
      const dpr = lienzo.width / lienzo.clientWidth;
      // El fondo, tomado de una esquina cualquiera del propio lienzo.
      const leer = (x, y, w, h) => c.getImageData(Math.round(x * dpr), Math.round(y * dpr),
                                                  Math.max(1, Math.round(w * dpr)),
                                                  Math.max(1, Math.round(h * dpr))).data;
      const fondo = leer(v.ox + 3, v.oy + v.h - 3, 1, 1);
      const distintos = (x, y, w, h) => {
        const d = leer(x, y, w, h);
        let n = 0;
        for (let i = 0; i < d.length; i += 4)
          if (Math.abs(d[i] - fondo[0]) + Math.abs(d[i+1] - fondo[1]) + Math.abs(d[i+2] - fondo[2]) > 6) n++;
        return n;
      };
      const t = 20, m = 6;      // una tira de 20 px a 6 px de cada orilla
      return {
        izquierda: distintos(v.ox + m, v.oy + v.h / 2 - t / 2, 2, t),
        derecha:   distintos(v.ox + v.w - m - 2, v.oy + v.h / 2 - t / 2, 2, t),
        arriba:    distintos(v.ox + v.w / 2 - t / 2, v.oy + TITULO_PRUEBA + m, t, 2),
        abajo:     distintos(v.ox + v.w / 2 - t / 2, v.oy + v.h - m - 2, t, 2),
      };
    }"""
    pagina.evaluate(f"() => {{ window.TITULO_PRUEBA = Ventanas.TITULO; window.__sonda = {sonda}; }}")

    # Tres zooms muy distintos. Al alejarse, el cuadro fijo de ±500 mm de la
    # 0.19.0 se encogía a un pañuelo en el centro y las orillas quedaban vacías.
    for nombre in ("Frontal", "Lateral", "Superior"):
        for escala, como in ((0.02, "alejadísimo"), (1.0, "a tamaño natural"), (40.0, "encimadísimo")):
            d = pagina.evaluate(f"() => window.__sonda('{nombre}', {escala})")
            vacias = [k for k, v in d.items() if v == 0]
            r.cierto(not vacias,
                     f"{como}, la rejilla de la {nombre} llega a las cuatro orillas",
                     f"sin nada en: {', '.join(vacias) or '—'} · {d}")

    # Y que alejarse no cueste caro: el paso crece con el zoom y el número de
    # líneas se queda quieto. Sin eso, un plano de obra arrodilla la app.
    ms = pagina.evaluate("""() => {
      for (const v of Ventanas.ventanas) v.escala = 0.004;
      Ventanas.centrarEnOrigen();
      const t0 = performance.now();
      for (let i = 0; i < 5; i++) { invalidarPlano(); pintarYa(); }
      return (performance.now() - t0) / 5; }""")
    r.cierto(ms < 350, f"y alejarse no la arrodilla: {ms:.0f} ms por cuadro con las cuatro al 0.4 %",
             f"{ms:.0f} ms")


# --- 5. la cara que se podía picar --------------------------------------

def _se_puede_picar_una_cara(r: comun.Reporte, pagina) -> None:
    """Lo que Mike reportó como «CRECER no sirvió».

    No era CRECER: la pieza nacía fuera de la Perspectiva, así que no había
    cara que picar y el comando contestaba, con razón, «primero señala una
    cara». Se mide de punta a punta, con el ratón de verdad.
    """
    pagina.evaluate("""async () => {
      const id = await crearEntidad({ tipo: 'polilinea', cerrada: true, plano: 'XY',
        puntos: [[0,0,0],[600,0,0],[600,400,0],[0,400,0]] }, 'base de la prueba');
      estado.sel = [id];
      await Comandos.correr('EXTRUIR 120');
      await new Promise((k) => setTimeout(k, 1200));
      estado.sel = [];
      encuadrar();
      await new Promise((k) => setTimeout(k, 500));
    }""")
    ids = pagina.evaluate("async () => (await fetch('/api/cuerpo/lista').then((x) => x.json())).ids")
    if not r.cierto(len(ids) == 1, "la pieza se levantó", str(ids)):
        return
    pieza = ids[0]

    # Extents encuadra **las cuatro**: cada una tiene que ver la pieza dentro.
    fuera = pagina.evaluate("""() => {
      const malas = [];
      for (const v of Ventanas.ventanas) {
        const g = estado.vista; estado.vista = v;
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const X of [0, 600]) for (const Y of [0, 400]) for (const Z of [0, 120]) {
          const q = window.aPX(X, Y, Z);
          x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]);
          y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]);
        }
        estado.vista = g;
        const dentro = x1 > v.ox && x0 < v.ox + v.w && y1 > v.oy && y0 < v.oy + v.h;
        if (!dentro) malas.push(v.nombre);
      }
      return malas; }""")
    r.igual(fuera, [], "y Extents la deja a la vista en las cuatro ventanas")

    # El punto se busca **bien adentro** de una cara, no en la primera que
    # aparezca: el ratón del navegador cae en píxeles enteros y un punto de la
    # orilla se va medio píxel al vecino, que es aire. Y se pica en enteros,
    # que es lo único que el navegador sabe mandar.
    p = pagina.evaluate("""() => {
      const v = Ventanas.la(1);
      const g = estado.vista; estado.vista = v;
      const caja = lienzo.getBoundingClientRect();
      const mismo = (x, y, cara) => { const c = Cuerpos.caraEn(x, y); return c && c.cara === cara; };
      let hit = null;
      for (let y = v.oy + 40; y < v.oy + v.h - 10 && !hit; y += 4)
        for (let x = v.ox + 10; x < v.ox + v.w - 10 && !hit; x += 4) {
          const cc = Cuerpos.caraEn(x, y);
          if (!cc) continue;
          // Bien adentro: sus cuatro vecinos a 4 px son de la misma cara.
          if (![[4,0],[-4,0],[0,4],[0,-4]].every(([a, b]) => mismo(x + a, y + b, cc.cara))) continue;
          // Y que el punto sea del lienzo y no de un panel encima: un clic que
          // se come otro elemento no prueba nada.
          const el = document.elementFromPoint(Math.round(caja.left + x), Math.round(caja.top + y));
          if (el && el.id === 'lienzo') hit = { x, y, cara: cc.cara };
        }
      estado.vista = g;
      return hit ? { ...hit, px: Math.round(caja.left + hit.x),
                            py: Math.round(caja.top + hit.y) } : null; }""")
    if not r.cierto(p is not None,
                    "se puede picar una cara de la pieza en la Perspectiva"):
        return

    pagina.mouse.click(p["px"], p["py"])
    pagina.wait_for_timeout(500)
    senalada = pagina.evaluate("() => TresD.senalada()")
    r.cierto(bool(senalada), "y el clic la señala de verdad", str(senalada))
    if not senalada:
        return

    antes = pagina.evaluate(
        f"async () => (await fetch('/api/cuerpo/{pieza}/malla').then((x) => x.json())).volumen_mm3")
    pagina.evaluate("async () => { await Comandos.correr('CRECER 50'); }")
    pagina.wait_for_timeout(2500)
    m = pagina.evaluate(f"async () => await fetch('/api/cuerpo/{pieza}/malla').then((x) => x.json())")
    r.casi(m["volumen_mm3"] - antes, 600 * 400 * 50,
           "y entonces CRECER sí crece: el perfil de la cara por la medida, 600 × 400 × 50", 1.0)
    r.casi(m["caja"][2], 170.0,
           "la pieza mide 50 mm más de alto: la cara se quedó, el material nació encima", 0.5)
