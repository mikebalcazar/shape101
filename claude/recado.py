"""El mandadero · recado 16: la 0.6.0 — un solo espacio.

Todo lo nuevo ya está en `main` (`cuerpos.js`, `camara.js`, el `tresd.js`
nuevo, la cámara dentro de `vista.js`). Aquí sólo se conecta:

1. El ratón de `vista.js` cede el clic al 3D cuando cae sobre una cara, y sólo
   entonces. Va **después** del pan: con el espacio apretado, arrastrar sobre
   una pieza sigue siendo mover la vista.
2. El fantasma se pinta en la capa de encima, cada cuadro.
3. El motor dice qué piezas tiene el dibujo (`/api/cuerpo/lista`).
4. La pantalla carga los dos archivos nuevos; el bloque 3D y la rueda 3D ganan
   Orbitar, Planta e Iso.
5. El sugeridor se achica: cinco filas, letra chica, angosto. Mike: «estorba
   muchísimo».
6. 0.6.0.

Cada reemplazo comprueba que el texto viejo aparezca exactamente una vez y
respeta el final de línea del archivo (los de `ui/` traen CRLF).
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
RAMA = "claude/un-solo-espacio"
VERSION = "0.6.0"
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


def cambiar(texto: str, viejo: str, nuevo: str, donde: str) -> str:
    fin = fin_de(texto)
    viejo, nuevo = viejo.replace("\n", fin), nuevo.replace("\n", fin)
    n = texto.count(viejo)
    if n != 1:
        raise RuntimeError(f"{donde}: «{viejo[:60]}…» aparece {n} veces, esperaba 1")
    return texto.replace(viejo, nuevo, 1)


def parchar(ruta: pathlib.Path, cambios, ya: str, donde: str) -> None:
    t = ruta.read_text(encoding="utf-8")
    if ya in t:
        anotar(f"{donde}: ya estaba, no se toca")
        return
    for viejo, nuevo in cambios:
        t = cambiar(t, viejo, nuevo, donde)
    ruta.write_text(t, encoding="utf-8", newline="")
    anotar(f"{donde}: parchado")


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Un solo espacio. El 3D ya no es un visor pegado encima del dibujo: las piezas "
            "se pintan en el mismo lienzo que las líneas, con la misma cámara, y la pieza se "
            "para sobre el contorno del que salió. La vista de planta es un ángulo de cámara, "
            "no un modo: se dibuja igual que siempre.",
            "ORBITAR gira la vista arrastrando, alrededor de lo que estás mirando. PLANTA, "
            "FRENTE, DERECHA e ISO son las vistas fijas. El comando 3D alterna planta e "
            "isométrica. Todo en la barra y en la rueda 3D (Alt + clic derecho sostenido).",
            "Al jalar una cara ahora ves en tiempo real a dónde va: la cara punteada en su "
            "sitio nuevo, las líneas que la unen al viejo y la medida en milímetros siguiendo "
            "al cursor. Al soltar, la pieza se rehace. Si la cara se ve exactamente de canto, "
            "el programa lo dice en vez de inventar un número.",
            "El sugeridor de comandos es cinco veces más chico: cinco filas, letra chica, "
            "pegado a la caja.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado16")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 y 2 · el ratón y el fantasma, en vista.js
    parchar(shape / "ui" / "vista.js", [
        ("""    lienzo.style.cursor = "grabbing";
    e.preventDefault();
    return;
  }
  if (cajaZoom) {""",
         """    lienzo.style.cursor = "grabbing";
    e.preventDefault();
    return;
  }
  // El 3D después del pan y antes de todo lo demás: si el clic cayó sobre la
  // cara de una pieza, es del 3D. Si no, sigue como siempre.
  if (typeof TresD !== "undefined" && TresD.abajo(e)) { e.preventDefault(); return; }
  if (cajaZoom) {"""),
        ('lienzo.addEventListener("mousemove", (e) => {',
         'lienzo.addEventListener("mousemove", (e) => {\n  if (typeof TresD !== "undefined" && TresD.mover(e)) return;'),
        ('lienzo.addEventListener("mouseup", (e) => {',
         'lienzo.addEventListener("mouseup", (e) => {\n  if (typeof TresD !== "undefined" && TresD.arrastrando()) { TresD.arriba(); return; }'),
        ("function pintarMira(c = ctx) {",
         "function pintarMira(c = ctx) {\n  if (typeof TresD !== \"undefined\") TresD.pintarFantasma(c);"),
    ], "TresD.abajo(e)", "ui/vista.js (ratón y fantasma)")

    # 3 · el motor lista sus piezas
    parchar(shape / "core" / "solido" / "rutas.py", [
        ('@router.get("/{id_}/malla")',
         '@router.get("/lista")\ndef lista():\n    """Los ids de las piezas del dibujo, para que la pantalla sepa qué pintar."""\n'
         '    doc = _doc()\n    return {"ids": [e.id for e in doc.entidades.values() if getattr(e, "tipo", "") == "cuerpo"]}\n\n\n'
         '@router.get("/{id_}/malla")'),
    ], '@router.get("/lista")', "core/solido/rutas.py (lista)")

    # 4 · la pantalla
    parchar(shape / "ui" / "index.html", [
        ('<script src="tresd-comandos.js"></script>',
         '<script src="tresd-comandos.js"></script>\n<script src="cuerpos.js"></script>\n<script src="camara.js"></script>'),
        ('<button data-cmd="STL" title="Sacar la pieza en STL, para imprimir">▲</button>',
         '<button data-cmd="STL" title="Sacar la pieza en STL, para imprimir">▲</button>\n'
         '        <button data-cmd="ORBITAR" title="Girar la vista arrastrando (ORBITAR)">⟳</button>\n'
         '        <button data-cmd="PLANTA" title="Mirar desde arriba, como siempre (PLANTA)">⬓</button>\n'
         '        <button data-cmd="ISO" title="Vista isométrica (ISO)">◈</button>'),
    ], "camara.js", "ui/index.html (scripts y bloque 3D)")
    parchar(shape / "ui" / "radial.js", [
        ('    { et: "Jalar",    icono: "↕",  cmd: "JALAR" },',
         '    { et: "Jalar",    icono: "↕",  cmd: "JALAR" },\n    { et: "Orbitar",  icono: "⟳",  cmd: "ORBITAR" },'),
    ], '"ORBITAR"', "ui/radial.js (rueda 3D)")

    # 5 · el sugeridor, chico
    parchar(shape / "ui" / "sugeridor.js", [
        ("const TOPE = 8;", "const TOPE = 5;"),
        ('borderRadius: "6px", overflow: "hidden", minWidth: "320px",',
         'borderRadius: "4px", overflow: "hidden", minWidth: "220px",'),
        ('boxShadow: "0 8px 24px rgba(0,0,0,0.45)", font: "13px system-ui, sans-serif",',
         'boxShadow: "0 4px 12px rgba(0,0,0,0.4)", font: "11px system-ui, sans-serif",'),
        ('lista.style.width = `${Math.max(320, r.width)}px`;',
         'lista.style.width = `${Math.max(220, Math.min(420, r.width))}px`;'),
        ('padding: "5px 10px", cursor: "pointer", display: "flex", gap: "10px",',
         'padding: "2px 8px", cursor: "pointer", display: "flex", gap: "8px",'),
        ('nom.style.minWidth = "7em";', 'nom.style.minWidth = "6em";'),
        ('ayuda.style.fontSize = "12px";', 'ayuda.style.fontSize = "10px";'),
    ], "const TOPE = 5;", "ui/sugeridor.js (achicado)")

    # 6 · la versión
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

    # Comprobar: que el JS siga siendo JS (node está en el corredor) y que el
    # motor importe con la ruta nueva.
    for js in ("vista.js", "tresd.js", "cuerpos.js", "camara.js", "sugeridor.js", "radial.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los seis archivos de la pantalla pasan node --check")
    salida = correr([sys.executable, "-c",
                     "import ast, pathlib; ast.parse(pathlib.Path('core/solido/rutas.py').read_text(encoding='utf-8'));"
                     "print('rutas.py sigue siendo Python válido')"], cwd=shape)
    anotar(salida.strip())

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, un solo espacio\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: un solo espacio\n\n"
            "El 3D deja de ser un visor pegado encima del dibujo. Las piezas se pintan en el\n"
            "mismo lienzo que las líneas, con la misma cámara, y la vista de planta es un\n"
            "ángulo, no un modo: en cero se dibuja con la misma cuenta de siempre, así que\n"
            "el 2D que ya funciona no cambia ni en el último decimal.\n\n"
            "El ratón cede el clic al 3D sólo cuando cae sobre una cara, y después del pan:\n"
            "con el espacio apretado, arrastrar sobre una pieza sigue moviendo la vista. El\n"
            "fantasma del arrastre se pinta en la capa de encima, cada cuadro.\n\n"
            "El sugeridor se achica a cinco filas y letra chica: Mike dijo que estorbaba\n"
            "muchísimo, y tenía razón."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado16/shape101")
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
