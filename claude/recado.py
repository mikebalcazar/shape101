"""El mandadero · recado 33: que navegar en otra ventana no secuestre el gesto.

Mike, probando la 0.12.0, reportó tres fallos:

  2. «Cuando uso el PAN sin que esté seleccionada la vista de perspectiva me
     mueve la vista seleccionada. Cada vez que uso el click central, me regresa
     la vista al centro, no la deja en donde está.»
  3. «Cuando uso PAN en otra vista que no está seleccionada, se selecciona la
     superior de nuevo solita y me mueve esa.»
  *. «Cuando uso shift+clickcentral en una vista que no está seleccionada me
     mueve la vista seleccionada, no la del mouse en ella.»

**Los tres son el mismo defecto**, y está en una sola línea.

`Ventanas.adoptar()` es la que, la primera vez, convierte la cámara de siempre
—la que el programa traía antes de que hubiera cuatro ventanas— en la ventana
Superior, y encuadra las otras tres. Debe correr **una vez**. Para saber si ya
había corrido se preguntaba:

    if (estado.vista === ventanas[activa]) return false;   // ya adopté

Esa pregunta es falsa durante la navegación. Cuando Mike aprieta el botón
central sobre una ventana que no es la activa, `navegarEn` apunta
`estado.vista` a la ventana **bajo el cursor** — que por definición no es
`ventanas[activa]`. Y `adoptar()` corre en cada repintado (`ui/vista.js`), o
sea a mitad del arrastre. Entonces se cree sin estrenar y secuestra el gesto:

  · `activa = 0`            → «se selecciona la superior de nuevo solita»
  · `estado.vista = ventanas[0]` → «me mueve la vista seleccionada»
  · `encuadrarTodas(puntos)`     → «me regresa la vista al centro»

Exactamente los tres síntomas, en ese orden.

El arreglo es una bandera propia: `adoptar()` se acuerda ella sola de que ya
corrió, en vez de deducirlo de un estado que el usuario mueve. La lección
—otra vez— es que una bandera de «ya pasó» no se infiere de otra cosa.

Va con prueba, en `pruebas/t007_dibujo.py`, corrida en el navegador de verdad:
navegar en una ventana que no es la activa y forzar el repintado de a mitad.
Medido aquí: sin el arreglo la prueba falla en dos comprobaciones; con él pasa.

De paso, el Python empotrado pasa a heredarse de la 0.12.0 —la última release
publicada— en vez de la 0.11.0, que es más vieja y está más cerca de la poda.

Sale como **0.12.1**: sólo se arregló algo, no hay nada nuevo que aprender.
"""
from __future__ import annotations

import ast
import datetime as dt
import os
import pathlib
import subprocess
import sys

DUENO = "mikebalcazar"
VERSION_VIEJA = "0.12.0"
VERSION_NUEVA = "0.12.1"

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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:70]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo)


# ── 1 · el arreglo ───────────────────────────────────────────────────────────

ADOPTAR_VIEJO = """  function adoptar(puntos) {
    if (typeof estado === "undefined" || estado.vista === ventanas[activa]) return false;
"""

ADOPTAR_NUEVO = """  let adoptado = false;
  function adoptar(puntos) {
    // La bandera es propia a propósito. Antes se preguntaba si `estado.vista`
    // era ya la ventana activa, y eso es falso a mitad de una navegación: con
    // el botón central sobre otra ventana, `estado.vista` apunta a la de abajo
    // del cursor. Adoptar se creía sin estrenar y secuestraba el gesto —volvía
    // la activa a la Superior y reencuadraba las cuatro—. Una bandera de «ya
    // pasó» no se deduce de un estado que el usuario mueve.
    if (typeof estado === "undefined" || adoptado) return false;
    adoptado = true;
"""

# ── 2 · la prueba que lo caza ────────────────────────────────────────────────

LLAMADA_VIEJA = """        _un_grip_mueve_su_punto(r, pagina, base, primera)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
"""

LLAMADA_NUEVA = """        _un_grip_mueve_su_punto(r, pagina, base, primera)
        _navegar_no_secuestra(r, pagina)
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
"""

PRUEBA_NUEVA = '''

def _navegar_no_secuestra(r: comun.Reporte, pagina) -> None:
    """Pan, zoom u órbita en una ventana que no es la activa: el repintado que
    ocurre a mitad del gesto no debe cambiar de ventana activa ni reencuadrar.

    En 0.12.0 sí lo hacía. `adoptar()` —la que la primera vez convierte la
    cámara de siempre en la ventana Superior— se creía sin estrenar cada vez
    que `estado.vista` no era la ventana activa, y durante la navegación es
    justo así: `estado.vista` apunta a la ventana bajo el cursor. Entonces
    secuestraba el gesto. Tres síntomas, un solo defecto.
    """
    datos = pagina.evaluate("""() => {
        Ventanas.activar(0);
        const f = Ventanas.la(2);                      // la Frontal, abajo a la izquierda
        const antes = { x: f.x, y: f.y, escala: f.escala };
        const navego = Ventanas.navegarEn(f.ox + f.w / 2, f.oy + f.h / 2);
        const tomo = estado.vista === f;
        Ventanas.adoptar([[0, 0, 0], [100, 100, 100]]);    // el repintado de a mitad
        const salida = {
            navego, tomo,
            activa: Ventanas.activa,
            sigueEnLaDeAbajo: estado.vista === f,
            seMovio: f.x !== antes.x || f.y !== antes.y || f.escala !== antes.escala,
        };
        Ventanas.terminarNavegacion();
        salida.vuelveALaActiva = estado.vista === Ventanas.laActiva();
        return salida;
    }""")
    r.cierto(datos["navego"] and datos["tomo"],
             "el botón central sobre otra ventana navega en ella")
    r.igual(datos["activa"], 0, "y la ventana activa no cambia sola")
    r.cierto(datos["sigueEnLaDeAbajo"],
             "el gesto sigue mandando en la ventana de abajo del cursor")
    r.cierto(not datos["seMovio"], "y nadie reencuadra a media navegación")
    r.cierto(datos["vuelveALaActiva"], "al soltar, el mando vuelve a la activa")
'''

# ── 3 · la bitácora ──────────────────────────────────────────────────────────

BITACORA_ANCLA = "BITACORA: list[dict] = [\n"

BITACORA_ENTRADA = '''BITACORA: list[dict] = [
    {
        "version": "0.12.1",
        "fecha": "2026-09-19",
        "cambios": [
            "Pan, zoom y órbita en una ventana que no es la activa ya no cambian de ventana "
            "activa ni devuelven las cuatro al centro. Movías una y se movía otra: el "
            "repintado de a mitad del gesto lo secuestraba.",
            "Shift + clic central en una ventana que no es la activa mueve esa, la de abajo "
            "del cursor, que es donde están las manos.",
        ],
    },
'''

# ── 4 · el Python empotrado, de la release más nueva ─────────────────────────

FUENTE_VIEJA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.11.0/shape101-0.11.0-setup.exe")
FUENTE_NUEVA = ("  INSTALADOR_ANTERIOR: https://github.com/mikebalcazar/descargas/releases/"
                "download/shape101-0.12.0/shape101-0.12.0-setup.exe")


def main() -> int:
    t_shape = os.environ["TOKEN_SHAPE101"]
    raiz = pathlib.Path("/tmp/recado33")
    raiz.mkdir(parents=True, exist_ok=True)
    shape = raiz / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)

    # 1 · adoptar se acuerda ella sola de que ya corrió
    ven = shape / "ui" / "ventanas.js"
    t = ven.read_text(encoding="utf-8")
    if "let adoptado = false;" in t:
        anotar("ui/ventanas.js ya tenía la bandera: no se toca")
    else:
        ven.write_text(cambiar(t, ADOPTAR_VIEJO, ADOPTAR_NUEVO, "ventanas.js"), encoding="utf-8")
        anotar("ui/ventanas.js: adoptar() corre una vez y ya; la navegación no la despierta")

    # 2 · la prueba que lo caza, en el navegador de verdad
    pru = shape / "pruebas" / "t007_dibujo.py"
    t = pru.read_text(encoding="utf-8")
    if "_navegar_no_secuestra" in t:
        anotar("t007 ya tenía la prueba: no se toca")
    else:
        t = cambiar(t, LLAMADA_VIEJA, LLAMADA_NUEVA, "t007 (llamada)")
        pru.write_text(t.rstrip("\n") + "\n" + PRUEBA_NUEVA, encoding="utf-8")
        anotar("pruebas/t007_dibujo.py: 5 comprobaciones nuevas de navegación entre ventanas")

    # 3 · la versión, en los dos sitios que deben decir lo mismo
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    t = cambiar(t, f'VERSION = "{VERSION_VIEJA}"', f'VERSION = "{VERSION_NUEVA}"',
                "version.py (VERSION)")
    t = cambiar(t, BITACORA_ANCLA, BITACORA_ENTRADA, "version.py (bitácora)")
    ver.write_text(t, encoding="utf-8")
    anotar(f"core/version.py: {VERSION_NUEVA} con su entrada de bitácora")

    paq = shape / "package.json"
    t = paq.read_text(encoding="utf-8")
    n = t.count(VERSION_VIEJA)
    if n != 3:
        raise RuntimeError(f"package.json: {VERSION_VIEJA} aparece {n} veces, esperaba 3")
    paq.write_text(t.replace(VERSION_VIEJA, VERSION_NUEVA), encoding="utf-8")
    anotar(f"package.json: los 3 sitios dicen {VERSION_NUEVA}")

    # 4 · el Python empotrado sale de la release más nueva
    flujo = shape / ".github" / "workflows" / "armar-y-publicar.yml"
    t = flujo.read_text(encoding="utf-8")
    if FUENTE_NUEVA in t:
        anotar("el flujo ya heredaba de la 0.12.0: no se toca")
    else:
        flujo.write_text(cambiar(t, FUENTE_VIEJA, FUENTE_NUEVA, "flujo (fuente)"),
                         encoding="utf-8")
        anotar("armar-y-publicar.yml: el Python empotrado se hereda de la 0.12.0")

    # 5 · que nada de esto esté roto antes de gastar 45 minutos
    correr(["node", "--check", str(ven)])
    anotar("ui/ventanas.js: JavaScript válido (node --check)")
    ast.parse(pru.read_text(encoding="utf-8"))
    anotar("pruebas/t007_dibujo.py: Python válido")
    correr([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
    import yaml
    assert yaml.safe_load(flujo.read_text(encoding="utf-8"))["jobs"]
    anotar("armar-y-publicar.yml: YAML válido")
    puesta = correr([sys.executable, "-c",
                     "import sys; sys.path.insert(0, '.'); "
                     "from core.version import VERSION; print(VERSION)"], cwd=shape).strip()
    import json
    dicho = json.loads(paq.read_text(encoding="utf-8"))["version"]
    if not (puesta == dicho == VERSION_NUEVA):
        raise RuntimeError(f"las versiones no coinciden: version.py={puesta} package.json={dicho}")
    anotar(f"version.py y package.json dicen lo mismo: {puesta}")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        "- recado: navegar en otra ventana ya no secuestra el gesto (0.12.1)\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")
    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            "0.12.1: navegar en otra ventana ya no secuestra el gesto\n\n"
            "Mike, sobre la 0.12.0: «cuando uso PAN en otra vista que no está seleccionada,\n"
            "se selecciona la superior de nuevo solita y me mueve esa», «cada vez que uso el\n"
            "click central, me regresa la vista al centro». Los tres fallos que reportó son\n"
            "el mismo, y está en una línea.\n\n"
            "`Ventanas.adoptar()` debe correr una vez: la primera, para convertir la cámara\n"
            "de siempre en la ventana Superior. Para saber si ya había corrido se preguntaba\n"
            "si `estado.vista` era ya la ventana activa. Durante una navegación eso es falso\n"
            "—`estado.vista` apunta a la ventana bajo el cursor—, así que a mitad del\n"
            "arrastre se creía sin estrenar y secuestraba el gesto: activa volvía a la\n"
            "Superior y encuadrarTodas devolvía las cuatro al centro.\n\n"
            "Ahora lleva su propia bandera. Una bandera de «ya pasó» no se deduce de un\n"
            "estado que el usuario mueve.\n\n"
            "Va con prueba en el navegador de verdad: sin el arreglo falla en dos\n"
            "comprobaciones, con él pasa.\n\n"
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
    shape = pathlib.Path("/tmp/recado33/shape101")
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
