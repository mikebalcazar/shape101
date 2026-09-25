"""Traer un dibujo 2D de draw101  ·  0.21.0

Mike, 24-sep: *«necesito poder importar dibujo 2D desde draw. El formato 101d»*.

El 2D se dibuja en draw101, que para eso es mucho mejor, y se levanta aquí. Lo
que se comprobó antes de escribir una línea: **el documento de los dos programas
es idéntico campo por campo**. Salieron del mismo código y nunca se separaron en
eso, así que un dibujo de draw101 no necesita traducción — necesitaba que
alguien lo dejara entrar. Lo que fallaba era la puerta: `/api/abrir` repartía
por extensión, `.t101d` no estaba en la lista, y el archivo acababa en el lector
de DXF contestando «is not a DXF file».

Y de paso apareció un defecto ya publicado, de la misma familia: la interfaz
seguía diciendo `.t101d` mientras el motor guardaba `.101s`, así que **los
archivos del propio shape101 no aparecían en su propio diálogo de Abrir** y
Guardar volvía a pedir la ruta cada vez. Por eso la primera comprobación de aquí
abajo no prueba una función: prueba que el motor y la interfaz digan lo mismo.

Lo que se fija:

1. **Las extensiones no se desincronizan.** Lo que el motor guarda tiene que ser
   lo que la interfaz ofrece abrir y lo que propone al guardar.
2. **El formato de draw101 entra**, y entra por las cuatro puertas que reparten
   por extensión: abrir, importar, referencia externa y comparar.
3. **Abrir un dibujo de draw101 no lo vuelve el archivo de guardado.** El 2D se
   sigue editando en draw101; guardarle encima desde aquí sería quitarle al
   taller su dibujo.
4. **Importar suma, no reemplaza**, y lo que entra es geometría de verdad: se
   selecciona y se levanta con EXTRUIR, que es para lo que se pidió.
5. **Cae en el suelo (XY)**, que fue la decisión de Mike, y **no repinta las
   capas que ya existen**.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import zipfile

from pruebas import comun, navegador

DESCRIPCION = "importar un dibujo 2D de draw101 y levantarlo"

# El contorno que viaja en el archivo de prueba, en milímetros.
ANCHO, FONDO, ALTO = 600.0, 400.0, 60.0


def _como_draw101(ruta: pathlib.Path) -> pathlib.Path:
    """Un `.t101d` escrito **a mano**, igual que lo escribe draw101.

    A propósito no se usa `proyecto.guardar`: eso escribiría un `.101s` y la
    prueba estaría comprobando que shape101 se entiende consigo mismo, que no es
    lo que hace falta saber. Esto es el contrato con el otro programa, escrito
    aquí para que se vea: un ZIP con `meta.json` y `documento.json`.

    Comprobado el 24-sep contra draw101 0.21.0 de verdad: se escribió un dibujo
    con su propio `core.proyecto` y el motor de aquí lo abrió con sus 3
    entidades y sus 2 capas.
    """
    doc = {
        "nombre": "mueble de draw101",
        "cliente": "", "unidad": "mm", "capa_activa": "0",
        "capas": [
            {"nombre": "0", "color": "#FFFFFF", "grosor": 25,
             "tipo_linea": "CONTINUOUS", "visible": True, "bloqueada": False,
             "imprime": True, "descripcion": "Capa cero — no se borra, no se renombra"},
            {"nombre": "MUEBLE", "color": "#C08040", "grosor": 35,
             "tipo_linea": "CONTINUOUS", "visible": True, "bloqueada": False,
             "imprime": True, "descripcion": "capa que aquí no existe"},
        ],
        "bloques": [], "estilos_texto": {}, "estilos_cota": {}, "layouts": [],
        "origen_t101x": "", "xrefs": [], "origen_dxf": "", "origen_dwg": "",
        "factor_unidades": 1.0, "insunits_origen": 4, "unidades": "mm",
        "entidades": [
            {"id": "a1", "tipo": "polilinea", "capa": "MUEBLE", "cerrada": True,
             "puntos": [[0, 0, 0], [ANCHO, 0, 0], [ANCHO, FONDO, 0], [0, FONDO, 0]]},
            {"id": "a2", "tipo": "circulo", "capa": "0",
             "centro": [ANCHO / 2, FONDO / 2], "radio": 40.0},
            {"id": "a3", "tipo": "linea", "capa": "0",
             "p1": [0, FONDO + 100], "p2": [ANCHO, FONDO + 100]},
        ],
    }
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(
            {"formato": 1, "app": "draw101", "guardado": "2026-09-24T18:00:00",
             "unidad": "mm"}, ensure_ascii=False))
        z.writestr("documento.json", json.dumps(doc, ensure_ascii=False))
    return ruta


def correr(r: comun.Reporte) -> None:
    _las_extensiones_cuadran(r)
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: el resto se salta)")
        return

    carpeta = pathlib.Path(tempfile.mkdtemp(prefix="t033-"))
    de_draw = _como_draw101(carpeta / "mueble.t101d")

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.set_viewport_size({"width": 1280, "height": 820})
        pagina.wait_for_timeout(400)
        # Importar va primero, sobre el documento recién arrancado. Abrir va
        # al final a propósito: es el que **reemplaza** lo que hay, así que si
        # fuera antes dejaría a las otras dos midiendo otro documento.
        _importar_suma(r, pagina, de_draw)
        _y_se_puede_levantar(r, pagina)
        _la_puerta_lo_deja_entrar(r, pagina, de_draw)


# --- 1. el motor y la interfaz tienen que decir lo mismo -------------------

def _las_extensiones_cuadran(r: comun.Reporte) -> None:
    """La comprobación que habría cazado el defecto de la 0.20.x.

    No prueba una función: prueba que dos archivos que nadie obliga a estar de
    acuerdo lo estén. Es la misma forma de defecto que el botón REJILLA de la
    0.20.0 —la preferencia decía una cosa y la pantalla otra— y por eso se
    escribe igual: se lee de los dos lados y se comparan.
    """
    import sys
    raiz = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz))
    from core import config

    app_js = (raiz / "ui" / "app.js").read_text(encoding="utf-8")
    propia = config.EXT_PROYECTO.lstrip(".")

    r.cierto(f'const EXT_PROPIA = "{propia}"' in app_js,
             f"la interfaz guarda con la misma extensión que el motor (.{propia})",
             "ui/app.js y core/config.py no dicen lo mismo")
    # El diálogo de Abrir tiene que ofrecer lo que este programa guarda. Sin
    # esto, Mike guardaba una pieza y no podía volver a abrirla.
    r.cierto("EXT_PROPIA, ...EXT_DRAW" in app_js,
             "y el diálogo de Abrir ofrece lo propio **y** lo de draw101")
    for ext in (".101d", ".t101d"):
        r.cierto(ext in config.EXT_DRAW101, f"el motor reconoce {ext} como de draw101")
    r.cierto(config.es_propio("x.101s") and config.es_propio("x.T101D"),
             "y `es_propio` no se casa con las mayúsculas")
    r.cierto(not config.es_propio("x.dxf"),
             "el DXF no cuenta como propio: ése pasa por el lector de planos ajenos")
    r.cierto(config.es_de_draw("x.t101d") and not config.es_de_draw("x.101s"),
             "y se distingue lo de draw101 de lo propio, para no guardarle encima")

    electron = (raiz / "electron" / "main.js").read_text(encoding="utf-8")
    r.cierto(config.EXT_PROYECTO in electron,
             "el doble clic de Windows abre la pieza propia",
             "electron/main.js no lista la extensión del motor")


# --- 2 y 3. la puerta -----------------------------------------------------

def _la_puerta_lo_deja_entrar(r: comun.Reporte, pagina, de_draw: pathlib.Path) -> None:
    abierto = pagina.evaluate("""async (ruta) => {
      const res = await fetch('/api/abrir', { method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ruta}) });
      const j = await res.json();
      return { ok: res.ok, detalle: j.detail || null, entidades: j.entidades,
               nombre: j.nombre, ruta: j.ruta || null };
    }""", str(de_draw))
    if not r.cierto(abierto["ok"], "Abrir acepta un dibujo de draw101",
                    str(abierto["detalle"])[:160]):
        return
    r.igual(abierto["entidades"], 3, "y entran sus tres entidades")
    r.igual(abierto["nombre"], "mueble de draw101", "con el nombre que traía")
    # Lo que protege el dibujo del taller: se abre, pero no se le guarda encima.
    r.cierto(not abierto["ruta"],
             "y **no** se queda como archivo de guardado: el 2D es de draw101",
             f"quedó apuntando a {abierto['ruta']}")


# --- 4 y 5. importar ------------------------------------------------------

def _importar_suma(r: comun.Reporte, pagina, de_draw: pathlib.Path) -> None:
    # Se parte de una pieza propia ya levantada: lo importante de «importar» es
    # que lo que ya estaba siga estando.
    pagina.evaluate("""async () => {
      const id = await crearEntidad({tipo:'polilinea', cerrada:true, plano:'XY',
        puntos:[[900,0,0],[1200,0,0],[1200,200,0],[900,200,0]]}, 'la que ya estaba');
      estado.sel = [id];
      await Comandos.correr('EXTRUIR 80');
      await new Promise((k) => setTimeout(k, 1200));
      estado.sel = [];
    }""")
    antes = pagina.evaluate(
        "async () => (await fetch('/api/estado').then((x) => x.json())).entidades")
    # La capa «0» ya existe aquí y tiene su propio color: importar no puede
    # repintársela. Se le pone una marca para ver si alguien la toca.
    pagina.evaluate("""async () => {
      await fetch('/api/capa/0', { method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ cambios: { descripcion: 'NO ME TOQUES' } }) });
    }""")

    d = pagina.evaluate("""async (ruta) => {
      const res = await fetch('/api/importar', { method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ruta}) });
      const j = await res.json();
      return { ok: res.ok, detalle: j.detail || null, importadas: j.importadas,
               capas_nuevas: j.capas_nuevas, solidos: j.solidos_omitidos,
               archivo: j.archivo, entidades: j.entidades };
    }""", str(de_draw))
    if not r.cierto(d["ok"], "IMPORTAR acepta el dibujo de draw101",
                    str(d["detalle"])[:160]):
        return
    r.igual(d["importadas"], 3, "y trae sus tres entidades")
    r.igual(d["entidades"], antes + 3,
            "sumadas a lo que ya había: importar no reemplaza, que es la diferencia con Abrir")
    r.igual(d["archivo"], "mueble.t101d", "y dice de qué archivo vinieron")

    cuerpos = pagina.evaluate(
        "async () => (await fetch('/api/cuerpo/lista').then((x) => x.json())).ids")
    r.igual(len(cuerpos), 1, "la pieza que ya estaba levantada sigue ahí")

    r.igual(d["capas_nuevas"], ["MUEBLE"],
            "se crea la capa que el dibujo traía y aquí no existía")
    capas = pagina.evaluate(
        "async () => (await fetch('/api/estado').then((x) => x.json())).capas")
    cero = [c for c in capas if c["nombre"] == "0"]
    r.cierto(cero and cero[0]["descripcion"] == "NO ME TOQUES",
             "y la capa «0» que ya existía **no** se repinta con la del otro dibujo",
             str(cero[:1])[:160])

    planos = pagina.evaluate("""async () => {
      await recargarTrazos();
      return [...new Set(estado.trazos.map((t) => t.plano || 'XY'))]; }""")
    r.igual(sorted(planos), ["XY"],
            "todo cae en el suelo (XY), que fue lo que eligió Mike el 24-sep")


def _y_se_puede_levantar(r: comun.Reporte, pagina) -> None:
    """Lo que separa importar de una referencia externa: esto se puede levantar.

    Un xref entra bloqueado —para calcar encima— y lo que no se selecciona no se
    puede extruir. Si esta comprobación se cae, la función no sirve para lo que
    se pidió por más que el dibujo se vea en pantalla.
    """
    s = pagina.evaluate("""async (a) => {
      await recargarTrazos();
      const t = estado.trazos.find((t) => (t.puntos || []).length === 5 &&
          Math.abs(t.puntos[1][0] - t.puntos[0][0]) === a);
      if (!t) return { hay: false };
      estado.sel = [t.id];
      await Comandos.correr('EXTRUIR 60');
      await new Promise((k) => setTimeout(k, 1600));
      const ids = await fetch('/api/cuerpo/lista').then((x) => x.json()).then((x) => x.ids);
      const m = await fetch(`/api/cuerpo/${ids[ids.length - 1]}/malla`).then((x) => x.json());
      return { hay: true, cuerpos: ids.length, volumen: m.volumen_mm3, caja: m.caja };
    }""", ANCHO)
    if not r.cierto(s["hay"], "el contorno importado se puede seleccionar"):
        return
    r.igual(s["cuerpos"], 2, "y levantarlo deja dos piezas: la de antes y la nueva")
    r.casi(s["volumen"], ANCHO * FONDO * ALTO,
           f"con el volumen exacto del contorno que venía de draw101: "
           f"{ANCHO:.0f} × {FONDO:.0f} × {ALTO:.0f}", 1.0)
    r.igual([round(k, 1) for k in s["caja"]], [ANCHO, FONDO, ALTO],
            "y midiendo lo que medía en draw101, sin escalarse por el camino")
