"""t013 · Editar un plano de fuera.

Mike, con el primer DWG abierto: *«cuando quiero borrar un elemento, no se
borra»*. **No era el borrado**: era que no se podía **seleccionar**. Una entidad
que el programa no modela no tenía geometría con la que engancharla al ratón,
así que picarla no seleccionaba nada, y sin selección no hay nada que borrar.
Desde que lo ajeno se dibuja, se veía perfectamente… y no respondía al clic.
**Ver algo que no responde es peor que no verlo**: no parece una limitación,
parece que el programa está roto.

Esta prueba abre un plano ajeno de verdad —una spline y una cota nativas de
AutoCAD, fabricadas con ezdxf— en el navegador, y comprueba las dos mitades de
esa lección, que tiran en direcciones contrarias:

1. **Lo ajeno se pica y se borra**, como cualquier cosa del dibujo.
2. **Al osnap se le ignora a propósito.** El punto medio de una raya teselada de
   una cota ajena no es el punto medio de nada, y en un plano que va a la CNC
   ese pelo es una pieza mal cortada. Seleccionar no necesita exactitud; medir
   sí. Es la misma línea que separa `core/dibujo.py` de `core/geometria.py`.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import urllib.request

import ezdxf

from pruebas import comun, navegador

DESCRIPCION = "un plano de fuera: se pica y se borra, pero no se le hace osnap"


def _plano_ajeno(ruta: pathlib.Path) -> None:
    """Un plano «de otro»: una spline y una cota que este programa conserva sin
    modelar, más una línea nuestra al lado como testigo."""
    doc = ezdxf.new("R2013", setup=True)
    ms = doc.modelspace()
    ms.add_line((0, 0), (1000, 0))                       # ésta sí la modelamos
    ms.add_spline([(0, 400), (300, 600), (600, 300), (900, 500)])
    dim = ms.add_linear_dim(base=(0, -200), p1=(0, 0), p2=(1000, 0))
    dim.render()
    doc.saveas(str(ruta))


def _pedir(base: str, ruta: str, datos: dict):
    req = urllib.request.Request(base + ruta, data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return

    carpeta = pathlib.Path(tempfile.mkdtemp(prefix="shape101-ajeno-"))
    plano = carpeta / "de-otro.dxf"
    _plano_ajeno(plano)

    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        _pedir(base, "/api/abrir", {"ruta": str(plano)})
        pagina.reload(wait_until="networkidle")
        pagina.wait_for_timeout(1500)
        navegador.cerrar_inicio(pagina)

        _se_ve(r, pagina, base)
        _se_pica_y_se_borra(r, pagina, base)
        _no_se_le_hace_osnap(r, pagina)

        r.igual(pagina.errores, [],
                "y abrir y editar un plano ajeno no deja un solo error de JavaScript")


def _se_ve(r: comun.Reporte, pagina, base) -> None:
    estado = navegador.estado(base)
    r.cierto(estado["entidades"] >= 3,
             "el plano ajeno abre con sus entidades", f"entraron {estado['entidades']}")

    crudas = pagina.evaluate("""() => {
        const g = (estado.geometria || []);
        return {total: g.length, aprox: g.filter(p => p.aprox).length};
    }""")
    r.cierto(crudas["total"] > 0, "el lienzo recibe geometría para enganchar el ratón")
    r.cierto(crudas["aprox"] > 0,
             "y lo que no modelamos viene marcado como aproximado (`aprox`)",
             f"{crudas['aprox']} de {crudas['total']}")

    # Y se **pinta**: un plano ajeno al que le faltan las cotas parece un plano
    # al que le faltan las cotas, y eso es justo lo que no queremos que parezca.
    trazos = navegador.trazos(base)
    r.cierto(len(trazos) > 3,
             "y se pinta entero, cotas ajenas incluidas", f"{len(trazos)} trazos")


def _se_pica_y_se_borra(r: comun.Reporte, pagina, base) -> None:
    """Lo que se ve, se pica; y lo que se pica, se borra."""
    id_ajeno = pagina.evaluate("""() => {
        const g = (estado.geometria || []).filter(p => p.aprox);
        if (!g.length) return null;
        const pr = g[0];
        const p = pr.tipo === 'seg'
            ? [(pr.a[0] + pr.b[0]) / 2, (pr.a[1] + pr.b[1]) / 2]
            : (pr.c || pr.centro);
        return Seleccion.bajoElCursor(p);
    }""")
    r.cierto(bool(id_ajeno),
             "picar encima de una entidad ajena la selecciona (era el «no se borra»)")

    antes = navegador.estado(base)["entidades"]
    if id_ajeno:
        # Se borra por donde lo borra la interfaz: el endpoint de una entidad.
        req = urllib.request.Request(base + f"/api/entidad/{id_ajeno}", method="DELETE")
        urllib.request.urlopen(req, timeout=15).read()
        despues = navegador.estado(base)["entidades"]
        r.igual(despues, antes - 1, "y entonces sí se borra")


def _no_se_le_hace_osnap(r: comun.Reporte, pagina) -> None:
    """La otra mitad, que tira al revés: a lo ajeno **no** se le engancha."""
    pagina.evaluate("""() => {
        estado.prefs.osnap = true;
        estado.prefs.osnap_apertura = 40;
        estado.prefs.osnap_modos = {extremo: true, medio: true, centro: true,
            cuadrante: true, interseccion: true, cercano: true, nodo: true};
    }""")

    res = pagina.evaluate("""() => {
        const aprox = (estado.geometria || []).filter(p => p.aprox && p.tipo === 'seg');
        const propias = (estado.geometria || []).filter(p => !p.aprox && p.tipo === 'seg');
        if (!aprox.length || !propias.length) return {sinDatos: true};
        const medio = (pr) => [(pr.a[0] + pr.b[0]) / 2, (pr.a[1] + pr.b[1]) / 2];
        const enAjena = Osnap.buscar(medio(aprox[0]), null, null);
        const enPropia = Osnap.buscar(medio(propias[0]), null, null);
        return {
            ajena: enAjena ? enAjena.modo : null,
            propia: enPropia ? enPropia.modo : null,
        };
    }""")

    if r.cierto(not res.get("sinDatos"),
                "el plano trae geometría ajena y propia para comparar"):
        # El control es la mitad que importa: si el osnap no enganchara **nada**,
        # esta prueba pasaría por la razón equivocada.
        r.cierto(res["propia"] is not None,
                 "sobre una línea nuestra sí se engancha (el control)")
        r.igual(res["ajena"], None,
                "y sobre la tesela de una cota ajena NO se engancha, a propósito")
