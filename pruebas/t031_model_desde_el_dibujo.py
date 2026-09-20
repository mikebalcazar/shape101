"""El grupo **model**, alcanzable desde el programa  ·  0.19.0

t030 fijó que el motor sabe revolver, barrer, loftear y crecer desde una cara.
Esta fija lo otro, que sin ello lo de t030 no le sirve a nadie: que se pueda
**llegar** a esas cuatro desde el dibujo, tecleando un comando.

Lo que se comprueba, en este orden:

1. **El plano de cada ventana dicho como plano.** Hasta la 0.18.0 la pieza se
   armaba en el suelo y se rotaba al salir (`rutas._a_mundo`). Con el grupo
   model eso deja de servir: un barrido quiere el perfil en la Frontal y el
   camino en la Superior, y esos dos no se rotan juntos. Ahora cada boceto se
   coloca desde el principio, con `planos.del_dibujo`. Las dos cuentas tienen
   que dar **lo mismo**, y eso se comprueba aquí punto por punto: son dos
   descripciones del mismo hecho escritas en archivos distintos, que es
   exactamente la forma que tienen de separarse sin que nadie se entere.
2. **Quién es el perfil y quién el eje o el camino se reparte solo**, por lo
   que cada entidad dice de sí misma: cerrada o abierta.
3. **Las tres puertas dan el volumen exacto**, contra fórmula y no contra «se
   ve bien».
4. **Un barrido entre ventanas distintas cae donde debe.** Es lo que no se
   podía hacer antes, así que es lo que hay que medir.
5. **Lo que no se puede hacer se niega en español y no rompe nada.** Incluido
   el caso callado: dos secciones en la misma ventana sin separación, que el
   kernel contesta con «BRep_API: command not done».
6. Y los cuatro comandos se pueden teclear.
"""
from __future__ import annotations

import math

from pruebas import comun, navegador

DESCRIPCION = "model desde el dibujo: REVOLVER, BARRER, LOFT y CRECER"


def _rect(x0, y0, x1, y1, plano="XY"):
    return {"tipo": "polilinea", "cerrada": True, "plano": plano,
            "puntos": [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]]}


def correr(r: comun.Reporte) -> None:
    _los_planos(r)
    _el_reparto(r)
    _desde_el_programa(r)


# --- 1. las dos cuentas del mismo plano ------------------------------------

def _los_planos(r: comun.Reporte) -> None:
    from core.solido import planos
    from core.solido import rutas

    # `rutas._a_mundo` lleva un punto del kernel al mundo rotando la pieza al
    # final. `planos.del_dibujo` describe el mismo plano para colocar el boceto
    # desde el principio. Si un día se separan, una pieza sale a un sitio y su
    # hermana a otro, y nadie sabría por qué.
    iguales = True
    for plano in ("XY", "XZ", "YZ"):
        pl = planos.plano_de(planos.del_dibujo(plano))
        for u, v in ((0, 0), (10, 0), (0, 10), (-7.5, 23.25)):
            por_plano = pl.from_local_coords((u, v, 0))
            por_rotacion = rutas._a_mundo(plano, (u, v, 0))
            if max(abs(a - b) for a, b in zip((por_plano.X, por_plano.Y, por_plano.Z),
                                              por_rotacion)) > 1e-9:
                iguales = False
    r.cierto(iguales, "el plano de cada ventana dice lo mismo que la rotación de siempre")

    r.igual(planos.del_dibujo("XY"), None,
            "y la Superior a ras de suelo no dice nada: las piezas de antes no cambian")
    subido = planos.del_dibujo("XY", 80.0)
    r.igual(subido["origen"], [0, 0, 80.0], "una sección subida 80 se va por su normal")
    r.igual(planos.del_dibujo("XZ", 50.0)["origen"], [0, -50.0, 0],
            "y en la Frontal se va hacia quien mira, que es su normal")


# --- 2. el reparto de la selección -----------------------------------------

def _el_reparto(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod

    r.cierto(mod.es_cerrada({"tipo": "circulo", "centro": [0, 0], "radio": 5}),
             "un círculo encierra área")
    r.cierto(mod.es_cerrada(_rect(0, 0, 10, 10)), "una polilínea cerrada, también")
    r.cierto(not mod.es_cerrada({"tipo": "linea", "p1": [0, 0], "p2": [10, 0]}),
             "una línea no")
    r.cierto(not mod.es_cerrada({"tipo": "polilinea", "cerrada": False,
                                 "puntos": [[0, 0, 0], [10, 0, 0], [10, 10, 0]]}),
             "y una polilínea abierta tampoco, aunque a la vista casi se cierre")

    cerradas, abiertas = mod.repartir([
        {"tipo": "linea", "p1": [0, 0], "p2": [0, 60]},
        _rect(10, 0, 30, 60),
    ])
    r.igual(len(cerradas), 1, "de una selección con eje y contorno sale un contorno")
    r.igual(len(abiertas), 1, "y un eje, sin importar en qué orden se señalaron")


# --- 3, 4, 5 y 6: desde el programa ----------------------------------------

def _desde_el_programa(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte de pantalla se salta)")
        return

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        r.cierto(pagina.evaluate(
            "['REVOLVER','BARRER','LOFT','CRECER'].every((c) => Comandos.existe(c))"),
            "REVOLVER, BARRER, LOFT y CRECER ya se pueden teclear")
        r.cierto(pagina.evaluate(
            "['TORNEAR','SWEEP','PIEL','EXTRUDEFACE'].every((c) => Comandos.existe(c))"),
            "y sus alias, para quien viene de otro CAD")

        # Que se puedan teclear no basta: Mike trabaja con la barra y con la
        # rueda. Un comando al que sólo se llega tecleando su nombre es un
        # comando que no existe para quien no sabe que existe.
        en_la_barra = pagina.evaluate("""() => ['REVOLVER','BARRER','LOFT','CRECER']
            .filter((c) => !document.querySelector(`.bloque[data-et="3D"] button[data-cmd="${c}"]`))""")
        r.igual(en_la_barra, [], "los cuatro tienen su botón en el bloque 3D de la barra")
        en_la_rueda = pagina.evaluate("""() => {
            const cmds = [];
            const hojas = (ramas) => ramas.forEach((g) => {
                if (g.cmd) cmds.push(g.cmd);
                if (g.hijos) hojas(g.hijos);
            });
            hojas(Radial.RUEDA_3D);
            return ['REVOLVER','BARRER','LOFT','CRECER'].filter((c) => !cmds.includes(c));
        }""")
        r.igual(en_la_rueda, [], "y su gajo en la rueda del 3D (Shift + clic derecho)")
        r.cierto(pagina.evaluate(
            "() => Radial.RUEDA_3D[0].cmd === 'EXTRUIR'"),
            "sin moverle el ángulo a Extruir, que la mano ya tiene aprendido")

        pagina.evaluate("() => { estado.prefs.osnap = false; }")

        # --- revolver: un tubo de pared 5, radio interior 30, alto 80 -------
        tubo = pagina.evaluate("""async () => {
            const perfil = await crearEntidad({
                tipo: 'polilinea', cerrada: true, plano: 'XY',
                puntos: [[30,0,0],[35,0,0],[35,80,0],[30,80,0]],
            }, 'perfil del tubo');
            const eje = await crearEntidad({
                tipo: 'linea', plano: 'XY', p1: [0,0], p2: [0,80],
            }, 'eje del tubo');
            const res = await fetch('/api/cuerpo/revolver', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: [eje, perfil], grados: 360 }),
            });
            const j = await res.json();
            return { ok: res.ok, j };
        }""")
        esperado = math.pi * (35 ** 2 - 30 ** 2) * 80
        if r.cierto(tubo["ok"], "REVOLVER levanta el tubo", str(tubo["j"])[:200]):
            r.casi(tubo["j"]["volumen_mm3"], esperado,
                   f"y su volumen es el de la fórmula: {esperado:,.0f} mm³", 1.0)
            # El eje se trazó en el papel de la Superior, así que el tubo queda
            # acostado: 80 a lo largo del eje y 70 de diámetro por los otros dos.
            # Es lo correcto y conviene dejarlo fijado, porque es justo lo que
            # sorprende la primera vez que se tornea algo aquí.
            r.igual(sorted(round(k, 1) for k in tubo["j"]["caja"]), [70.0, 70.0, 80.0],
                    "y mide 80 a lo largo del eje por 70 de diámetro")

        # --- barrer: perfil en la Frontal, camino en la Superior ------------
        # Esto es lo que no se podía hacer antes de que cada boceto tuviera su
        # plano: los dos bocetos viven en ventanas distintas.
        barrido = pagina.evaluate("""async () => {
            const perfil = await crearEntidad({
                tipo: 'polilinea', cerrada: true, plano: 'XZ',
                puntos: [[-5,-5,0],[5,-5,0],[5,5,0],[-5,5,0]],
            }, 'perfil del barrido');
            const camino = await crearEntidad({
                tipo: 'polilinea', cerrada: false, plano: 'XY',
                puntos: [[0,0,0],[0,100,0]],
            }, 'camino del barrido');
            const res = await fetch('/api/cuerpo/barrer', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: [perfil, camino] }),
            });
            const j = await res.json();
            return { ok: res.ok, j };
        }""")
        if r.cierto(barrido["ok"], "BARRER lleva el perfil por el camino", str(barrido["j"])[:200]):
            r.casi(barrido["j"]["volumen_mm3"], 10000.0,
                   "10 × 10 por 100 de camino = 10 000 mm³ exactos", 0.5)
            r.igual([round(k, 1) for k in barrido["j"]["caja"]], [10.0, 100.0, 10.0],
                    "y la pieza cae a caballo de las dos ventanas: 10 de ancho, "
                    "100 de fondo y 10 de alto")

        # --- loft: dos cuadrados de la misma ventana, separados 80 ----------
        piel = pagina.evaluate("""async () => {
            const a = await crearEntidad({
                tipo: 'polilinea', cerrada: true, plano: 'XY',
                puntos: [[0,0,0],[40,0,0],[40,40,0],[0,40,0]],
            }, 'sección de abajo');
            const b = await crearEntidad({
                tipo: 'polilinea', cerrada: true, plano: 'XY',
                puntos: [[10,10,0],[30,10,0],[30,30,0],[10,30,0]],
            }, 'sección de arriba');
            const res = await fetch('/api/cuerpo/loft', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: [a, b], separacion: 80 }),
            });
            const j = await res.json();
            const sin = await fetch('/api/cuerpo/loft', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ids: [a, b], separacion: 0 }),
            });
            return { ok: res.ok, j, sinSeparacion: sin.status, aviso: (await sin.json()).detail };
        }""")
        # Tronco de pirámide: h/3 · (A1 + A2 + √(A1·A2))
        tronco = 80.0 / 3.0 * (1600 + 400 + math.sqrt(1600 * 400))
        if r.cierto(piel["ok"], "LOFT pasa la piel por las dos secciones", str(piel["j"])[:200]):
            r.casi(piel["j"]["volumen_mm3"], tronco,
                   f"y da el tronco de pirámide de la fórmula: {tronco:,.0f} mm³", 1.0)
        r.igual(piel["sinSeparacion"], 400,
                "dos secciones en la misma ventana sin separación se niegan")
        r.cierto("separación" in (piel["aviso"] or "") or "separac" in (piel["aviso"] or ""),
                 "y el aviso dice qué hacer, no «BRep_API: command not done»",
                 str(piel["aviso"])[:160])

        # --- lo que se niega ------------------------------------------------
        negados = pagina.evaluate("""async () => {
            const cerrado = await crearEntidad({
                tipo: 'polilinea', cerrada: true, plano: 'XY',
                puntos: [[200,0,0],[240,0,0],[240,40,0],[200,40,0]],
            }, 'contorno suelto');
            const suelta = await crearEntidad({
                tipo: 'linea', plano: 'XY', p1: [300,0], p2: [340,0],
            }, 'línea suelta');
            const pide = async (ruta, cuerpo) => {
                const res = await fetch(`/api/cuerpo/${ruta}`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(cuerpo),
                });
                return { status: res.status, detail: (await res.json()).detail || '' };
            };
            return {
                revolverSinEje: await pide('revolver', { ids: [cerrado], grados: 360 }),
                barrerSinCamino: await pide('barrer', { ids: [cerrado] }),
                loftConLineas: await pide('loft', { ids: [cerrado, suelta], separacion: 50 }),
                revolverMuchosGrados: await pide('revolver', { ids: [cerrado, suelta], grados: 400 }),
            };
        }""")
        for clave, que in (("revolverSinEje", "REVOLVER sin línea de eje"),
                           ("barrerSinCamino", "BARRER sin camino"),
                           ("loftConLineas", "LOFT con una línea suelta entre las secciones"),
                           ("revolverMuchosGrados", "REVOLVER de 400 grados")):
            caso = negados[clave]
            r.igual(caso["status"], 400, f"{que} se niega")
            r.cierto(caso["detail"] and not any(
                mal in caso["detail"] for mal in ("BRep", "Standard_", "Traceback", "Exception")),
                f"y lo dice en español: «{caso['detail'][:70]}»")

        # Que negarse no deje basura: las piezas buenas siguen ahí y sólo ésas.
        cuantas = pagina.evaluate(
            "async () => (await fetch('/api/cuerpo/lista').then((x) => x.json())).ids.length")
        r.igual(cuantas, 3, "y de todo eso quedaron tres piezas: las tres que sí se podían")

        # --- crecer: material nuevo con el perfil de una cara ---------------
        crecido = pagina.evaluate("""async () => {
            const ids = (await fetch('/api/cuerpo/lista').then((x) => x.json())).ids;
            const id = ids[ids.length - 1];               // el loft
            const antes = await fetch(`/api/cuerpo/${id}/malla`).then((x) => x.json());
            const refs = await fetch(`/api/cuerpo/${id}/referencias`).then((x) => x.json());
            const arriba = (refs.caras || []).find((c) => c === 'arriba') || refs.caras[0];
            const res = await fetch(`/api/cuerpo/${id}/crecer-cara`, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ cara: arriba, mm: 25, unir: true }),
            });
            const j = await res.json();
            return { ok: res.ok, cara: arriba, antes: antes.volumen_mm3,
                     despues: j.volumen_mm3, alto: j.caja ? j.caja[2] : null, detalle: j.detail };
        }""")
        if r.cierto(crecido["ok"], "CRECER levanta material desde una cara", str(crecido["detalle"])[:160]):
            r.casi(crecido["despues"] - crecido["antes"], 20 * 20 * 25,
                   "y lo que creció es el perfil de la cara por la medida: 20 × 20 × 25", 1.0)
            r.casi(crecido["alto"], 105.0,
                   "la pieza mide 25 mm más de alto: la cara se quedó, el material nació encima", 0.5)
