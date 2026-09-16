"""El mandadero · recado 15: la 0.5.0 — el sugeridor y el 3D a la mano.

Seis enganches en cuatro archivos grandes. Todo lo nuevo ya está escrito y
subido (`ui/sugeridor.js`, `ui/tresd-comandos.js`); aquí sólo se conecta.

1. **La pantalla carga** el sugeridor y los comandos nuevos del 3D.
2. **Las flechas** le preguntan al sugeridor antes de mover el historial. Con la
   caja vacía siguen siendo el historial, como siempre; con algo tecleado
   eligen entre las sugerencias. De paso deja de borrarse lo escrito al apretar
   la flecha.
3. **La barra** gana un bloque «3D»: Extruir, Ver 3D, Jalar, STEP, STL. Hasta
   ahora el 3D sólo existía tecleado, o sea que estaba escondido. Mike lo dijo
   claro: los comandos tecleados son auxiliares; lo que manda es el icono y la
   rueda.
4. **La rueda 3D con Alt + clic derecho**, idea de Mike. La rueda de 2D no
   cambia ni un ángulo: se anota si venía Alt en el momento de apretar y se
   elige la rueda al abrir. Como el gesto es el mismo, funciona igual estando
   en el dibujo o en la vista 3D.
5. **`tresd.js` expone** lo que los comandos nuevos necesitan.
6. **0.5.0** en los dos sitios que tienen que coincidir.

Sobre los finales de línea: los archivos de `ui/` traen CRLF y los de `core/`
LF. Cada inserción usa el final de línea del archivo que toca. Meter el
equivocado marca el archivo entero como cambiado y deja ilegible cualquier
comparación futura con draw101.
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
RAMA = "claude/el-3d-a-la-mano"
VERSION = "0.5.0"
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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo, 1)


def fin_de_linea(texto: str) -> str:
    return "\r\n" if "\r\n" in texto else "\n"


RUEDA_3D = '''  /* --- La rueda del 3D  ·  Alt + clic derecho -------------------------------
   * Idea de Mike (16-sep): en vez de meterle un noveno gajo a la rueda de
   * siempre —que le movería el ángulo a los ocho que ya tiene aprendidos con
   * la mano—, el 3D tiene la suya. Mismo gesto, con Alt.
   *
   * Funciona igual estando en el dibujo o en la vista 3D: no hay que entrar al
   * 3D para levantar un contorno. */
  const RUEDA_3D = [
    { et: "Extruir",  icono: "⬒",  cmd: "EXTRUIR" },
    { et: "Ver 3D",   icono: "◳",  cmd: "3D" },
    { et: "Jalar",    icono: "↕",  cmd: "JALAR" },
    { et: "Sacar",    icono: "⇪",  hijos: [
        { et: "STEP", icono: "S",  cmd: "STEP" },
        { et: "STL",  icono: "▲",  cmd: "STL" },
      ] },
  ];

  // Cuál de las dos ruedas está abierta. La elige `abrir` según el Alt.
  let rueda = RUEDA;

'''

BLOQUE_3D = '''    <div class="bloque" data-et="3D">
      <div class="titulo">3D</div>
      <div class="celdas">
        <button data-cmd="EXTRUIR" title="Levantar el contorno seleccionado (EXTRUIR)">⬒</button>
        <button data-cmd="3D" title="Ver las piezas en 3D · Escape vuelve al dibujo">◳</button>
        <button data-cmd="JALAR" title="Mover la cara señalada una medida (JALAR)">↕</button>
        <button data-cmd="STEP" title="Sacar la pieza en STEP, para otro CAD">S</button>
        <button data-cmd="STL" title="Sacar la pieza en STL, para imprimir">▲</button>
      </div>
    </div>
'''

FLECHAS_VIEJO = '        if (!historial.length) return;'
FLECHAS_NUEVO = ('        // El sugeridor tiene preferencia: si hay algo tecleado y hay lista, las'
                 '\n        // flechas eligen entre las sugerencias. Con la caja vacía no hay lista y'
                 '\n        // esto devuelve false, así que el historial sigue siendo el de siempre.'
                 '\n        if (typeof Sugeridor !== "undefined" &&'
                 '\n            Sugeridor.mover(e.key === "ArrowUp" ? -1 : 1)) return;'
                 '\n        if (!historial.length) return;')

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Sugeridor de comandos: al teclear sale la lista de los que empiezan así, con sus "
            "atajos y para qué sirven. Las flechas eligen y Enter corre. Con la caja vacía las "
            "flechas siguen siendo el historial, como siempre.",
            "El 3D ya no está escondido en la consola: tiene su bloque en la barra de "
            "herramientas —Extruir, Ver 3D, Jalar, STEP, STL— y su propia rueda con "
            "**Alt + clic derecho sostenido**. La rueda de siempre no cambió ni un ángulo.",
            "JALAR mueve la cara señalada una medida exacta. Arrastrar da la sensación; "
            "teclear da el milímetro, y en un taller hacen falta los dos.",
            "STEP y STL sacan la pieza desde la barra o la rueda, sin teclear.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado15")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 y 3 · la pantalla: los dos archivos nuevos y el bloque de la barra
    idx = shape / "ui" / "index.html"
    t = idx.read_text(encoding="utf-8")
    fin = fin_de_linea(t)
    if "sugeridor.js" not in t:
        ancla = '<script src="tresd.js"></script>'
        t = cambiar(t, ancla, ancla + fin + '<script src="sugeridor.js"></script>'
                    + fin + '<script src="tresd-comandos.js"></script>', "index.html (scripts)")
        anotar("ui/index.html: carga sugeridor.js y tresd-comandos.js")
    else:
        anotar("ui/index.html ya los cargaba")
    if 'data-et="3D"' not in t:
        ancla = '    <div class="bloque" data-et="ANOTACIONES">'
        t = cambiar(t, ancla, BLOQUE_3D.replace("\n", fin) + ancla, "index.html (barra)")
        anotar("ui/index.html: bloque «3D» en la barra de herramientas")
    else:
        anotar("ui/index.html ya tenía el bloque 3D")
    idx.write_text(t, encoding="utf-8", newline="")

    # 2 · las flechas
    cmds = shape / "ui" / "comandos.js"
    t = cmds.read_text(encoding="utf-8")
    if "Sugeridor.mover" in t:
        anotar("ui/comandos.js ya preguntaba al sugeridor")
    else:
        fin = fin_de_linea(t)
        cmds.write_text(cambiar(t, FLECHAS_VIEJO, FLECHAS_NUEVO.replace("\n", fin),
                                "comandos.js (flechas)"), encoding="utf-8", newline="")
        anotar("ui/comandos.js: las flechas preguntan al sugeridor antes que al historial")

    # 4 · la rueda del 3D
    rad = shape / "ui" / "radial.js"
    t = rad.read_text(encoding="utf-8")
    if "RUEDA_3D" in t:
        anotar("ui/radial.js ya tenía la rueda 3D")
    else:
        fin = fin_de_linea(t)
        t = cambiar(t, "  function abrir(cx, cy) {",
                    RUEDA_3D.replace("\n", fin) + "  function abrir(cx, cy) {" + fin
                    + "    rueda = (inicio && inicio.alt) ? RUEDA_3D : RUEDA;", "radial.js (abrir)")
        t = cambiar(t, "inicio = { x: e.clientX, y: e.clientY, t: performance.now() };",
                    "inicio = { x: e.clientX, y: e.clientY, t: performance.now(), alt: e.altKey };",
                    "radial.js (abajo)")
        # Las ocho veces que se usa la lista pasan a usar la que esté abierta.
        for viejo, nuevo, donde in (
            ("const gajos = RUEDA.map((item, i) => {", "const gajos = rueda.map((item, i) => {", "gajos"),
            ("const a = angDe(i, RUEDA.length);", "const a = angDe(i, rueda.length);", "ángulo"),
            ("const item = RUEDA[i];", "const item = rueda[i];", "hijos"),
            ("const angPadre = -90 + i * (360 / RUEDA.length);", "const angPadre = -90 + i * (360 / rueda.length);", "ángulo del padre"),
            ("gajoBajo(x - abierto.cx, y - abierto.cy, RUEDA.length)", "gajoBajo(x - abierto.cx, y - abierto.cy, rueda.length)", "gajo bajo el cursor"),
            ("if (i >= 0 && RUEDA[i].hijos", "if (i >= 0 && rueda[i].hijos", "abrir hijos"),
            ("RUEDA[s.padre].hijos[s.elegido]", "rueda[s.padre].hijos[s.elegido]", "hijo elegido"),
            ("abierto.elegido >= 0 ? RUEDA[abierto.elegido]", "abierto.elegido >= 0 ? rueda[abierto.elegido]", "gajo elegido"),
        ):
            t = cambiar(t, viejo, nuevo, f"radial.js ({donde})")
        t = cambiar(t, "return { abajo, arrastre, arriba, cancelar, RUEDA,",
                    "return { abajo, arrastre, arriba, cancelar, RUEDA, RUEDA_3D,", "radial.js (salida)")
        rad.write_text(t, encoding="utf-8", newline="")
        anotar("ui/radial.js: rueda 3D con Alt + clic derecho; la de 2D no cambia ni un ángulo")

    # 5 · lo que tresd.js tiene que prestar
    js = shape / "ui" / "tresd.js"
    t = js.read_text(encoding="utf-8")
    if "primerCuerpo" in t:
        anotar("ui/tresd.js ya prestaba lo necesario")
    else:
        js.write_text(cambiar(
            t, "return { abrir, cerrar, pintar, traer, activo: () => activo, cuerpos };",
            "return { abrir, cerrar, pintar, traer, jalar, cuerpos,\n"
            "           activo: () => activo,\n"
            "           senalada: () => senalada,\n"
            "           primerCuerpo: () => [...cuerpos.keys()][0] || null };",
            "tresd.js (salida)"), encoding="utf-8", newline="")
        anotar("ui/tresd.js: presta jalar, la cara señalada y la primera pieza")

    # 6 · la versión
    hoy = dt.date.today().isoformat()
    ver = shape / "core" / "version.py"
    t = ver.read_text(encoding="utf-8")
    actual = re.search(r'VERSION = "([^"]+)"', t).group(1)
    t = cambiar(t, f'VERSION = "{actual}"', f'VERSION = "{VERSION}"', "version.py")
    t = re.sub(r'FECHA = "[^"]+"', f'FECHA = "{hoy}"', t, count=1)
    ver.write_text(cambiar(t, "BITACORA: list[dict] = [\n", BITACORA % (VERSION, hoy),
                           "version.py (bitácora)"), encoding="utf-8")
    paq = shape / "package.json"
    t = paq.read_text(encoding="utf-8")
    t = cambiar(t, f'"version": "{actual}"', f'"version": "{VERSION}"', "package.json")
    t = cambiar(t, f'"_versionApp": "{actual} —', f'"_versionApp": "{VERSION} —', "package.json")
    paq.write_text(cambiar(t, f'"artifactName": "shape101-{actual}-setup.${{ext}}"',
                           f'"artifactName": "shape101-{VERSION}-setup.${{ext}}"',
                           "package.json"), encoding="utf-8")
    anotar(f"versión {actual} → {VERSION} en core/version.py y package.json")

    # Comprobar lo que se puede sin pantalla
    for archivo, debe in ((idx, "tresd-comandos.js"), (idx, 'data-et="3D"'),
                          (cmds, "Sugeridor.mover"), (rad, "RUEDA_3D"), (js, "primerCuerpo")):
        if debe not in archivo.read_text(encoding="utf-8"):
            raise RuntimeError(f"{archivo.name} no quedó con {debe}")
    if "RUEDA[" in rad.read_text(encoding="utf-8"):
        raise RuntimeError("radial.js todavía usa RUEDA[ directo en algún sitio")
    anotar("los cinco enganches están puestos y radial.js ya no usa la lista fija")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, el sugeridor y el 3D a la mano\n\n```\n"
        + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: el sugeridor de comandos y el 3D a la mano\n\n"
            "El 3D sólo existía tecleado, o sea que estaba escondido. Mike lo dijo claro: los\n"
            "comandos tecleados son auxiliares; lo que manda es el icono y la rueda. Ahora\n"
            "tiene su bloque en la barra y su propia rueda con Alt + clic derecho sostenido,\n"
            "idea suya para no meterle un noveno gajo a la rueda de siempre, que le movería\n"
            "el ángulo a los ocho que ya tiene aprendidos con la mano.\n\n"
            "El sugeridor enseña los comandos que empiezan como lo tecleado, encabezados por\n"
            "el que Enter correría ahora mismo. Las flechas ya tenían dueño —el historial—,\n"
            "así que se reparten por lo que hay escrito."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado15/shape101")
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
