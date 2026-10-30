"""t045 · La tolerancia del documento: una sola distancia decide si dos cosas se tocan.

Rhino tiene una «tolerancia absoluta» por documento y todo la usa. shape101
tenía una por módulo, y el mismo contorno de un plano ajeno —cuatro líneas con
huecos de dos centésimas— **se unía** con UNIR (0.05) pero **no cerraba** al
extruirlo (OpenCASCADE cose a unas micras). Ahora las dos operaciones, y
recortar y extender, usan la del documento (core/tolerancia.py).

Lo que se comprueba:

- la tolerancia vive en el documento: 0.05 mm por omisión, se guarda en el
  `.101s`, un archivo viejo abre con 0.05, y no acepta valores absurdos;
- en un dibujo en centímetros se convierte: 0.05 mm son 0.005 cm;
- **el contorno con huecos de 0.02 mm se extruye** (antes: «no forma ningún
  contorno cerrado») y uno con huecos de medio milímetro sigue sin cerrar:
  la tolerancia cose, no tapa errores de dibujo;
- con la tolerancia en 0.01 mm, el mismo contorno ya no cierra: el número
  manda de verdad, no es decorativo;
- UNIR por la API usa la del documento;
- RECORTAR no deja un pedacito de centésimas cuando un cruce cae pegado a la
  punta de la línea.
"""

from __future__ import annotations

import json
import math
import urllib.request

from core import entidades as E
from core import proyecto
from core import tolerancia
from core.documento import Documento
from core.solido import boceto, rutas
from pruebas import comun, navegador

DESCRIPCION = "tolerancia del documento: unir, coser un sólido y recortar con la misma distancia"


def _con_huecos(hueco: float) -> list:
    """Un rectángulo de 600 × 400 en cuatro líneas sueltas, con `hueco` mm
    entre cada una y la siguiente."""
    return [E.Linea(p1=[0, 0], p2=[600, 0]),
            E.Linea(p1=[600 + hueco, 0], p2=[600, 400]),
            E.Linea(p1=[600, 400 + hueco], p2=[0, 400]),
            E.Linea(p1=[0, 400], p2=[0, hueco])]


def correr(r: comun.Reporte) -> None:
    _el_documento(r)
    _soldar(r)
    _solido(r)
    _navegador(r)


def _el_documento(r: comun.Reporte) -> None:
    doc = Documento.nuevo()
    r.igual(doc.tolerancia_mm, 0.05, "un dibujo nuevo tiene 0.05 mm, la que UNIR ya usaba")
    r.casi(tolerancia.de(doc), 0.05, "en un dibujo en mm, la tolerancia en unidades es 0.05")
    doc.unidades = "cm"
    r.casi(tolerancia.de(doc), 0.005, "en uno en cm, 0.05 mm son 0.005 cm", 1e-12)
    doc.unidades = "mm"

    doc.tolerancia_mm = 0.01
    with comun.carpeta() as tmp:
        ruta = proyecto.guardar(doc, tmp / "t045.101s")
        r.igual(proyecto.abrir(ruta).tolerancia_mm, 0.01, "se guarda en el .101s y vuelve igual")
    viejo = doc.a_dict()
    viejo.pop("tolerancia_mm")
    r.igual(Documento.de_dict(viejo).tolerancia_mm, 0.05, "un archivo viejo (sin el dato) abre con 0.05")
    viejo["tolerancia_mm"] = "basura"
    r.igual(Documento.de_dict(viejo).tolerancia_mm, 0.05, "un dato roto no rompe la apertura: vale 0.05")
    for malo in (0, -1, 5, float("nan")):
        r.levanta(ValueError, tolerancia.valida_mm, f"no acepta {malo} mm", malo)


def _soldar(r: comun.Reporte) -> None:
    pts = [[0, 0], [0.03, 0.03], [0.2, 0], [10, 10], [10.049, 10]]
    reps = tolerancia.soldar(pts, 0.05)
    r.cierto(reps[1] is reps[0], "dos puntos a 0.042 se sueldan en uno")
    r.cierto(reps[2] is not reps[0], "uno a 0.2 se queda aparte")
    r.cierto(reps[4] is reps[3], "y otro par a 0.049 también se suelda")
    r.cierto(all(math.dist(p, q) <= 0.05 for p, q in zip(pts, reps)),
             "ningún punto se mueve más que la tolerancia")


def _solido(r: comun.Reporte) -> None:
    from core.solido import cuerpo as mod_cuerpo

    # El boceto solo: con la tolerancia que se le dé.
    dicts = [e.a_dict() for e in _con_huecos(0.02)]
    try:
        cara = boceto.cara_de(dicts, 0.05)
        r.casi(cara.area, 600 * 400, "con huecos de 0.02 mm el contorno cierra y mide 600 × 400", 1e-6)
    except ValueError as exc:
        r.cierto(False, "con huecos de 0.02 mm el contorno cierra", str(exc))
    r.levanta(ValueError, boceto.cara_de, "con tolerancia 0.01 mm, el mismo contorno no cierra",
              dicts, 0.01)
    r.levanta(ValueError, boceto.cara_de, "y con huecos de medio milímetro tampoco: no se tapan errores",
              [e.a_dict() for e in _con_huecos(0.5)], 0.05)

    # De punta a punta: dibujado en el documento y extruido por la ruta del 3D.
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    previo = tolerancia._doc_actual
    tolerancia.enchufar(lambda: doc)
    mod_cuerpo.olvidar()
    with doc.transaccion("Dibujar"):
        ids = [doc.agregar(e).id for e in _con_huecos(0.02)]
    try:
        malla = rutas.extruir(rutas.Extruir(ids=ids, mm=18))
        r.casi(malla["volumen_mm3"], 600 * 400 * 18, "y EXTRUIR lo vuelve un sólido de 600 × 400 × 18", 1.0)
        cuerpo = doc.entidades[malla["id"]]
        doc.tolerancia_mm = 0.01
        r.levanta(Exception, mod_cuerpo.malla,
                  "si se baja la tolerancia a 0.01, la misma pieza se regenera y ya no cierra (no sale de caché)",
                  cuerpo)
    except Exception as exc:      # noqa: BLE001 — el mensaje es el diagnóstico
        r.cierto(False, "EXTRUIR el contorno con huecos de 0.02 mm", repr(exc))
    finally:
        doc.tolerancia_mm = 0.05
        tolerancia.enchufar(previo)
        mod_cuerpo.olvidar()


def _api(base: str, ruta: str, cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(base + ruta, data=datos, method="POST" if datos else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as f:
        return json.loads(f.read().decode("utf-8"))


def _ids(base) -> list[str]:
    return sorted({t["id"] for t in navegador.trazos(base)}, key=lambda s: int(s[1:]))


def _navegador(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la parte del navegador se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        pagina.evaluate("""() => {
            estado.prefs.osnap = false; estado.prefs.ortho = false;
            estado.prefs.snap_rejilla = false; estado.prefs.dinamica = false;
            encuadrarCaja(-100, -300, 1100, 300);
        }""")
        pagina.wait_for_timeout(200)

        # El comando TOLERANCIA cambia la del documento y el resumen la trae.
        # (El espacio es Enter en la línea de comando: el valor se teclea aparte.)
        navegador.comando(pagina, "TOLERANCIA")
        navegador.comando(pagina, "0.01")
        pagina.wait_for_timeout(300)
        r.casi(pagina.evaluate("() => estado.resumen.tolerancia_mm"), 0.01,
               "el comando TOLERANCIA, tecleando 0.01, la cambia y el navegador la ve")

        # UNIR por la API, con la del documento: 0.02 de hueco ya no se une.
        pagina.evaluate("""async () => {
            await post('/api/operacion', {accion: 'Dibujar', agregar: [
                {tipo: 'linea', p1: [0, 200], p2: [100, 200]},
                {tipo: 'linea', p1: [100.02, 200], p2: [200, 200]}]});
            await recargarTrazos(); }""")
        pagina.wait_for_timeout(300)
        res = _api(base, "/api/unir", {"ids": _ids(base)})
        r.igual(len(res.get("creadas", [])), 0, "con 0.01 mm, UNIR no junta dos líneas a 0.02")
        navegador.comando(pagina, "TOLERANCIA")
        navegador.comando(pagina, "0.05")
        pagina.wait_for_timeout(300)
        res = _api(base, "/api/unir", {"ids": _ids(base)})
        r.igual(len(res.get("creadas", [])), 1, "con 0.05 mm, las mismas sí se unen")
        pagina.evaluate("(ids) => post('/api/operacion', {accion: 'limpiar', borrar: ids}).then(recargarTrazos)",
                        _ids(base))
        pagina.wait_for_timeout(300)

        # RECORTAR: la vertical cruza la horizontal a 0.02 de su punta derecha.
        pagina.evaluate("""async () => {
            await post('/api/operacion', {accion: 'Dibujar', agregar: [
                {tipo: 'linea', p1: [0, 0], p2: [1000, 0]},
                {tipo: 'linea', p1: [500, -200], p2: [500, 200]},
                {tipo: 'linea', p1: [999.98, -200], p2: [999.98, 200]}]});
            await recargarTrazos(); Seleccion.limpiar(); }""")
        pagina.wait_for_timeout(300)
        antes = _ids(base)
        horizontal = antes[0]
        navegador.comando(pagina, "RECORTAR")
        x, y = pagina.evaluate("""(p) => {
            const [x, y] = aPX(p[0], p[1]);
            const caja = document.querySelector('#lienzo').getBoundingClientRect();
            return [caja.left + x, caja.top + y];
        }""", [800, 0])
        pagina.mouse.move(x, y)
        pagina.wait_for_timeout(80)
        pagina.mouse.click(x, y)
        pagina.wait_for_timeout(500)
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(300)
        despues = _ids(base)
        with urllib.request.urlopen(base + f"/api/entidad/{horizontal}", timeout=5) as f:
            h = json.loads(f.read().decode("utf-8"))
        r.igual(len(despues), len(antes),
                "RECORTAR no deja un pedacito de 0.02 suelto (no aparece una entidad nueva)")
        r.punto(h["p2"][:2], [500, 0],
                "la línea se recorta hasta el cruce de x=500: el de 999.98 es su propia punta")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
