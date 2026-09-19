"""El mandadero · recado 35: la 0.14.0, cada punto y cada arista suyos.

Mike, el 19-sep, viendo la 0.13.0: *«debería ser un sólido, cada contorno
independiente (un loft como dices). Todas las aristas son independientes y
todos los puntos también. Para generar el sólido se generan superficies entre
cada región creada por las aristas»*.

Hasta la 0.13.0 los tiradores salían del **boceto**: una pieza era un contorno
levantado, así que la esquina de abajo y la de arriba eran el mismo punto y
mover una movía las dos. Ahora salen del **sólido**.

**Lo que no se perdió.** La pieza se sigue guardando como cómo se hizo. Las
dos operaciones nuevas apuntan a un **nombre** —`abajo|lado[0]|lado[3]` es la
esquina donde se juntan esas tres caras— y no a un índice, así que cambiar una
cota del boceto no le cambia el nombre a la esquina. Comprobado en t025: el
mismo nombre sobre un boceto de 900 de ancho cae en 900, y jalarlo 50 da 950.

Las tres trampas que costaron su rato, todas anotadas en el código:

1. **Rellenar el contorno de una cara alabeada la infla.** Medido: una cara se
   iba a z = −39.53 en una pieza de 18 de espesor. Ahora va superficie reglada
   entre los lados opuestos y se queda exactamente en 0..18.
2. **El reglado reescribe sus bordes como BSPLINE** aunque sean rectos. La
   segunda edición los dejaba quietos y el contorno ya no cerraba. Ahora se
   **mide** si una arista es recta en vez de creerle al nombre del tipo.
3. **Los nombres se perdían** al alabearse una cara, porque se buscaban por
   superficie —y una cara reglada no tiene una sola normal—. Ahora van por
   centro y área contra las caras guardadas.

Y el arreglo que Mike pidió aparte: **Ctrl+Z ya redibuja al instante**. Lo que
cambia en una pieza 3D no viaja en el parche de trazos, así que deshacer
devolvía un parche vacío, la llave del plano no cambiaba y el lienzo reusaba el
cuadro de antes.

Medido antes de disparar, con el kernel de verdad: **531 comprobaciones en 25
pruebas, todas verdes**, t025 con 45 suyas.

El módulo nuevo (`core/solido/remallar.py`), el de pantalla (`ui/tiradores.js`)
y la prueba ya están en la rama `claude/loft-0.14.0`; aquí se funde y se
parchan los cuatro archivos que sólo cambian por dentro.
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
RAMA_NUEVA = "claude/loft-0.14.0"
VERSION_VIEJA = "0.13.0"
VERSION_NUEVA = "0.14.0"

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
    """Cada trozo tiene que aparecer **una sola vez**. Si no pega, o pega dos
    veces, el recado se para aquí en vez de dejar un archivo medio parchado."""
    t = ruta.read_text(encoding="utf-8")
    for i, (viejo, nuevo) in enumerate(cambios):
        n = t.count(viejo)
        if n != 1:
            raise RuntimeError(f"{donde} #{i}: «{viejo[:70]}…» aparece {n} veces, esperaba 1")
        t = t.replace(viejo, nuevo)
    ruta.write_text(t, encoding="utf-8")
    anotar(f"{donde}: {len(cambios)} cambio(s)")


# ── core/solido/nombres.py · nombrar vértices y reconocer caras regladas ─────

NOMBRES = [
    ('''    def arista(self, solido: Shape, nombre: str) -> Edge:''',
     '''    def vertices(self, solido: Shape) -> dict:
        """`nombreA|nombreB|nombreC → vértice` para cada punto donde se juntan
        tres o más caras nombradas.

        Es la misma idea que los nombres de arista, un piso más abajo: un punto
        no se llama por dónde está —eso cambia en cuanto se mueve algo— sino
        por **qué caras lo forman**. Así, mover una cota del boceto no le
        cambia el nombre a la esquina, y una esquina jalada sigue jalada.

        Si dos puntos distintos comparten las mismas caras —pasa en piezas con
        huecos— se desempatan por posición, en orden, y eso también es estable
        mientras la topología no cambie.
        """
        caras = list(solido.faces())
        nombres = self.nombres_en(solido)
        crudo: dict = {}
        for v in solido.vertices():
            vecinas = sorted({nombres[i] for i, f in enumerate(caras)
                              if nombres[i] and _cara_toca(f, v)})
            if len(vecinas) < 3:
                continue
            crudo.setdefault("|".join(vecinas), []).append(v)
        out = {}
        for nombre, vs in crudo.items():
            if len(vs) == 1:
                out[nombre] = vs[0]
                continue
            for k, v in enumerate(sorted(vs, key=lambda q: (round(q.X, 6), round(q.Y, 6),
                                                            round(q.Z, 6)))):
                out[f"{nombre}#{k}"] = v
        return out

    def vertice(self, solido: Shape, nombre: str):
        todos = self.vertices(solido)
        if nombre in todos:
            return todos[nombre]
        # Por si llega con las caras en otro orden: el nombre es un conjunto.
        base, _, sufijo = nombre.partition("#")
        clave = "|".join(sorted(base.split("|"))) + (f"#{sufijo}" if sufijo else "")
        try:
            return todos[clave]
        except KeyError:
            raise KeyError(f"no hay un vértice llamado «{nombre}»; hay: {sorted(todos)}")

    def arista(self, solido: Shape, nombre: str) -> Edge:'''),

    ('''    def aristas(self, solido: Shape) -> dict[str, Edge]:
        """`nombreA|nombreB → arista` para cada arista entre dos caras nombradas."""
        out = {}
        caras = list(solido.faces())
        nombres = {i: self.nombre_de(f) for i, f in enumerate(caras)}''',
     '''    def nombres_en(self, solido: Shape) -> dict:
        """`índice de cara → nombre`, para las caras de **este** sólido.

        Primero por dónde está cada cara, contra las que ya se tienen
        guardadas, y sólo después por superficie. El orden importa: desde la
        0.14.0 una cara puede dejar de ser plana —se alabea al mover un punto y
        pasa a ser una superficie reglada—, y por superficie no se
        reconocería. Con eso se perderían su nombre, los de sus aristas y los
        de sus vértices, que es justo el historial que este archivo existe para
        sostener.
        """
        guardadas = {}
        for nombre, f in self.caras.items():
            try:
                guardadas.setdefault(_donde(f), nombre)
            except Exception:
                continue
        out = {}
        for i, f in enumerate(solido.faces()):
            n = None
            try:
                n = guardadas.get(_donde(f))
            except Exception:
                n = None
            out[i] = n if n else self.nombre_de(f)
        return out

    def aristas(self, solido: Shape) -> dict[str, Edge]:
        """`nombreA|nombreB → arista` para cada arista entre dos caras nombradas."""
        out = {}
        caras = list(solido.faces())
        nombres = self.nombres_en(solido)'''),

    ('''def huella(cara: Face) -> tuple:''',
     '''def _donde(cara: Face) -> tuple:
    """Dónde está esta cara y cuánto mide. Sin la normal, a propósito.

    `huella` lleva la normal, y para una cara plana es la mejor identidad que
    hay. Pero desde la 0.14.0 una cara puede ser **reglada** —se alabea al
    mover un punto— y entonces no tiene una sola normal: `normal_at()` da un
    valor distinto según dónde se pregunte, y la huella deja de casar consigo
    misma. Medido el 19-sep: tras dos ediciones encadenadas, `lado[1]` perdía
    su nombre y con él el de sus cuatro aristas; de doce aristas nombradas
    quedaban ocho.

    Centro y área alcanzan para reconocer **la misma cara del mismo sólido**,
    que es para lo único que se usa esto.
    """
    c = cara.center()
    return (round(c.X, 3), round(c.Y, 3), round(c.Z, 3), round(cara.area, 2))


def huella(cara: Face) -> tuple:'''),

    ('''def _cara_tiene(cara: Face, arista: Edge) -> bool:
    m = arista.position_at(0.5)
    for e in cara.edges():
        if (e.position_at(0.5) - m).length < TOL_DIST and abs(e.length - arista.length) < TOL_DIST:
            return True
    return False''',
     '''def _cara_toca(cara: Face, vertice) -> bool:
    """¿Ese punto es uno de los vértices de esta cara? Se compara por posición
    con la misma tolerancia que todo lo demás: dos objetos distintos del kernel
    pueden ser el mismo punto del mundo."""
    p = (vertice.X, vertice.Y, vertice.Z)
    for v in cara.vertices():
        if (abs(p[0] - v.X) < TOL_DIST and abs(p[1] - v.Y) < TOL_DIST
                and abs(p[2] - v.Z) < TOL_DIST):
            return True
    return False


def _extremos(e: Edge) -> tuple:
    """Los dos extremos de una arista, ordenados: sirven de identidad sin
    depender de cómo esté parametrizada."""
    a, b = e.start_point(), e.end_point()
    pa = (round(a.X, 4), round(a.Y, 4), round(a.Z, 4))
    pb = (round(b.X, 4), round(b.Y, 4), round(b.Z, 4))
    return (pa, pb) if pa <= pb else (pb, pa)


def _cara_tiene(cara: Face, arista: Edge) -> bool:
    """¿Esta arista es una de las de esta cara?

    Se compara por **extremos**, no por el punto de en medio. Desde la 0.14.0
    la misma arista puede llegar como LINE desde una cara y como BSPLINE desde
    la de al lado —la superficie reglada de una cara alabeada reescribe sus
    bordes—, y un BSPLINE no tiene su punto medio geométrico en el parámetro
    0.5: la parametrización no es uniforme. Medido el 19-sep: por el punto
    medio, las cuatro aristas de la cara reglada se quedaban sin nombre y de
    doce nombradas quedaban ocho.

    Un círculo completo tiene los dos extremos en el mismo sitio, así que el
    largo sigue entrando en la comparación para no confundir dos que se cierren
    sobre el mismo punto.
    """
    ext = _extremos(arista)
    for e in cara.edges():
        if _extremos(e) == ext and abs(e.length - arista.length) < TOL_DIST:
            return True
    return False'''),
]

# ── core/solido/historial.py · las dos operaciones nuevas ────────────────────

HISTORIAL = [
    ('''  {"op": "empujar_cara", "cara": "arriba", "mm": 10}     positivo = hacia afuera
''',
     '''  {"op": "empujar_cara", "cara": "arriba", "mm": 10}     positivo = hacia afuera
  {"op": "mover_vertice", "vertice": "abajo|lado[0]|lado[3]", "d": [dx, dy, dz]}
  {"op": "mover_arista",  "arista": "lado[1]|arriba",         "d": [dx, dy, dz]}
'''),
    ('''from core.solido import boceto, nombres''',
     '''from core.solido import boceto, nombres, remallar'''),
    ('''OPERACIONES = {"boceto", "extruir", "restar", "redondear", "empujar_cara"}''',
     '''OPERACIONES = {"boceto", "extruir", "restar", "redondear", "empujar_cara",
               "mover_vertice", "mover_arista"}'''),
    ('''    else:
        raise ValueError(f"op {i}: no conozco «{clase}»")''',
     '''    elif clase in ("mover_vertice", "mover_arista"):
        # Mover un punto o una arista del **sólido**, no del boceto.
        #
        # Mike lo pidió así el 19-sep: cada punto y cada arista independientes.
        # Que apunten a un nombre y no a un índice es lo que hace que esto siga
        # siendo un historial: cambias una cota del boceto y la esquina que
        # jalaste sigue siendo esa esquina.
        if solido is None:
            raise ValueError(f"op {i}: {clase} sin una pieza antes")
        d = op.get("d") or [0, 0, 0]
        if clase == "mover_vertice":
            v = nom.vertice(solido, op["vertice"])
            puntos = [remallar.punto_de(v)]
        else:
            a = nom.arista(solido, op["arista"])
            puntos = [remallar.punto_de(a.start_point()), remallar.punto_de(a.end_point())]
        if not all(abs(k) < 1e-9 for k in d):       # mover cero no es mover
            # Por `nombres_en`, no por `nombre_de`: una cara que ya se alabeó
            # en una edición anterior es una superficie reglada, y por
            # superficie no se reconocería. Medido el 19-sep: con `nombre_de`,
            # la segunda edición encadenada dejaba a `lado[1]` sin nombre y con
            # él se iban sus cuatro aristas y cuatro de los ocho vértices.
            porIndice = nom.nombres_en(solido)
            viejos = [porIndice[k] for k in range(len(solido.faces()))]
            solido, caras, _ = remallar.mover(solido, [(p, tuple(d)) for p in puntos], viejos)
            nom.caras = caras
    else:
        raise ValueError(f"op {i}: no conozco «{clase}»")'''),
]

# ── core/solido/cuerpo.py · los tiradores salen del sólido ───────────────────

CUERPO_DESDE = "def _puntos_de(e: dict) -> list:"

CUERPO_NUEVO = '''def tiradores(cuerpo) -> dict:
    """De qué se puede jalar esta pieza: **sus vértices y sus aristas de
    verdad**, no los puntos del boceto.

    Mike, el 19-sep: «todas las aristas son independientes y todos los puntos
    también». Hasta la 0.13.0 los tiradores salían del contorno, así que una
    esquina de abajo y la de arriba eran el mismo punto y moverla movía las
    dos. Ahora cada uno es suyo.

    Cada tirador viaja con su **nombre**, no con un índice: `abajo|lado[0]|
    lado[3]` es la esquina donde se juntan esas tres caras, y lo sigue siendo
    aunque cambie una cota del boceto. Es lo mismo que ya hacía posible jalar
    una cara y que siguiera jalada.

    Todo en coordenadas del kernel; `rutas.py` lo gira al plano de la pieza.
    """
    reg = regenerar(cuerpo)
    salida = {"id": cuerpo.id, "plano": getattr(cuerpo, "plano", "XY"),
              "vertices": [], "aristas": []}
    if reg.solido is None:
        return salida
    for nombre, v in reg.nombrador.vertices(reg.solido).items():
        salida["vertices"].append({"nombre": nombre, "p": [v.X, v.Y, v.Z]})
    for nombre, e in reg.nombrador.aristas(reg.solido).items():
        m = e.position_at(0.5)
        a, b = e.start_point(), e.end_point()
        salida["aristas"].append({"nombre": nombre, "p": [m.X, m.Y, m.Z],
                                  "a": [a.X, a.Y, a.Z], "b": [b.X, b.Y, b.Z],
                                  "recta": e.geom_type.name == "LINE"})
    return salida


def mover_vertice(operaciones: list, nombre: str, d) -> list:
    """Una operación más al final: esa esquina, corrida. No se toca nada de lo
    anterior, así que deshacer es quitar la última y ya."""
    return json.loads(json.dumps(operaciones)) + [
        {"op": "mover_vertice", "vertice": nombre, "d": [float(k) for k in d]}]


def mover_arista(operaciones: list, nombre: str, d) -> list:
    return json.loads(json.dumps(operaciones)) + [
        {"op": "mover_arista", "arista": nombre, "d": [float(k) for k in d]}]
'''

# ── core/solido/rutas.py · la vuelta del mundo, y las dos rutas ──────────────

RUTAS_DEL_MUNDO = [
    ('''def _al_mundo(m: dict, plano: str) -> dict:''',
     '''def _del_mundo(plano: str, p):
    """(x, y, z) del mundo → (u, v, w) del kernel. La vuelta exacta de
    `_a_mundo`, y por eso se escriben juntas: si un día cambia una, la otra
    tiene que cambiar en el mismo renglón.

      XY: (x, y, z) → (x, y, z)
      XZ: (u, −w, v) = (x, y, z) → (x, z, −y)
      YZ: (w, u, v)  = (x, y, z) → (y, z, x)
    """
    x, y, z = p[0], p[1], p[2] if len(p) > 2 else 0.0
    if plano == "XZ":
        return [x, z, -y]
    if plano == "YZ":
        return [y, z, x]
    return [x, y, z]


def _al_mundo(m: dict, plano: str) -> dict:'''),
]

RUTAS_DESDE = '@router.get("/{id_}/tiradores")'
RUTAS_HASTA = 'class Exportar(BaseModel):'

RUTAS_NUEVO = '''@router.get("/{id_}/tiradores")
def tiradores(id_: str):
    """De qué se puede jalar la pieza: sus vértices y sus aristas de verdad,
    cada uno con su nombre, ya girados al plano de la pieza.

    Esto sí toca el kernel —hay que tener el sólido para saber sus puntos—,
    pero la regeneración está en caché por huella de las operaciones: pedirlos
    después de pintar no cuesta nada.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    d = mod.tiradores(c)
    plano = d["plano"]
    for v in d["vertices"]:
        v["p"] = _a_mundo(plano, v["p"])
    for a in d["aristas"]:
        for k in ("p", "a", "b"):
            a[k] = _a_mundo(plano, a[k])
    return d


class MoverEnElMundo(BaseModel):
    nombre: str
    d: list[float]


def _mover(id_: str, entrada: MoverEnElMundo, cual: str):
    """El camino común de mover un vértice y mover una arista.

    El arrastre llega en coordenadas del mundo —es lo que el ratón sabe— y se
    gira al plano de la pieza antes de entrar al historial, porque el kernel
    siempre trabaja en XY.

    Si la pieza sale imposible, el historial se queda como estaba. Es la misma
    promesa de todas las demás operaciones: vale más que no pase nada a que el
    modelo quede roto y el usuario no sepa en qué momento.
    """
    from core.solido import cuerpo as mod
    c = _cuerpo(id_)
    antes = list(c.operaciones)
    if all(abs(k) < 1e-9 for k in entrada.d):
        return _malla(c)
    d = _del_mundo(getattr(c, "plano", "XY"), list(entrada.d) + [0.0, 0.0, 0.0])
    hacer = mod.mover_vertice if cual == "vertice" else mod.mover_arista
    nuevas = hacer(antes, entrada.nombre, d)
    doc = _doc()
    with doc.transaccion(f"mover {cual}"):
        doc.modificar(id_, {"operaciones": nuevas})
    try:
        return _malla(doc.entidades[id_])
    except HTTPException:
        with doc.transaccion(f"deshacer mover {cual}"):
            doc.modificar(id_, {"operaciones": antes})
        raise


@router.post("/{id_}/mover-vertice")
def mover_vertice(id_: str, entrada: MoverEnElMundo):
    """Una esquina de la pieza, corrida. Sólo esa."""
    return _mover(id_, entrada, "vertice")


@router.post("/{id_}/mover-arista")
def mover_arista(id_: str, entrada: MoverEnElMundo):
    """Una arista entera, corrida: sus dos extremos se mueven lo mismo."""
    return _mover(id_, entrada, "arista")


class Exportar(BaseModel):'''

# ── ui/app.js · Ctrl+Z redibuja al instante ──────────────────────────────────

APP = [
    ('''$("#b-deshacer").onclick = async () => {
  const r = await post("/api/deshacer");
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  if (r.accion) Comandos.eco("Deshecho: " + r.accion);
};
$("#b-rehacer").onclick = async () => {
  const r = await post("/api/rehacer");
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  if (r.accion) Comandos.eco("Rehecho: " + r.accion);
};''',
     '''/* Deshacer y rehacer **siempre** vuelven a preguntar por las piezas y siempre
 * redibujan. Mike, 19-sep: «cuando das ctrl+Z, no se dibuja luego luego el
 * undo hasta que no haces otro comando».
 *
 * Por qué pasaba: lo que cambia en una pieza 3D no viaja en el parche de
 * trazos —una pieza no es un trazo—, así que deshacer una extrusión o un punto
 * movido devolvía un parche vacío. Con el parche vacío, `aplicarParche` no
 * creaba un arreglo de trazos nuevo, la llave del plano no cambiaba (ver
 * `llavePlano` en vista.js, que compara por identidad del arreglo) y el lienzo
 * reusaba el cuadro de antes. Se veía igual hasta que otro comando invalidaba
 * la caché, que es exactamente lo que Mike describió.
 *
 * Preguntar por las piezas cuesta una llamada que ni toca el kernel, y
 * deshacer no pasa sesenta veces por segundo. */
async function trasDeshacerORehacer(r, verbo) {
  aplicar(r);
  if (!aplicarParche(r)) await recargarTrazos();
  if (window.Cuerpos) {
    Cuerpos.olvidar();
    if (window.Tiradores) Tiradores.olvidar();
    Cuerpos.refrescar();
  }
  if (window.invalidarPlano) window.invalidarPlano();
  pintar();
  if (r.accion) Comandos.eco(verbo + ": " + r.accion);
}
$("#b-deshacer").onclick = async () => {
  await trasDeshacerORehacer(await post("/api/deshacer"), "Deshecho");
};
$("#b-rehacer").onclick = async () => {
  await trasDeshacerORehacer(await post("/api/rehacer"), "Rehecho");
};'''),
]

BITACORA_ANCLA = "BITACORA: list[dict] = [\n"

BITACORA_ENTRADA = '''BITACORA: list[dict] = [
    {
        "version": "0.14.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Cada punto y cada arista de una pieza se mueven solos. Los tiradores ya no "
            "salen del contorno sino del sólido: la esquina de arriba y la de abajo son dos "
            "puntos distintos, y mover una ya no mueve la otra.",
            "Arrastrar el medio de una arista la corre entera, sin doblarla.",
            "El arrastre va en el plano de la ventana donde estás: en la Superior sobre XY, "
            "en la Frontal sobre XZ, en la Lateral sobre YZ.",
            "Una pieza puede dejar de ser un prisma: si una cara se alabea, se pone la "
            "superficie que pasa por sus cuatro puntos, sin inflarse.",
            "Lo que se hizo después —un barreno, una cara jalada— se sigue volviendo a "
            "aplicar solo: la pieza se guarda como cómo se hizo, no como geometría.",
            "Si un movimiento deja una pieza imposible, el programa lo dice y no cambia nada.",
            "Ctrl+Z ya redibuja al instante. Antes había que dar otro comando para ver el "
            "resultado de deshacer.",
        ],
    },
'''

FUENTE_VIEJA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.12.1/shape101-0.12.1-setup.exe")
FUENTE_NUEVA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.13.0/shape101-0.13.0-setup.exe")


def main() -> int:
    t_shape = os.environ["TOKEN_SHAPE101"]
    raiz = pathlib.Path("/tmp/recado35")
    raiz.mkdir(parents=True, exist_ok=True)
    shape = raiz / "shape101"
    correr(["git", "clone",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # 0 · lo que ya estaba empujado aparte
    correr(["git", "fetch", "origin", RAMA_NUEVA], cwd=shape)
    correr(["git", "merge", "--no-edit", "FETCH_HEAD"], cwd=shape)
    for n in ("core/solido/remallar.py", "ui/tiradores.js", "pruebas/t025_tiradores.py"):
        if not (shape / n).is_file():
            raise RuntimeError(f"la fusión no trajo {n}")
    anotar(f"fundida {RAMA_NUEVA}: remallar.py, tiradores.js y t025")

    # 1 · el motor
    parchar(shape / "core" / "solido" / "nombres.py", NOMBRES, "core/solido/nombres.py")
    parchar(shape / "core" / "solido" / "historial.py", HISTORIAL, "core/solido/historial.py")

    cue = shape / "core" / "solido" / "cuerpo.py"
    t = cue.read_text(encoding="utf-8")
    if CUERPO_DESDE not in t:
        raise RuntimeError("cuerpo.py: no encuentro dónde empieza la cola vieja")
    cue.write_text(t[:t.index(CUERPO_DESDE)] + CUERPO_NUEVO, encoding="utf-8")
    anotar("core/solido/cuerpo.py: los tiradores salen del sólido")

    rut = shape / "core" / "solido" / "rutas.py"
    parchar(rut, RUTAS_DEL_MUNDO, "core/solido/rutas.py (la vuelta del mundo)")
    t = rut.read_text(encoding="utf-8")
    if RUTAS_DESDE not in t or RUTAS_HASTA not in t:
        raise RuntimeError("rutas.py: no encuentro el bloque de rutas a reemplazar")
    viejo = t[t.index(RUTAS_DESDE):t.index(RUTAS_HASTA) + len(RUTAS_HASTA)]
    rut.write_text(t.replace(viejo, RUTAS_NUEVO), encoding="utf-8")
    anotar("core/solido/rutas.py: tiradores del sólido y las dos rutas de mover")

    # 2 · la pantalla
    parchar(shape / "ui" / "app.js", APP, "ui/app.js")

    # 3 · la versión
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

    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if FUENTE_NUEVA not in t:
        if t.count(FUENTE_VIEJA) != 1:
            raise RuntimeError("el flujo: INSTALADOR_ANTERIOR no dice lo que esperaba")
        flujo.write_text(t.replace(FUENTE_VIEJA, FUENTE_NUEVA), encoding="utf-8")
        anotar("armar-y-publicar.yml: el Python empotrado se hereda de la 0.13.0")

    # 4 · nada se dispara sin comprobar antes todo lo comprobable sin Windows
    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    for n in ("ui/tiradores.js", "ui/vista.js", "ui/app.js", "ui/cuerpos.js"):
        correr(["node", "--check", str(shape / n)])
    anotar("los 4 archivos de JavaScript son válidos (node --check)")
    for n in ("core/solido/remallar.py", "core/solido/nombres.py", "core/solido/historial.py",
              "core/solido/cuerpo.py", "core/solido/rutas.py", "core/version.py",
              "pruebas/t025_tiradores.py"):
        ast.parse((shape / n).read_text(encoding="utf-8"))
    anotar("los 7 archivos de Python son válidos")

    def exige(ruta, trozos, donde):
        t = (shape / ruta).read_text(encoding="utf-8")
        faltan = [x for x in trozos if x not in t]
        if faltan:
            raise RuntimeError(f"{donde} se quedó sin: {faltan}")

    exige("core/solido/nombres.py", ["def vertices(", "def vertice(", "def nombres_en(",
                                     "def _donde(", "def _cara_toca(", "def _extremos("],
          "nombres.py")
    exige("core/solido/historial.py", ["mover_vertice", "mover_arista", "remallar.mover",
                                       "nom.nombres_en("], "historial.py")
    exige("core/solido/cuerpo.py", ["def tiradores(", "def mover_vertice(", "def mover_arista("],
          "cuerpo.py")
    exige("core/solido/rutas.py", ["def _del_mundo(", "/{id_}/mover-vertice",
                                   "/{id_}/mover-arista", "class MoverEnElMundo"], "rutas.py")
    exige("ui/app.js", ["trasDeshacerORehacer"], "app.js")
    exige("ui/index.html", ['<script src="tiradores.js">'], "index.html")
    anotar("el motor y la pantalla tienen todas sus piezas nuevas")

    import yaml
    if not yaml.safe_load(flujo.read_text(encoding="utf-8"))["jobs"]:
        raise RuntimeError("el flujo dejó de ser YAML válido")
    puesta = correr([sys.executable, "-c",
                     "import sys; sys.path.insert(0, '.'); "
                     "from core.version import VERSION; print(VERSION)"], cwd=shape).strip()
    dicho = json.loads(paq.read_text(encoding="utf-8"))["version"]
    if not (puesta == dicho == VERSION_NUEVA):
        raise RuntimeError(f"las versiones no coinciden: version.py={puesta} package.json={dicho}")
    anotar(f"version.py y package.json dicen lo mismo: {puesta}")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\\n\\n*Lo escribe `claude/recado.py` al correr en Actions.*\\n\\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\\n"
        "- recado: la 0.14.0, cada punto y cada arista suyos\\n\\n```\\n"
        + "\\n".join(lineas) + "\\n```\\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.14.0: cada punto y cada arista de una pieza, independientes\\n\\n"
            "Mike, viendo la 0.13.0: «debería ser un sólido, cada contorno independiente.\\n"
            "Todas las aristas son independientes y todos los puntos también».\\n\\n"
            "Los tiradores ya no salen del boceto sino del sólido. Dos operaciones nuevas\\n"
            "—mover_vertice y mover_arista— apuntan a un NOMBRE derivado de las caras que\\n"
            "forman el punto, no a un índice, así que el historial sigue siendo un\\n"
            "historial: cambias una cota del boceto y la esquina que jalaste sigue siendo\\n"
            "esa esquina. Comprobado: el mismo nombre sobre un boceto de 900 de ancho cae\\n"
            "en 900, y jalarlo 50 da 950.\\n\\n"
            "Tres trampas del kernel, las tres anotadas donde se arreglaron:\\n\\n"
            "- Rellenar el contorno de una cara alabeada la infla: medido, una cara se iba\\n"
            "  a z = -39.53 en una pieza de 18 de espesor. Va reglada entre los lados\\n"
            "  opuestos y se queda en 0..18.\\n"
            "- El reglado reescribe sus bordes como BSPLINE aunque sean rectos. Ahora se\\n"
            "  mide si una arista es recta en vez de creerle al nombre del tipo.\\n"
            "- Los nombres se perdían al alabearse una cara, porque se buscaban por\\n"
            "  superficie y una cara reglada no tiene una sola normal.\\n\\n"
            "Y Ctrl+Z ya redibuja al instante: lo que cambia en una pieza no viaja en el\\n"
            "parche de trazos, así que deshacer devolvía un parche vacío y el lienzo\\n"
            "reusaba el cuadro de antes.\\n\\n"
            "531 comprobaciones en 25 pruebas, verdes, con el kernel de verdad.\\n\\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\\n"
            "Claude-Session: https://claude.ai/code/session_01TKb4oF3d8wwHYJ6eKA7qew"],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    anotar("main actualizado")
    correr(["git", "push", "-f", "origin", f"HEAD:refs/heads/claude/publicar-{VERSION_NUEVA}"],
           cwd=shape)
    anotar(f"rama claude/publicar-{VERSION_NUEVA} empujada: el armado arranca solo")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado35/shape101")
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
            "# Último recado · FALLÓ\\n\\n"
            f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\\n\\n"
            "```\\n" + "\\n".join(lineas) + "\\n\\nERROR: " + error + "\\n```\\n", encoding="utf-8")
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
