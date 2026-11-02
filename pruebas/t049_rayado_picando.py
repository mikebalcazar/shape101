"""t049 · RAYADO picando dentro: el área sale del arreglo de curvas, con sus islas.

Hasta la fase B2b, RAYADO pedía elegir **un** contorno cerrado: una polilínea
cerrada o un círculo. El LEEME lo decía claro: «no se pica dentro para que
adivine el contorno; detectar islas en un plano medio dibujado falla más de lo
que acierta». Ahora se pica dentro, como en AutoCAD y en Rhino: con todas las
curvas a la vista —abiertas o cerradas, que se cruzan o no— OpenCASCADE parte
una hoja en regiones (core/regiones.region_en), y la del punto es el área.

Se comprueba:

- cuatro líneas sueltas que se cruzan y sobresalen cierran un área; un círculo
  y una spline adentro quedan como islas;
- el borde exterior y el círculo salen exactos (rectas y arcos como bulge) y la
  isla de spline sobre la spline, dentro de la flecha;
- picar dentro de una isla raya la isla; un hueco de 0.02 mm cierra (tolerancia
  del documento) y uno de 1 mm avisa que el área tiene una abertura; picar
  sobre una línea avisa;
- un rectángulo cortado por una spline abierta: cada lado es un área distinta;
- el rayado resultante se pinta y sale al DXF como HATCH, con su isla;
- en el programa: RAYADO, clic dentro, y queda un rayado con su isla; Ctrl+Z lo
  quita.
"""

from __future__ import annotations

import math

import ezdxf

from core import dibujo
from core import entidades as E
from core import regiones as R
from core.documento import Documento
from export import dxf as export_dxf
from pruebas import comun, navegador

DESCRIPCION = "RAYADO picando dentro: área por el arreglo de curvas, con islas"

VENTANA = [-300, -300, 1800, 900]
ISLA_SPLINE = [[350, 100], [500, 50], [550, 250], [400, 300]]


def _lineas(doc, hueco=0.0):
    """Cuatro líneas sueltas que se cruzan (y sobresalen) en un rectángulo de
    600 × 400. Con `hueco`, la de la izquierda no llega a la de abajo."""
    with doc.transaccion("Dibujar"):
        doc.agregar(E.Linea(p1=[-50, 0], p2=[650, 0]))
        doc.agregar(E.Linea(p1=[600, -50], p2=[600, 450]))
        doc.agregar(E.Linea(p1=[650, 400], p2=[-50, 400]))
        doc.agregar(E.Linea(p1=[0, 450], p2=[0, hueco if hueco else -50]))


def _area_polilinea(ruta) -> float:
    return R.area_de_contorno([{"tipo": "polilinea", "puntos": ruta, "cerrada": True}])


def correr(r: comun.Reporte) -> None:
    _con_islas(r)
    _bordes(r)
    _spline_que_corta(r)
    _navegador(r)


def _con_islas(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    _lineas(doc)
    with doc.transaccion("Dibujar"):
        doc.agregar(E.Circulo(centro=[200, 200], radio=50))
        sp = doc.agregar(E.Spline(puntos_control=ISLA_SPLINE, cerrada=True))
    res = R.region_en(doc, [100, 350], VENTANA)
    r.igual(res["contornos"], 3, "cuatro líneas sueltas cierran el área, con el círculo y la spline como islas")
    exterior, *islas = res["rutas"]
    r.casi(_area_polilinea(exterior), 240000, "el borde exterior es el rectángulo de 600 × 400, exacto", 1e-6)
    circ = next(i for i in islas if len(i) == 2)
    r.casi(_area_polilinea(circ), math.pi * 2500, "el círculo sale exacto, como dos medios arcos", 1e-6)
    isla_sp = next(i for i in islas if len(i) > 2)
    c = sp.curva()
    peor = max(math.dist(c.cercano(q[:2])[1], q[:2]) for q in isla_sp)
    r.cierto(peor < 1e-6, "los vértices de la isla de spline están sobre la spline", f"{peor:.2e}")
    a_sp = R.area_de_contorno([sp.a_dict()])
    # La ruta de un HATCH es una polilínea: el polígono inscrito pierde, a lo
    # más, la flecha por el perímetro.
    perimetro = sum(math.dist(isla_sp[i][:2], isla_sp[(i + 1) % len(isla_sp)][:2]) for i in range(len(isla_sp)))
    r.casi(_area_polilinea(isla_sp), a_sp, "y encierra su área (a la flecha de 0.05)", 0.05 * perimetro)
    r.casi(res["area"], 240000 - math.pi * 2500 - _area_polilinea(isla_sp),
           "el área a rayar descuenta las dos islas", 1e-6)

    dentro = R.region_en(doc, [200, 200], VENTANA)
    r.igual(dentro["contornos"], 1, "picar dentro del círculo raya el círculo (la isla), sin más")
    r.casi(dentro["area"], math.pi * 2500, "con el área del círculo", 1e-6)

    # Se pinta y va al DXF como HATCH con su isla.
    with doc.transaccion("Rayar"):
        ray = doc.agregar(E.Rayado(rutas=res["rutas"], patron="ANSI31", solido=False))
    trazos = dibujo.trazos_de(doc, ray)
    r.cierto(any(t.get("puntos") or t.get("lineas") for t in trazos), "el rayado se pinta")
    with comun.carpeta() as tmp:
        export_dxf.escribir(doc, tmp / "t049.dxf")
        leido = ezdxf.readfile(str(tmp / "t049.dxf"))
        hatch = next((h for h in leido.modelspace() if h.dxftype() == "HATCH"), None)
        r.cierto(hatch is not None and len(hatch.paths) == 3,
                 "sale al DXF como HATCH con sus tres caminos (el borde y las dos islas)",
                 str(len(hatch.paths)) if hatch is not None else "sin HATCH")
        r.igual(len(leido.audit().errors), 0, "y el DXF pasa la auditoría de ezdxf")


def _bordes(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    _lineas(doc, hueco=0.02)
    res = R.region_en(doc, [300, 200], VENTANA)
    r.casi(res["area"], 240000, "un hueco de 0.02 mm cierra: es menos que la tolerancia (0.05)", 1e-3)
    doc = Documento.nuevo()
    _lineas(doc, hueco=1.0)
    r.levanta(R.NoSeCombina, R.region_en, "un hueco de 1 mm avisa que el área tiene una abertura",
              doc, [300, 200], VENTANA)
    doc = Documento.nuevo()
    _lineas(doc)
    r.levanta(R.NoSeCombina, R.region_en, "picar justo sobre una línea avisa", doc, [300, 0], VENTANA)
    r.levanta(R.NoSeCombina, R.region_en, "picar donde no hay nada a la vista avisa",
              Documento.nuevo(), [0, 0], VENTANA)


def _spline_que_corta(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    with doc.transaccion("Dibujar"):
        doc.agregar(E.Polilinea(puntos=[[0, 0], [600, 0], [600, 400], [0, 400]], cerrada=True))
        sp = doc.agregar(E.Spline(puntos_ajuste=[[-50, 100], [200, 300], [400, 100], [650, 300]]))
    arriba = R.region_en(doc, [50, 380], VENTANA)
    abajo = R.region_en(doc, [300, 20], VENTANA)
    r.casi(arriba["area"] + abajo["area"], 240000,
           "una spline abierta que cruza el rectángulo lo parte en dos áreas que suman el todo",
           240000 * 2e-4)
    ruta = abajo["rutas"][0]
    c = sp.curva()
    sobre = [q for q in ruta if 0 < q[1] < 400 and 0 < q[0] < 600]
    peor = max((math.dist(c.cercano(q[:2])[1], q[:2]) for q in sobre), default=1)
    r.cierto(sobre and peor < 1e-6, "y el corte va por la spline", f"{peor:.2e}")


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""async () => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            await post('/api/operacion', {accion: 'Dibujar', agregar: [
                {tipo: 'linea', p1: [-50, 0], p2: [650, 0]}, {tipo: 'linea', p1: [600, -50], p2: [600, 450]},
                {tipo: 'linea', p1: [650, 400], p2: [-50, 400]}, {tipo: 'linea', p1: [0, 450], p2: [0, -50]},
                {tipo: 'circulo', centro: [200, 200], radio: 50}]});
            await recargarTrazos(); Seleccion.limpiar(); encuadrarCaja(-200, -200, 800, 600); }""")
        pagina.wait_for_timeout(300)
        antes = len({t["id"] for t in navegador.trazos(base)})
        pagina.evaluate("() => { Comandos.correr('RAYADO SOLID'); }")
        pagina.wait_for_timeout(300)
        # Un punto del área que no esté tapado por la barra flotante: sobre ella
        # el clic aprieta un botón (pasó: GRUPO), no pica el dibujo.
        x, y = pagina.evaluate("""(candidatos) => {
            const caja = document.querySelector('#lienzo').getBoundingClientRect();
            for (const p of candidatos) {
                const [x, y] = aPX(p[0], p[1]);
                const e = document.elementFromPoint(caja.left + x, caja.top + y);
                if (e && e.id === 'lienzo') return [caja.left + x, caja.top + y];
            }
            return null;
        }""", [[450, 300], [100, 100], [500, 50], [50, 350], [550, 350], [100, 300]])
        pagina.mouse.move(x, y)
        pagina.wait_for_timeout(80)
        pagina.mouse.click(x, y)
        pagina.wait_for_timeout(5000)          # el kernel tarda en cargar la primera vez
        tr = navegador.trazos(base)
        ids = {t["id"] for t in tr}
        r.igual(len(ids), antes + 1, "RAYADO, con un clic dentro, crea un rayado")
        rayado = pagina.evaluate("""async (ids) => { for (const i of ids) { const e = await api('/api/entidad/' + i);
                                    if (e.tipo === 'rayado') return e; } return null; }""", sorted(ids))
        r.cierto(rayado is not None and len(rayado["rutas"]) == 2,
                 "con su borde y la isla del círculo", str(rayado and len(rayado["rutas"])))
        pagina.keyboard.press("Control+z")
        pagina.wait_for_timeout(600)
        r.igual(len({t["id"] for t in navegador.trazos(base)}), antes, "Ctrl+Z quita el rayado")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
