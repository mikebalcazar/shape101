"""El mandadero · recado 27: 0.11.0 — planos por ventana y el híbrido de activación.

Lo que Mike pidió tras la 0.10.0, más lo pendiente, todo junto:

1. **Orbitar sólo en la Perspectiva**, con el botón central; **Shift + central**
   hace pan ahí. En las tres ortogonales el central es pan y nada más.
2. **Activación híbrida**: la ventana activa se elige con clic y se queda para
   los comandos; el mouse over sólo manda para pan, zoom y órbita, que van a
   la ventana bajo el cursor sin cambiar la activa. Esto quita además el
   fallo de la 0.10.0: el mouse over cambiaba la ventana a mitad del comando,
   la línea se calculaba con una cámara y se pintaba con otra, y la
   Perspectiva brincaba.
3. **Plano por ventana.** Cada línea del dibujo sabe en qué plano vive
   (`plano`: XY, XZ o YZ); nace con el plano de la ventana activa; los archivos
   viejos valen XY. La Frontal dibuja sobre XZ y la Lateral sobre YZ. El visor,
   el hule, la selección y el fantasma de extruir lo respetan en las cuatro.
4. **El kernel sigue en XY** —donde los nombres de caras están probados— y la
   pieza se rota al salir: a la pantalla y al STEP. Un contorno en la Frontal
   se extruye hacia quien mira; en la Lateral, hacia +X. Los tres mapeos son
   rotaciones, no espejos, y `ui/planos.js` hace la misma cuenta.
5. Una prueba nueva, `t024_planos`, extruye un contorno en XZ y comprueba que
   la pieza sale a donde debe.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
import shutil
import subprocess
import sys

DUENO = "mikebalcazar"
RAMA = "claude/planos-por-ventana"
VERSION = "0.11.0"
DESTINO = f"claude/publicar-{VERSION}"

lineas: list[str] = []


def anotar(t: str) -> None:
    print(t, flush=True)
    lineas.append(t)


def _sin_secretos(t: str) -> str:
    for n in ("TOKEN_DRAW101", "TOKEN_SHAPE101"):
        v = os.environ.get(n)
        if v:
            t = t.replace(v, "***")
    return t


def correr(orden, cwd=None) -> str:
    h = subprocess.run(orden, cwd=cwd, capture_output=True, text=True)
    if h.returncode != 0:
        raise RuntimeError(_sin_secretos(f"falló {orden[0]}: {h.stderr.strip()[-800:]}"))
    return h.stdout


def fin_de(t: str) -> str:
    return "\r\n" if "\r\n" in t else "\n"


def cambiar(texto: str, viejo: str, nuevo: str, donde: str, veces: int = 1) -> str:
    fin = fin_de(texto)
    viejo, nuevo = viejo.replace("\n", fin), nuevo.replace("\n", fin)
    n = texto.count(viejo)
    if veces and n != veces:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba {veces}")
    if not veces and n == 0:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» no aparece")
    return texto.replace(viejo, nuevo)


def parchar(ruta: pathlib.Path, cambios, ya: str, donde: str) -> None:
    t = ruta.read_text(encoding="utf-8")
    if ya in t:
        anotar(f"{donde}: ya estaba, no se toca")
        return
    for c in cambios:
        veces = c[2] if len(c) > 2 else 1
        t = cambiar(t, c[0], c[1], donde, veces)
    ruta.write_text(t, encoding="utf-8", newline="")
    anotar(f"{donde}: parchado")


PLANO_MOTOR = '''def _a_mundo(plano: str, p):
    """(u, v, w) del kernel → (x, y, z) del mundo. Rotaciones, no espejos:
    XZ → (u, −w, v), hacia quien mira la Frontal; YZ → (w, u, v), hacia +X.
    `ui/planos.js` hace exactamente la misma cuenta."""
    u, v, w = p[0], p[1], p[2] if len(p) > 2 else 0.0
    if plano == "XZ":
        return [u, -w, v]
    if plano == "YZ":
        return [w, u, v]
    return [u, v, w]


def _al_mundo(m: dict, plano: str) -> dict:
    """La malla del kernel, ya en el mundo. El kernel siempre trabaja en XY:
    ahí los nombres de caras están probados. La pieza se rota al salir."""
    if plano in (None, "", "XY"):
        return m
    for cara in m.get("caras", []):
        v = cara.get("v") or []
        nuevo = []
        for k in range(0, len(v), 3):
            nuevo.extend(_a_mundo(plano, (v[k], v[k + 1], v[k + 2])))
        cara["v"] = nuevo
    m["aristas"] = [[_a_mundo(plano, p) for p in a] for a in m.get("aristas", [])]
    return m


def _rotar(solido, plano: str):
    """Lo mismo para el sólido que se exporta: la rotación que lleva el plano
    del kernel al del mundo."""
    from build123d import Axis
    if plano == "XZ":
        return solido.rotate(Axis.X, 90)
    if plano == "YZ":
        return solido.rotate(Axis((0, 0, 0), (1, 1, 1)), 120)
    return solido


def _malla(cuerpo):'''

T024 = '''"""Planos por ventana · un contorno dibujado en la Frontal se extruye hacia quien mira.

Mike (17-sep): «cuando dibujas en la ventana de la vista superior, dibuja
sobre X-Y en Z = 0, y así según la vista». Cada línea sabe en qué plano vive y
la pieza sale a donde debe. El kernel sigue trabajando en XY —donde los
nombres de caras están probados— y la pieza se rota al salir.
"""
from __future__ import annotations

from core import entidades as E
from core.documento import Documento
from core.solido import rutas
from pruebas import comun

DESCRIPCION = "extruir sobre XZ y YZ: la pieza sale a donde debe"

ANCHO, ALTO, ESPESOR = 900.0, 600.0, 18.0


def caja(malla):
    xs, ys, zs = [], [], []
    for c in malla["caras"]:
        v = c["v"]
        for k in range(0, len(v), 3):
            xs.append(v[k]); ys.append(v[k + 1]); zs.append(v[k + 2])
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def correr(r: comun.Reporte):
    from core.solido import cuerpo as mod
    doc = Documento.nuevo()
    rutas.enchufar(lambda: doc)
    mod.olvidar()

    # Dibujado en la Frontal: (u, v) son (x, z). Se extruye hacia −Y.
    frontal = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, ALTO, 0], [0, ALTO, 0]], cerrada=True)
    frontal.plano = "XZ"
    doc.agregar(frontal)
    m = rutas.extruir(rutas.Extruir(ids=[frontal.id], mm=ESPESOR))
    r.igual(doc.entidades[m["id"]].plano, "XZ", "la pieza recuerda el plano del contorno")
    (x0, x1), (y0, y1), (z0, z1) = caja(m)
    r.casi(x1 - x0, ANCHO, "en la Frontal el ancho va sobre X", 1e-6)
    r.casi(z1 - z0, ALTO, "en la Frontal el alto va sobre Z", 1e-6)
    r.casi(y1 - y0, ESPESOR, "el espesor va sobre Y", 1e-6)
    r.casi(y1, 0.0, "y crece hacia quien mira: la pieza queda en Y negativa", 1e-6)
    r.casi(m["volumen_mm3"], ANCHO * ALTO * ESPESOR, "el volumen no cambia por rotar", 1.0)

    # Dibujado en la Lateral: (u, v) son (y, z). Se extruye hacia +X.
    lateral = E.Polilinea(puntos=[[0, 0, 0], [ANCHO, 0, 0], [ANCHO, ALTO, 0], [0, ALTO, 0]], cerrada=True)
    lateral.plano = "YZ"
    doc.agregar(lateral)
    m2 = rutas.extruir(rutas.Extruir(ids=[lateral.id], mm=ESPESOR))
    (x0, x1), (y0, y1), (z0, z1) = caja(m2)
    r.casi(y1 - y0, ANCHO, "en la Lateral el ancho va sobre Y", 1e-6)
    r.casi(z1 - z0, ALTO, "en la Lateral el alto va sobre Z", 1e-6)
    r.casi(x1 - x0, ESPESOR, "el espesor va sobre X", 1e-6)
    r.casi(x0, 0.0, "y crece hacia +X", 1e-6)

    # Un archivo viejo no trae plano y vale XY.
    vieja = E.de_dict({"tipo": "linea", "p1": [0, 0], "p2": [100, 0]})
    r.igual(getattr(vieja, "plano", None), "XY", "una entidad sin plano vale XY")
'''

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Cada ventana dibuja sobre su plano: la Superior sobre el suelo, la Frontal sobre "
            "XZ y la Lateral sobre YZ. Cada línea recuerda en qué plano vive y se ve en las "
            "cuatro ventanas desde su ángulo, con su selección y su hule.",
            "Extruir empuja en la dirección del plano: un contorno de la Frontal se levanta "
            "hacia quien mira; uno de la Lateral, hacia el lado. STEP y STL salen ya rotados.",
            "La ventana activa se elige con clic y se queda para los comandos. Pan, zoom y "
            "órbita van a la ventana bajo el cursor sin cambiarla: es lo que quita el brinco "
            "de la Perspectiva y el hule mal pintado de la 0.10.0.",
            "Orbitar sólo existe en la Perspectiva, con el botón central. Shift + central hace "
            "pan ahí. En las ortogonales el central es pan.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado27")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # --- el motor -----------------------------------------------------------
    parchar(shape / "core" / "entidades.py", [
        ('    grupo: str = ""',
         '    grupo: str = ""\n'
         '    # En qué plano vive: XY (el suelo), XZ (la Frontal) o YZ (la Lateral).\n'
         '    # Los archivos viejos no lo traen y valen XY. Ver ui/planos.js.\n'
         '    plano: str = "XY"'),
    ], 'plano: str = "XY"', "core/entidades.py (cada línea sabe su plano)")
    parchar(shape / "core" / "dibujo.py", [
        ('        "capa": e.capa,', '        "capa": e.capa,\n        "plano": getattr(e, "plano", "XY"),', 0),
    ], '"plano": getattr(e, "plano", "XY")', "core/dibujo.py (los trazos llevan el plano)")
    parchar(shape / "core" / "solido" / "rutas.py", [
        ("def _malla(cuerpo):", PLANO_MOTOR),
        ('    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"))',
         '    nuevo = Cuerpo(operaciones=ops, capa=entidades[0].get("capa", "0"),\n'
         '                   plano=entidades[0].get("plano", "XY"))'),
        ('    f = _factor_mm()\n    if f != 1.0 and "volumen_mm3" in m:',
         '    m = _al_mundo(m, getattr(cuerpo, "plano", "XY"))\n    f = _factor_mm()\n    if f != 1.0 and "volumen_mm3" in m:'),
        ('    solido = reg.solido.scale(f) if f != 1.0 else reg.solido',
         '    solido = reg.solido.scale(f) if f != 1.0 else reg.solido\n    solido = _rotar(solido, getattr(c, "plano", "XY"))'),
    ], "_al_mundo", "core/solido/rutas.py (la pieza se rota al salir)")
    (shape / "pruebas" / "t024_planos.py").write_text(T024, encoding="utf-8")
    anotar("pruebas/t024_planos.py escrita")

    # --- la pantalla --------------------------------------------------------
    parchar(shape / "ui" / "ventanas.js", [
        ("  /** Activar: la cámara de esa ventana pasa a ser `estado.vista`. */",
         "  /** Navegar —pan, zoom, órbita— en la ventana bajo el cursor sin cambiar\n"
         "   *  la activa: la activa es de los comandos, y se elige con clic. Mike lo\n"
         "   *  quiso así: híbrido. Dura lo que dura el gesto. */\n"
         "  let navegando = null;\n"
         "  function navegarEn(px, py) {\n"
         "    const i = bajo(px, py);\n"
         "    if (i < 0 || i === activa || typeof estado === \"undefined\") return false;\n"
         "    navegando = i;\n"
         "    estado.vista = ventanas[i];\n"
         "    return true;\n"
         "  }\n"
         "  function terminarNavegacion() {\n"
         "    if (navegando === null || typeof estado === \"undefined\") return;\n"
         "    navegando = null;\n"
         "    estado.vista = ventanas[activa];\n"
         "  }\n\n"
         "  /** Activar: la cámara de esa ventana pasa a ser `estado.vista`. */"),
        ("           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,",
         "           adoptar, encuadrarTodas, pintarTodas, proyectar, TITULO,\n           navegarEn, terminarNavegacion,"),
    ], "function navegarEn", "ui/ventanas.js (navegar sin activar)")

    vista = shape / "ui" / "vista.js"
    # 1 · activar sólo con el botón izquierdo; navegar con el central sin activar
    parchar(vista, [
        ("    const i = Ventanas.bajo(vx0, vy0);\n    if (i >= 0 && i !== Ventanas.activa) { Ventanas.activar(i); invalidarPlano(); pintar(); }",
         "    const i = Ventanas.bajo(vx0, vy0);\n"
         "    if (e.button === 0 && i >= 0 && i !== Ventanas.activa) { Ventanas.activar(i); invalidarPlano(); pintar(); }\n"
         "    if (e.button === 1) Ventanas.navegarEn(vx0, vy0);      // pan u órbita donde está el cursor"),
        ('  if (e.button === 1 && typeof Camara !== "undefined" && (estado.vista.persp ? !e.altKey : e.altKey)) { Camara.arrastrar(e); e.preventDefault(); return; }',
         '  if (e.button === 1 && typeof Camara !== "undefined" && estado.vista.persp && !e.shiftKey) { Camara.arrastrar(e); e.preventDefault(); return; }'),
    ], "Ventanas.navegarEn(vx0, vy0)", "ui/vista.js (central navega; orbitar sólo en la Perspectiva)")
    # 2 · fuera el mouse over que activaba
    parchar(vista, [
        ("  // La ventana se activa con solo pasar el mouse: zoom, pan y órbita van\n"
         "  // donde está el cursor. No mientras se arrastra algo.\n"
         "  if (typeof Ventanas !== \"undefined\" && e.buttons === 0 && !(typeof Extrusion !== \"undefined\" && Extrusion.activa())) {\n"
         "    const iv = Ventanas.bajo(px, py);\n"
         "    if (iv >= 0 && iv !== Ventanas.activa) { Ventanas.activar(iv); invalidarPlano(); }\n"
         "  }\n", ""),
    ], "__sin_mouse_over__", "ui/vista.js (el mouse over ya no activa)")
    # 3 · la rueda navega en la ventana bajo el cursor; al soltar se vuelve a la activa
    parchar(vista, [
        ("  zoomEn(e.clientX - caja.left, e.clientY - caja.top, e.deltaY < 0 ? f : 1 / f);",
         "  if (typeof Ventanas !== \"undefined\") Ventanas.navegarEn(e.clientX - caja.left, e.clientY - caja.top);\n"
         "  zoomEn(e.clientX - caja.left, e.clientY - caja.top, e.deltaY < 0 ? f : 1 / f);\n"
         "  if (typeof Ventanas !== \"undefined\") Ventanas.terminarNavegacion();"),
        ('window.addEventListener("mouseup", (e) => {',
         'window.addEventListener("mouseup", (e) => {\n  if (typeof Ventanas !== "undefined") Ventanas.terminarNavegacion();'),
    ], "Ventanas.terminarNavegacion()", "ui/vista.js (rueda y soltar)")
    # 4 · aMM devuelve coordenadas del plano de la ventana
    parchar(vista, [
        ("  const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;\n  const cz = Math.cos(v.rz), sz = Math.sin(v.rz);\n  return [ux * cz + uy * sz, -ux * sz + uy * cz];",
         "  // En la Frontal y la Lateral lo que se devuelve son las coordenadas del\n"
         "  // plano de la ventana —(x, z) o (y, z)—, que es donde se dibuja ahí.\n"
         "  if (v.plano === \"XZ\" || v.plano === \"YZ\") return [ux, vy];\n"
         "  const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;\n  const cz = Math.cos(v.rz), sz = Math.sin(v.rz);\n  return [ux * cz + uy * sz, -ux * sz + uy * cz];"),
    ], 'if (v.plano === "XZ" || v.plano === "YZ") return [ux, vy];', "ui/vista.js (aMM por plano)")
    # 5 · pintarParte por el plano de la parte o de la ventana
    t = vista.read_text(encoding="utf-8")
    if "const P = (x, y) =>" not in t:
        ini = t.index("function pintarParte(h, c = ctx) {")
        fin_f = t.index("\nfunction ", ini + 10)
        cuerpo = t[ini:fin_f]
        n = cuerpo.count("aPX(")
        cuerpo = cuerpo.replace("aPX(", "P(")
        eol = fin_de(t)
        cuerpo = cuerpo.replace("function pintarParte(h, c = ctx) {",
                                "function pintarParte(h, c = ctx) {" + eol
                                + "  // Cada parte va por su plano, o por el de la ventana activa si no lo trae." + eol
                                + "  const P = (x, y) => { const m = typeof Planos !== \"undefined\" ? Planos.aMundo(h.plano || estado.vista.plano || \"XY\", x, y, 0) : [x, y, 0]; return aPX(m[0], m[1], m[2]); };", 1)
        t = t[:ini] + cuerpo + t[fin_f:]
        vista.write_text(t, encoding="utf-8", newline="")
        anotar(f"ui/vista.js (pintarParte por plano): {n} conversiones pasan por el plano")

    parchar(shape / "ui" / "visor.js", [
        ("              const q = aPX(pol[i][0], pol[i][1], 0);",
         "              const mp = Planos.aMundo(t.plano || \"XY\", pol[i][0], pol[i][1], 0);\n              const q = aPX(mp[0], mp[1], mp[2]);"),
        ("          const q = aPX(pts[i][0], pts[i][1], 0);",
         "          const mp = Planos.aMundo(t.plano || \"XY\", pts[i][0], pts[i][1], 0);\n          const q = aPX(mp[0], mp[1], mp[2]);"),
        ("      const q = aPX(t.p[0], t.p[1], 0);",
         "      const mp = Planos.aMundo(t.plano || \"XY\", t.p[0], t.p[1], 0);\n      const q = aPX(mp[0], mp[1], mp[2]);"),
    ], "Planos.aMundo(t.plano", "ui/visor.js (pinta cada trazo en su plano)")

    parchar(shape / "ui" / "dibujar.js", [
        ("async function crearEntidad(entidad, accion) {",
         "async function crearEntidad(entidad, accion) {\n"
         "  // Lo nuevo nace en el plano de la ventana activa.\n"
         "  if (entidad && !entidad.plano && estado.vista && estado.vista.plano) entidad.plano = estado.vista.plano;"),
        ("async function crearVarias(entidades, accion) {",
         "async function crearVarias(entidades, accion) {\n"
         "  for (const en of entidades || []) if (en && !en.plano && estado.vista && estado.vista.plano) en.plano = estado.vista.plano;"),
    ], "Lo nuevo nace en el plano", "ui/dibujar.js (lo nuevo nace en el plano de la ventana)")

    parchar(shape / "ui" / "extruir.js", [
        ("      out.push(t.puntos.map((p) => [p[0], p[1]]));",
         "      out.push({ plano: t.plano || \"XY\", pts: t.puntos.map((p) => [p[0], p[1]]) });"),
        ("    const q0 = window.aPX(0, 0, 0), q1 = window.aPX(0, 0, 1);",
         "    const n = Planos.normal(a.contornos[0].plano);\n    const q0 = window.aPX(0, 0, 0), q1 = window.aPX(n[0], n[1], n[2]);"),
        ("    for (const pts of a.contornos) {", "    for (const { plano, pts } of a.contornos) {"),
        ("      pts.forEach((p, i) => { const q = window.aPX(p[0], p[1], a.mm); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]); });",
         "      pts.forEach((p, i) => { const m = Planos.aMundo(plano, p[0], p[1], a.mm); const q = window.aPX(m[0], m[1], m[2]); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]); });"),
        ("        const q0 = window.aPX(p[0], p[1], 0), q1 = window.aPX(p[0], p[1], a.mm);",
         "        const m0 = Planos.aMundo(plano, p[0], p[1], 0), m1 = Planos.aMundo(plano, p[0], p[1], a.mm);\n"
         "        const q0 = window.aPX(m0[0], m0[1], m0[2]), q1 = window.aPX(m1[0], m1[1], m1[2]);"),
    ], "Planos.normal(a.contornos[0].plano)", "ui/extruir.js (el fantasma en su plano)")

    parchar(shape / "ui" / "index.html", [
        ('<script src="extruir.js"></script>', '<script src="extruir.js"></script>\n<script src="planos.js"></script>'),
    ], "planos.js", "ui/index.html (carga los planos)")

    # --- la versión -----------------------------------------------------------
    hoy = dt.date.today().isoformat()
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    actual = re.search(r'VERSION = "([^"]+)"', t).group(1)
    if actual != VERSION:
        t = cambiar(t, f'VERSION = "{actual}"', f'VERSION = "{VERSION}"', "version.py")
        t = re.sub(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', t, count=1)
        ver.write_text(cambiar(t, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy), "version.py"),
                       encoding="utf-8")
        paq = shape / "package.json"
        t = paq.read_text(encoding="utf-8")
        t = cambiar(t, f'"version": "{actual}"', f'"version": "{VERSION}"', "package.json")
        t = cambiar(t, f'"_versionApp": "{actual} —', f'"_versionApp": "{VERSION} —', "package.json")
        paq.write_text(cambiar(t, f'"artifactName": "shape101-{actual}-setup.${{ext}}"',
                               f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"', "package.json"),
                       encoding="utf-8")
        anotar(f"versión {actual} → {VERSION}")

    for js in ("vista.js", "ventanas.js", "visor.js", "dibujar.js", "extruir.js", "planos.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    correr([sys.executable, "-c",
            "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in "
            "('core/entidades.py', 'core/dibujo.py', 'core/solido/rutas.py', 'pruebas/t024_planos.py')]"], cwd=shape)
    anotar("seis archivos de la pantalla pasan node --check; cuatro de Python siguen válidos")
    # La misma cuenta en las dos lenguas: si difiere, la pieza sale a otro sitio.
    js = correr(["node", "-e",
                 "const P=require('./ui/planos.js');console.log(JSON.stringify([P.aMundo('XZ',1,2,3),P.aMundo('YZ',1,2,3),P.aMundo('XY',1,2,3)]))"], cwd=shape).strip()
    if js != "[[1,-3,2],[3,1,2],[1,2,3]]":
        raise RuntimeError(f"planos.js no mapea como el motor: {js}")
    anotar("planos.js y el motor hacen la misma cuenta")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, planos por ventana y activación híbrida\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: planos por ventana y activación híbrida\n\n"
            "Cada línea sabe en qué plano vive y nace con el plano de la ventana activa; la\n"
            "Frontal dibuja sobre XZ y la Lateral sobre YZ. El kernel sigue en XY, donde los\n"
            "nombres de caras están probados, y la pieza se rota al salir: a la pantalla y al\n"
            "STEP. Los tres mapeos son rotaciones, no espejos, y ui/planos.js hace la misma\n"
            "cuenta que el motor; el recado lo comprueba.\n\n"
            "La ventana activa se elige con clic y se queda para los comandos; pan, zoom y\n"
            "órbita van a la ventana bajo el cursor sin cambiarla. Eso quita el brinco de la\n"
            "Perspectiva y el hule mal pintado de la 0.10.0. Orbitar sólo en la Perspectiva,\n"
            "con el central; Shift + central hace pan ahí."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado27/shape101")
    if not (shape / ".git").is_dir():
        return
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
