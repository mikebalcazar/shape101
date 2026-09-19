"""El mandadero · recado 34: la 0.13.0.

Tres cosas que Mike pidió y una deuda que ya no se paga en otro sitio.

1. **Tiradores en las piezas.** Mike, el 18-sep: «ve pensando en ya agregar los
   modificadores de los endpoints o vértices. Y las aristas deben tener también
   el handle en el midpoint para poder arrastrarlo». El módulo
   (`ui/tiradores.js`) y la prueba (`pruebas/t025_tiradores.py`) ya están en la
   rama `claude/tiradores-0.13.0`; aquí se funde, se enchufan las dos funciones
   del motor y se engancha todo al lienzo.

2. **Al abrir un archivo con piezas, las piezas se ven.** Hasta la 0.12.1 había
   que teclear `3D`: nadie le preguntaba al motor qué piezas había al cargar un
   dibujo. Un archivo guardado con piezas se veía vacío de piezas, que es la
   clase de cosa que hace dudar de si se guardó bien.

3. **El instalador es de shape101.** Icono propio —una pieza en isometría, que
   es lo que Mike eligió el 16-sep— y sus pantallas. Hasta ahora llevaba el
   icono de draw101. Las imágenes se dibujan aquí con `build/imagenes.py` y se
   versionan: el armado corre en Windows y no tiene por qué saber dibujar.

4. **Las releases viejas se podan solas.** Mike, el 18-sep: «quedémonos sólo
   con las 3 últimas». Cada instalador pesa 340 MB y había quince. Se hace en
   el flujo, después de comprobar la release nueva, y **nunca** toca las tres
   más recientes ni `shape101-ultima`: de la más reciente sale el Python
   empotrado del siguiente armado, y ésa es la regla que no se rompe.

De paso, dos arreglos que salieron al pasar por ahí:

- Los grips del medio de una línea seguían proyectándose a mano en planta. Es
  exactamente el error que costó la 0.11.0 y la 0.12.0, vivo en un rincón.
- `Cuerpos.refrescar()` se devolvía sin hacer nada si ya había una petición en
  vuelo. Abrir un archivo justo mientras contestaba la anterior perdía la buena.

Medido antes de disparar, en una máquina con el kernel puesto: **512
comprobaciones en 25 pruebas, todas verdes**, con la prueba nueva corriendo el
navegador de verdad y regenerando sólidos con OpenCascade.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA_NUEVA = "claude/tiradores-0.13.0"
VERSION_VIEJA = "0.12.1"
VERSION_NUEVA = "0.13.0"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    v = os.environ.get("TOKEN_SHAPE101")
    return t.replace(v, "***") if v else t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


def parchar(ruta: pathlib.Path, cambios: list, donde: str) -> None:
    """Cambia un archivo, un trozo a la vez, y **exige que cada trozo aparezca
    una sola vez**. Un reemplazo que no pega, o que pega dos veces, para el
    recado aquí en vez de dejar un archivo medio parchado que nadie entienda."""
    t = ruta.read_text(encoding="utf-8")
    for i, (viejo, nuevo) in enumerate(cambios):
        n = t.count(viejo)
        if n != 1:
            raise RuntimeError(f"{donde} #{i}: «{viejo[:70]}…» aparece {n} veces, esperaba 1")
        t = t.replace(viejo, nuevo)
    ruta.write_text(t, encoding="utf-8")
    anotar(f"{donde}: {len(cambios)} cambio(s)")


# ── core/solido/cuerpo.py · de qué se agarra una pieza y cómo se corre ───────

CUERPO_ANCLA = '''    raise ValueError("este cuerpo no tiene boceto que mover")
'''

CUERPO_NUEVO = '''    raise ValueError("este cuerpo no tiene boceto que mover")


def _puntos_de(e: dict) -> list:
    """Los puntos de control de una entidad del boceto: (indice, x, y).

    Son exactamente los que `mover_punto` sabe mover. Si aquí sale un punto que
    allá no se puede mover, la pantalla enseñaría un tirador que no jala, y eso
    es peor que no enseñarlo. La prueba t025 lo comprueba uno por uno.
    """
    t = e.get("tipo")
    if t == "polilinea":
        return [(i, float(p[0]), float(p[1])) for i, p in enumerate(e.get("puntos") or [])]
    if t == "linea":
        a, b = e.get("p1"), e.get("p2")
        return [(0, float(a[0]), float(a[1])), (1, float(b[0]), float(b[1]))]
    if t in ("circulo", "arco"):
        c = e.get("centro")
        return [(0, float(c[0]), float(c[1]))]
    return []


def _segmentos_de(e: dict) -> list:
    """Los tramos rectos: (a, b, x_medio, y_medio).

    Los tramos con bulge —los que son un arco— se quedan fuera a propósito:
    arrastrar el medio de un arco tendría que cambiar su curvatura, y eso es
    otra operación. Enseñar ahí un tirador que se comporta como si fuera recto
    sería mentir.
    """
    t = e.get("tipo")
    if t == "linea":
        a, b = e.get("p1"), e.get("p2")
        return [(0, 1, (float(a[0]) + float(b[0])) / 2, (float(a[1]) + float(b[1])) / 2)]
    if t != "polilinea":
        return []
    pts = e.get("puntos") or []
    n = len(pts)
    if n < 2:
        return []
    tramos = n - 1 + (1 if e.get("cerrada") else 0)
    out = []
    for i in range(tramos):
        a, b = i, (i + 1) % n
        bulge = pts[a][2] if len(pts[a]) > 2 else 0
        if abs(float(bulge or 0)) > 1e-12:
            continue
        out.append((a, b, (float(pts[a][0]) + float(pts[b][0])) / 2,
                    (float(pts[a][1]) + float(pts[b][1])) / 2))
    return out


def tiradores(cuerpo) -> dict:
    """De qué se puede jalar esta pieza, en coordenadas del boceto.

    La pantalla los lleva al mundo con el plano de la pieza y los reparte a lo
    alto: abajo, a media altura (el medio de la arista vertical) y arriba. Los
    tres jalan el mismo punto del contorno, porque la pieza es un contorno
    levantado: mover una esquina es mover **la** esquina.
    """
    boceto = next((o for o in cuerpo.operaciones if o.get("op") == "boceto"), None)
    altura = next((float(o.get("mm", 0)) for o in cuerpo.operaciones
                   if o.get("op") == "extruir"), 0.0)
    vertices, segmentos = [], []
    for i, e in (enumerate(boceto.get("entidades") or []) if boceto else []):
        for punto, x, y in _puntos_de(e):
            vertices.append({"entidad": i, "punto": punto, "uv": [x, y]})
        for a, b, mx, my in _segmentos_de(e):
            segmentos.append({"entidad": i, "a": a, "b": b, "uv": [mx, my]})
    return {"id": cuerpo.id, "plano": getattr(cuerpo, "plano", "XY"),
            "altura": altura, "vertices": vertices, "segmentos": segmentos}


def mover_segmento(operaciones: list, entidad: int, a: int, b: int,
                   dx: float, dy: float) -> list:
    """Corre un tramo entero: sus dos extremos se mueven lo mismo.

    Es lo que uno espera al agarrar el medio de una arista y jalarla: la arista
    se mueve, no se dobla. Por dentro son dos puntos movidos, y de ahí en
    adelante es `mover_punto` de siempre: la pieza se rehace desde el contorno
    nuevo y lo que se hizo después se vuelve a aplicar solo.
    """
    ops = json.loads(json.dumps(operaciones))
    op = next((o for o in ops if o.get("op") == "boceto"), None)
    if op is None:
        raise ValueError("este cuerpo no tiene boceto que mover")
    ents = op.get("entidades") or []
    if not (0 <= entidad < len(ents)):
        raise ValueError(f"el boceto no tiene la entidad {entidad}")
    e = ents[entidad]
    for punto in (a, b):
        for k, x, y in _puntos_de(e):
            if k == punto:
                ops = mover_punto(ops, entidad, punto, x + float(dx), y + float(dy))
                ents = next(o for o in ops if o.get("op") == "boceto")["entidades"]
                e = ents[entidad]
                break
        else:
            raise ValueError(f"esa entidad no tiene el punto {punto}")
    return ops
'''

# ── core/solido/rutas.py · las dos rutas nuevas ──────────────────────────────

RUTAS_ANCLA = '''class Exportar(BaseModel):'''

RUTAS_NUEVO = '''@router.get("/{id_}/tiradores")
def tiradores(id_: str):
    """De qué se puede jalar la pieza: los puntos del contorno y el medio de
    sus tramos rectos, en coordenadas del boceto.

    No toca el kernel: sale de leer las operaciones. Por eso la pantalla los
    puede pedir sin que cueste nada y enseñarlos en cuanto se señala la pieza.
    """
    from core.solido import cuerpo as mod
    return mod.tiradores(_cuerpo(id_))


class MoverSegmento(BaseModel):
    entidad: int = 0
    a: int
    b: int
    dx: float
    dy: float


@router.post("/{id_}/mover-segmento")
def mover_segmento(id_: str, entrada: MoverSegmento):
    """Corre un tramo del contorno: sus dos extremos se mueven lo mismo.

    Como todo lo demás aquí, si la pieza sale imposible el historial se queda
    como estaba: vale más que no pase nada a que el modelo quede roto.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    antes = list(c.operaciones)
    if entrada.dx == 0 and entrada.dy == 0:
        return _malla(c)
    try:
        nuevas = mod.mover_segmento(antes, entrada.entidad, entrada.a, entrada.b,
                                    entrada.dx, entrada.dy)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    doc = _doc()
    with doc.transaccion("mover segmento"):
        doc.modificar(id_, {"operaciones": nuevas})
    try:
        return _malla(doc.entidades[id_])
    except HTTPException:
        with doc.transaccion("deshacer mover segmento"):
            doc.modificar(id_, {"operaciones": antes})
        raise


class Exportar(BaseModel):'''

# ── ui/vista.js · enganchar los tiradores al lienzo ──────────────────────────

VISTA = [
    ('''      if (typeof TresD !== "undefined") TresD.pintarFantasma(cc);
''',
     '''      if (typeof TresD !== "undefined") TresD.pintarFantasma(cc);
      // Los tiradores van al final: son lo que se agarra, y lo que se agarra
      // se pinta encima de todo lo demás.
      if (typeof Tiradores !== "undefined") Tiradores.pintar(cc);
'''),
    ('''  if (typeof TresD !== "undefined" && TresD.abajo(e)) { e.preventDefault(); return; }
''',
     '''  // Antes que la cara: un tirador se ve encima de ella y se agarra antes.
  // Si el orden fuera el otro, jalar una esquina empezaría a jalar la cara que
  // tiene debajo y no habría manera de llegar nunca a la esquina.
  if (typeof Tiradores !== "undefined" && Tiradores.abajo(e)) { e.preventDefault(); return; }
  if (typeof TresD !== "undefined" && TresD.abajo(e)) { e.preventDefault(); return; }
'''),
    ('''  if (typeof TresD !== "undefined" && TresD.arrastrando()) { TresD.arriba(); return; }
  if (e.button !== 0 || estado.captura || cajaZoom) return;''',
     '''  if (typeof Tiradores !== "undefined" && Tiradores.arrastrando()) { Tiradores.arriba(); return; }
  if (typeof TresD !== "undefined" && TresD.arrastrando()) { TresD.arriba(); return; }
  if (e.button !== 0 || estado.captura || cajaZoom) return;'''),
    ('''  if (typeof TresD !== "undefined" && TresD.mover(e)) return;''',
     '''  if (typeof Tiradores !== "undefined" && Tiradores.mover(e)) return;
  if (typeof TresD !== "undefined" && TresD.mover(e)) return;'''),
    ('''window.addEventListener("mouseup", (e) => {
  if (typeof Ventanas !== "undefined") Ventanas.terminarNavegacion();''',
     '''window.addEventListener("mouseup", (e) => {
  // También aquí: un arrastre que termina con el ratón fuera del lienzo tiene
  // que soltarse igual, o el tirador se queda pegado al cursor para siempre.
  // `arriba()` se desarma sola, así que llamarla dos veces no hace daño.
  if (typeof Tiradores !== "undefined" && Tiradores.arrastrando()) Tiradores.arriba();
  if (typeof Ventanas !== "undefined") Ventanas.terminarNavegacion();'''),
]

# ── ui/app.js · las piezas del dibujo que se abre ────────────────────────────

APP = [
    ('''  if (window.Bloques) Bloques.olvidar();     // las definiciones son de este dibujo
  estado.trazos = d.trazos;''',
     '''  if (window.Bloques) Bloques.olvidar();     // las definiciones son de este dibujo
  // Y las piezas 3D también son de este dibujo. Hasta la 0.12.1 nadie las
  // pedía al abrir: había que teclear 3D para que aparecieran, y un archivo
  // guardado con piezas se veía vacío de piezas. No se espera a que lleguen:
  // el kernel puede tardar y el plano ya está listo; cuando llegan, se pintan.
  if (window.Cuerpos) { Cuerpos.olvidar(); if (window.Tiradores) Tiradores.olvidar(); Cuerpos.refrescar(); }
  estado.trazos = d.trazos;'''),
    ('''  pintarCapas();
  pintar();
  return true;
}

async function refrescar(encuadra = false) {''',
     '''  // Deshacer una extrusión llega por aquí, no por `recargarTrazos`: si nadie
  // volviera a preguntar qué piezas hay, la pieza deshecha se quedaría pintada
  // encima de un contorno que ya nadie levantó. Preguntar cuesta una llamada
  // que no toca el kernel; sólo se piden las mallas que faltan.
  if (window.Cuerpos && (fuera.size || (p.trazos && p.trazos.length) ||
      (p.geometria && p.geometria.length))) Cuerpos.refrescar();
  pintarCapas();
  pintar();
  return true;
}

async function refrescar(encuadra = false) {'''),
]

# ── ui/cuerpos.js · que una petición en vuelo no se trague la siguiente ──────

CUERPOS_JS = [
    ('''  let pidiendo = false;''',
     '''  let pidiendo = false;
  let otraVez = false;           // llegó otra petición mientras ésta iba en camino'''),
    ('''  async function refrescar() {
    if (pidiendo) return;
    pidiendo = true;''',
     '''  async function refrescar() {
    // Si ya hay una pregunta en vuelo, no se hacen dos: se apunta que al
    // terminar hay que volver a preguntar. Devolverse sin más —como hasta la
    // 0.12.1— perdía la petición buena: abrir un archivo justo mientras la
    // anterior contestaba dejaba las piezas del dibujo nuevo sin pedir.
    if (pidiendo) { otraVez = true; return; }
    pidiendo = true;'''),
    ('''    } finally {
      pidiendo = false;
    }
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
  }''',
     '''    } finally {
      pidiendo = false;
    }
    if (window.invalidarPlano) window.invalidarPlano();
    if (window.pintar) window.pintar();
    if (otraVez) { otraVez = false; await refrescar(); }
  }'''),
]

# ── ui/seleccion.js · los grips del medio, por la cámara ─────────────────────

SELECCION = [
    ('''        for (const m of gripsMedios(id)) {
          if (Math.hypot(m.b[0] - m.a[0], m.b[1] - m.a[1]) * esc < 26) continue;
          const px = (m.p[0] - vx) * esc, py = (vy - m.p[1]) * esc;''',
     '''        for (const m of gripsMedios(id)) {
          if (Math.hypot(m.b[0] - m.a[0], m.b[1] - m.a[1]) * esc < 26) continue;
          // Por `aPX` y por el plano de la entidad, como los de vértice de
          // arriba. Hasta la 0.12.1 esta línea proyectaba a mano en planta y
          // los grips del medio salían en otro sitio en cuanto la vista
          // giraba: el mismo error que costó la 0.11.0, que quedó vivo aquí.
          const mm = Planos.aMundo(planoDe(id), m.p[0], m.p[1], 0);
          const qm = aPX(mm[0], mm[1], mm[2]);
          const px = qm[0], py = qm[1];'''),
]

INDICE = [
    ('<script src="planos.js"></script>',
     '<script src="planos.js"></script>\n<script src="tiradores.js"></script>'),
]

BOCETO = [
    ('"""De un boceto de draw101 (entidades 2D) a un sólido de build123d.',
     '"""De un boceto del dibujo (entidades 2D) a un sólido de build123d.'),
]

PAQUETE_NSIS = [
    ('''    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "perMachine": true,
      "shortcutName": "shape101"
    }''',
     '''    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true,
      "perMachine": true,
      "shortcutName": "shape101",
      "installerIcon": "build/icon.ico",
      "uninstallerIcon": "build/icon.ico",
      "installerHeaderIcon": "build/icon.ico",
      "installerHeader": "build/installerHeader.bmp",
      "installerSidebar": "build/installerSidebar.bmp",
      "uninstallerSidebar": "build/uninstallerSidebar.bmp"
    }'''),
]

BITACORA_ANCLA = "BITACORA: list[dict] = [\n"

BITACORA_ENTRADA = '''BITACORA: list[dict] = [
    {
        "version": "0.13.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Las piezas traen tiradores: un cuadrito en cada esquina —abajo, a media altura y "
            "arriba— y un círculo en el medio de cada arista. Se arrastran y la pieza se rehace "
            "desde el contorno nuevo, sin perder lo que hayas hecho después.",
            "Arrastrar el medio de una arista corre la arista entera: se mueve, no se dobla.",
            "Con el ortho encendido, el tirador se va por un solo eje.",
            "Al abrir un archivo con piezas, las piezas ya se ven. Antes había que teclear 3D "
            "para que aparecieran, y un dibujo guardado se veía vacío de piezas.",
            "Deshacer una extrusión ya borra la pieza de la pantalla.",
            "Los grips del medio de una línea se ven en su sitio en las cuatro ventanas. "
            "Seguían proyectándose en planta, como la selección antes de la 0.12.0.",
            "El instalador es de shape101: icono propio —una pieza en isometría— y sus "
            "pantallas. Hasta ahora llevaba el icono de draw101.",
        ],
    },
'''

# ── el flujo · de dónde sale el Python y la poda de releases ─────────────────

FUENTE_VIEJA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.12.0/shape101-0.12.0-setup.exe")
FUENTE_NUEVA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.12.1/shape101-0.12.1-setup.exe")

PODA_ANCLA = "      - name: El cuaderno del armado, pase lo que pase"

PODA = r'''      - name: Podar releases viejas de descargas (quedan las 3 más recientes)
        if: success()
        continue-on-error: true
        shell: bash
        env:
          GH_TOKEN: ${{ secrets.TOKEN_DESCARGAS }}
          VER: ${{ steps.version.outputs.version }}
        run: |
          # Mike, 18-sep: «quedémonos sólo con las 3 últimas». Cada instalador
          # pesa 340 MB y llegaron a ser quince.
          #
          # REGLA QUE NO SE ROMPE: la más reciente nunca se borra, porque de
          # ella sale el Python empotrado del siguiente armado. Por eso se
          # guardan tres y no una: margen de sobra para que un armado en vuelo
          # encuentre la suya. `shape101-ultima` es un puntero fijo y tampoco
          # se toca: el patrón de abajo sólo casa con números.
          #
          # Va con `continue-on-error`: cuando esto corre, la versión ya está
          # publicada y comprobada. Que la limpieza falle no puede convertir un
          # armado bueno en uno rojo.
          set -e
          if [ -z "$GH_TOKEN" ]; then echo "sin TOKEN_DESCARGAS: no se poda nada"; exit 0; fi
          mapfile -t TAGS < <(gh api --paginate repos/mikebalcazar/descargas/releases \
            --jq '.[].tag_name' | grep -E '^shape101-[0-9]+\.[0-9]+\.[0-9]+$' \
            | sort -t- -k2 -V -r)
          echo "releases de shape101 publicadas: ${#TAGS[@]}"
          if [ "${#TAGS[@]}" -le 3 ]; then echo "tres o menos: no hay qué podar"; exit 0; fi
          echo "se quedan: ${TAGS[0]} ${TAGS[1]} ${TAGS[2]}"
          for t in "${TAGS[@]:3}"; do
            if [ "$t" = "shape101-$VER" ]; then
              echo "::warning::$t es la que se acaba de publicar: no se toca"
              continue
            fi
            echo "borrando $t"
            gh release delete "$t" --repo mikebalcazar/descargas --cleanup-tag --yes || \
              echo "::warning::no se pudo borrar $t"
          done

'''


def main() -> int:
    t_shape = os.environ["TOKEN_SHAPE101"]
    raiz = pathlib.Path("/tmp/recado34")
    raiz.mkdir(parents=True, exist_ok=True)
    shape = raiz / "shape101"
    # Clon completo, no `--depth 1`: hay que fundir una rama.
    correr(["git", "clone",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # 0 · los archivos nuevos, que ya estaban empujados aparte
    correr(["git", "fetch", "origin", RAMA_NUEVA], cwd=shape)
    correr(["git", "merge", "--no-edit", "FETCH_HEAD"], cwd=shape)
    for n in ("ui/tiradores.js", "pruebas/t025_tiradores.py", "build/imagenes.py"):
        if not (shape / n).is_file():
            raise RuntimeError(f"la fusión no trajo {n}")
    anotar(f"fundida {RAMA_NUEVA}: tiradores.js, t025 e imagenes.py")

    # 1 · el motor: de qué se agarra una pieza y cómo se corre una arista
    parchar(shape / "core" / "solido" / "cuerpo.py",
            [(CUERPO_ANCLA, CUERPO_NUEVO)], "core/solido/cuerpo.py")
    parchar(shape / "core" / "solido" / "rutas.py",
            [(RUTAS_ANCLA, RUTAS_NUEVO)], "core/solido/rutas.py")

    # 2 · la pantalla
    parchar(shape / "ui" / "vista.js", VISTA, "ui/vista.js")
    parchar(shape / "ui" / "app.js", APP, "ui/app.js")
    parchar(shape / "ui" / "cuerpos.js", CUERPOS_JS, "ui/cuerpos.js")
    parchar(shape / "ui" / "seleccion.js", SELECCION, "ui/seleccion.js")
    parchar(shape / "ui" / "index.html", INDICE, "ui/index.html")
    parchar(shape / "core" / "solido" / "boceto.py", BOCETO, "core/solido/boceto.py")

    # 3 · las imágenes del instalador, dibujadas aquí y versionadas
    correr([sys.executable, "-m", "pip", "install", "-q", "pillow", "pyyaml"])
    salida = correr([sys.executable, "build/imagenes.py"], cwd=shape)
    for l in salida.strip().splitlines():
        anotar("imagen" + l)
    for n in ("icon.ico", "icon.png", "installerHeader.bmp", "installerSidebar.bmp",
              "uninstallerSidebar.bmp"):
        f = shape / "build" / n
        if not f.is_file() or f.stat().st_size < 1000:
            raise RuntimeError(f"build/{n} no se generó bien")
    parchar(shape / "package.json", PAQUETE_NSIS, "package.json (nsis)")

    # 4 · la versión, en los dos sitios que deben decir lo mismo
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    for viejo, nuevo, donde in ((f'VERSION = "{VERSION_VIEJA}"', f'VERSION = "{VERSION_NUEVA}"',
                                 "VERSION"),
                                (BITACORA_ANCLA, BITACORA_ENTRADA, "bitácora")):
        if t.count(viejo) != 1:
            raise RuntimeError(f"core/version.py ({donde}): no pega")
        t = t.replace(viejo, nuevo)
    ver.write_text(t, encoding="utf-8")
    anotar(f"core/version.py: {VERSION_NUEVA} con su entrada de bitácora")

    paq = shape / "package.json"
    t = paq.read_text(encoding="utf-8")
    n = t.count(VERSION_VIEJA)
    if n != 3:
        raise RuntimeError(f"package.json: {VERSION_VIEJA} aparece {n} veces, esperaba 3")
    paq.write_text(t.replace(VERSION_VIEJA, VERSION_NUEVA), encoding="utf-8")
    anotar(f"package.json: los 3 sitios dicen {VERSION_NUEVA}")

    # 5 · el flujo: hereda de la 0.12.1 y poda lo viejo
    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if FUENTE_NUEVA not in t:
        if t.count(FUENTE_VIEJA) != 1:
            raise RuntimeError("el flujo: INSTALADOR_ANTERIOR no dice lo que esperaba")
        t = t.replace(FUENTE_VIEJA, FUENTE_NUEVA)
        anotar("armar-y-publicar.yml: el Python empotrado se hereda de la 0.12.1")
    if "Podar releases viejas" not in t:
        if t.count(PODA_ANCLA) != 1:
            raise RuntimeError("el flujo: no encuentro dónde meter la poda")
        t = t.replace(PODA_ANCLA, PODA + PODA_ANCLA)
        anotar("armar-y-publicar.yml: poda de releases (quedan las 3 más recientes)")
    flujo.write_text(t, encoding="utf-8")

    # 6 · nada se dispara sin comprobar antes todo lo comprobable sin Windows
    for n in ("ui/tiradores.js", "ui/vista.js", "ui/app.js", "ui/cuerpos.js", "ui/seleccion.js"):
        correr(["node", "--check", str(shape / n)])
    anotar("los 5 archivos de JavaScript son válidos (node --check)")
    for n in ("core/solido/cuerpo.py", "core/solido/rutas.py", "core/solido/boceto.py",
              "core/version.py", "pruebas/t025_tiradores.py", "build/imagenes.py"):
        ast.parse((shape / n).read_text(encoding="utf-8"))
    anotar("los 6 archivos de Python son válidos")
    cuerpo_py = (shape / "core" / "solido" / "cuerpo.py").read_text(encoding="utf-8")
    for f in ("def tiradores(", "def mover_segmento("):
        if f not in cuerpo_py:
            raise RuntimeError(f"cuerpo.py se quedó sin «{f}»")
    rutas_py = (shape / "core" / "solido" / "rutas.py").read_text(encoding="utf-8")
    for f in ("/{id_}/tiradores", "/{id_}/mover-segmento"):
        if f not in rutas_py:
            raise RuntimeError(f"rutas.py se quedó sin «{f}»")
    anotar("el motor tiene sus dos funciones y sus dos rutas")
    import yaml
    if not yaml.safe_load(flujo.read_text(encoding="utf-8"))["jobs"]:
        raise RuntimeError("el flujo dejó de ser YAML válido")
    anotar("armar-y-publicar.yml: YAML válido")
    if '<script src="tiradores.js">' not in (shape / "ui" / "index.html").read_text(encoding="utf-8"):
        raise RuntimeError("index.html no carga tiradores.js")
    anotar("index.html carga tiradores.js")
    puesta = correr([sys.executable, "-c",
                     "import sys; sys.path.insert(0, '.'); "
                     "from core.version import VERSION; print(VERSION)"], cwd=shape).strip()
    dicho = json.loads(paq.read_text(encoding="utf-8"))["version"]
    if not (puesta == dicho == VERSION_NUEVA):
        raise RuntimeError(f"las versiones no coinciden: version.py={puesta} package.json={dicho}")
    anotar(f"version.py y package.json dicen lo mismo: {puesta}")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: tiradores, piezas al abrir, instalador propio (0.13.0)\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.13.0: tiradores en las piezas, piezas al abrir, instalador propio\n\n"
            "Tiradores en vértices y medios de arista, que Mike pidió el 18-sep. Una pieza\n"
            "es un contorno levantado, así que un tirador no deforma triángulos: dice qué\n"
            "punto del contorno mueve y el motor rehace la pieza desde el contorno nuevo.\n"
            "Cada esquina da tres —abajo, a media altura y arriba— y los tres jalan el mismo\n"
            "punto; cada tramo recto da dos, y ésos corren la arista entera sin doblarla.\n"
            "Los tramos curvos se quedan sin tirador de medio a propósito: arrastrarlo\n"
            "tendría que cambiar la curvatura, y eso es otra operación.\n\n"
            "Al abrir un archivo con piezas, las piezas ya se ven: nadie le preguntaba al\n"
            "motor qué piezas había al cargar un dibujo, y había que teclear 3D. Deshacer\n"
            "una extrusión también borra ya la pieza de la pantalla.\n\n"
            "El instalador lleva icono y pantallas de shape101, no las de draw101.\n\n"
            "Y dos que salieron al pasar: los grips del medio de una línea seguían\n"
            "proyectándose a mano en planta —el error de la 0.11.0, vivo en un rincón—, y\n"
            "Cuerpos.refrescar() perdía una petición si llegaba con otra en vuelo.\n\n"
            "512 comprobaciones en 25 pruebas, verdes, con el kernel de verdad.\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado")
    correr(["git", "push", "-f", "origin", f"HEAD:refs/heads/claude/publicar-{VERSION_NUEVA}"],
           cwd=shape)
    anotar(f"rama claude/publicar-{VERSION_NUEVA} empujada: el armado arranca solo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado34/shape101")
    if not (shape / ".git").is_dir():
        return
    try:
        correr(["git", "merge", "--abort"], cwd=shape)
    except Exception:
        pass
    try:
        correr(["git", "checkout", "--", "."], cwd=shape)
        correr(["git", "clean", "-fd"], cwd=shape)
        correr(["git", "checkout", "-B", "claude/recado-fallo"], cwd=shape)
        (shape / "claude").mkdir(exist_ok=True)
        (shape / "claude" / "ultimo-recado.md").write_text(
            "# Último recado · FALLÓ\n\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n\n"
            "```\n" + "\n".join(lineas) + "\n\nERROR: " + error + "\n```\n", encoding="utf-8")
        correr(["git", "add", "claude/ultimo-recado.md"], cwd=shape)
        correr(["git", "commit", "-m", "recado fallido: dónde se rompió"], cwd=shape)
        correr(["git", "push", "-f", "origin", "claude/recado-fallo"], cwd=shape)
    except Exception as e2:
        print(f"ni el aviso del fracaso se pudo escribir: {e2}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        d = _sin_secretos(f"{type(e).__name__}: {e}")
        print(f"el recado falló: {d}")
        avisar_del_fracaso(d)
        sys.exit(1)
