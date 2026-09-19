"""El mandadero · recado 28: 0.12.0 — lo que Mike vio en la 0.11.0.

Segundo intento: el primero se detuvo en `node --check` por un acento grave de
más en la llave del plano, y no empujó nada. La comprobación hizo su trabajo.

1. **La selección se dibujaba mal en las cuatro ventanas.** `seleccion.js` proyecta
   a mano en planta —`(x − vx)·escala`—, sin cámara ni plano, y además guarda
   una foto por vista que no sabe de las cuatro ventanas. Ahora pasa por `aPX` y
   por el plano de cada entidad, y con cuatro ventanas nunca usa la foto.
2. **Pan, zoom y órbita no se veían en tiempo real.** La llave que decide si
   redibujar el plano sólo miraba la cámara activa, y navegar va en la ventana
   bajo el cursor. Ahora la llave mira las cuatro. Y la foto que el lienzo
   reusa durante un gesto —válida con una sola vista— se apaga con cuatro.
3. **La Superior se giraba.** ORBITAR, ISO y compañía actuaban sobre la
   ventana activa. Ahora las ortogonales están clavadas: girar siempre va a la
   Perspectiva, esté activa o no.
4. **La perspectiva se estiraba al alejar.** La fuerza de la perspectiva
   estaba en milímetros, y al alejarse los milímetros en pantalla se multiplican.
   Ahora va en píxeles (foco 1400 px): igual de conservadora a cualquier zoom.
5. **La rueda 3D con Shift + clic derecho**, no Alt.
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
RAMA = "claude/seleccion-en-las-cuatro"
VERSION = "0.12.0"
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


BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "La selección se ve bien en las cuatro ventanas, cada una desde su ángulo y en el "
            "plano de cada línea. En 0.11.0 se proyectaba siempre en planta y salía mal.",
            "Pan, zoom y órbita se ven en tiempo real en la ventana bajo el cursor.",
            "Las tres ventanas ortogonales están clavadas en su vista: ORBITAR, ISO y las demás "
            "giran siempre la Perspectiva, esté activa o no.",
            "La perspectiva ya no se estira al alejar: su fuerza va en píxeles, no en "
            "milímetros, y es la misma a cualquier zoom.",
            "La rueda 3D sale con Shift + clic derecho sostenido (antes era Alt).",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado28")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 · la selección por cámara y por plano
    parchar(shape / "ui" / "seleccion.js", [
        ("    if (estado.sel.size < UMBRAL_FOTO_SEL) { _pintarSeleccionDirecto(ctx); return; }",
         "    // Con cuatro ventanas nunca se usa la foto: se pinta directo en cada una.\n"
         "    if (estado.sel.size < UMBRAL_FOTO_SEL || typeof Ventanas !== \"undefined\") { _pintarSeleccionDirecto(ctx); return; }"),
        ("    const seVe = (c) => c && !(c[2] < mx0 || c[0] > mx1 || c[3] < my0 || c[1] > my1);",
         "    // Girada, o en un plano que no es el suelo, la ventana en planta no dice\n"
         "    // qué se ve: se pinta todo. Y cada entidad va por su plano, con la cámara.\n"
         "    const girada = !!(estado.vista.rx || estado.vista.rz) || (estado.vista.plano && estado.vista.plano !== \"XY\");\n"
         "    const planoDe = (id) => { const tt = estado.trazos.find((x) => x.id === id); return (tt && tt.plano) || \"XY\"; };\n"
         "    const seVe = (c) => girada || (c && !(c[2] < mx0 || c[0] > mx1 || c[3] < my0 || c[1] > my1));"),
        ("          const px = (pts[i][0] - vx) * esc, py = (vy - pts[i][1]) * esc;",
         "          const mp = Planos.aMundo(t.plano || \"XY\", pts[i][0], pts[i][1], 0);\n"
         "          const qp = aPX(mp[0], mp[1], mp[2]);\n"
         "          const px = qp[0], py = qp[1];"),
        ("          const px = (q[0] - vx) * esc, py = (vy - q[1]) * esc;",
         "          const mg = Planos.aMundo(planoDe(id), q[0], q[1], 0);\n"
         "          const qg = aPX(mg[0], mg[1], mg[2]);\n"
         "          const px = qg[0], py = qg[1];"),
    ], "planoDe(id)", "ui/seleccion.js (selección por cámara y por plano)")

    vista = shape / "ui" / "vista.js"
    # 2 · la llave del plano mira las cuatro; la foto se apaga con cuatro ventanas
    parchar(vista, [
        ("function llavePlano() {\n  const v = estado.vista;\n  return `",
         "function llavePlano() {\n  const v = estado.vista;\n"
         "  // Las cuatro cámaras, no sólo la activa: navegar va en la ventana bajo el\n"
         "  // cursor, y si su cámara cambia el plano tiene que redibujarse.\n"
         "  const todas = typeof Ventanas !== \"undefined\"\n"
         "    ? Ventanas.ventanas.map((q) => `${q.x}|${q.y}|${q.escala}|${q.rx}|${q.rz}|${q.ox}|${q.oy}|${q.w}|${q.h}`).join(\";\") : \"\";\n"
         "  return `${todas}#"),
    ], "const todas = typeof Ventanas", "ui/vista.js (la llave mira las cuatro)")
    parchar(vista, [
        ("    if (!enGesto || !foto || !fotoVista) return false;",
         "    // Con cuatro ventanas la foto corrida ya no dice la verdad: mover una\n"
         "    // ventana no mueve las otras. Se redibuja siempre.\n"
         "    if (typeof Ventanas !== \"undefined\") return false;\n"
         "    if (!enGesto || !foto || !fotoVista) return false;"),
    ], "la foto corrida ya no dice la verdad", "ui/vista.js (sin foto con cuatro ventanas)")
    # 4 · la perspectiva en píxeles
    parchar(vista, [
        ("    const k = 1 / Math.max(0.1, 1 - prof / (v.dist || 4000));",
         "    // El foco va en píxeles: así la perspectiva es igual de conservadora a\n"
         "    // cualquier zoom. En milímetros se estiraba al alejarse.\n"
         "    const k = 1 / Math.max(0.1, 1 - prof * v.escala / (v.foco || 1400));"),
        ("    const t = (Math.sin(v.rx) / cx) / (v.dist || 4000);",
         "    const t = (Math.sin(v.rx) / cx) * v.escala / (v.foco || 1400);"),
    ], "(v.foco || 1400)", "ui/vista.js (perspectiva en píxeles)")
    parchar(shape / "ui" / "ventanas.js", [
        ("persp: true, dist: 4000", "persp: true, foco: 1400"),
    ], "foco: 1400", "ui/ventanas.js (foco en píxeles)")

    # 3 · las ortogonales, clavadas: girar siempre va a la Perspectiva
    parchar(shape / "ui" / "camara.js", [
        ("  function poner(rx, rz, pivote) {\n    const el = lienzo();\n    const v = estado.vista;",
         "  /** Girar siempre va a la Perspectiva, esté activa o no: las tres ortogonales\n"
         "   *  están clavadas en su vista. Mike: «la Superior debe quedarse locked». */\n"
         "  function destino() {\n"
         "    if (estado.vista.persp) return estado.vista;\n"
         "    if (typeof Ventanas !== \"undefined\") { const p = Ventanas.ventanas.find((x) => x.persp); if (p) return p; }\n"
         "    return estado.vista;\n"
         "  }\n\n"
         "  function poner(rx, rz, pivote) {\n    const el = lienzo();\n"
         "    const guardadaVista = estado.vista;\n"
         "    const v = destino();\n"
         "    estado.vista = v;                       // aPX y aMM miran estado.vista"),
        ("      v.x += (q[0] - antes[0]) / v.escala;\n      v.y += (antes[1] - q[1]) / v.escala;\n    }\n    repintar();\n  }",
         "      v.x += (q[0] - antes[0]) / v.escala;\n      v.y += (antes[1] - q[1]) / v.escala;\n    }\n"
         "    estado.vista = guardadaVista;\n    repintar();\n  }"),
    ], "function destino()", "ui/camara.js (girar va a la Perspectiva)")

    # 5 · la rueda 3D con Shift
    parchar(shape / "ui" / "radial.js", [
        ("inicio = { x: e.clientX, y: e.clientY, t: performance.now(), alt: e.altKey };",
         "inicio = { x: e.clientX, y: e.clientY, t: performance.now(), alt: e.shiftKey };   // Shift, no Alt (Mike, 18-sep)"),
    ], "alt: e.shiftKey", "ui/radial.js (rueda 3D con Shift)")

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

    for js in ("vista.js", "seleccion.js", "camara.js", "ventanas.js", "radial.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los cinco archivos pasan node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, lo que Mike vio en la 0.11.0\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: la selección en las cuatro, navegar en vivo, ortogonales clavadas\n\n"
            "La selección proyectaba a mano en planta, sin cámara ni plano, y guardaba una\n"
            "foto por vista: con cuatro ventanas salía mal en todas. Ahora va por aPX y por\n"
            "el plano de cada entidad, sin foto. La llave del plano mira las cuatro cámaras,\n"
            "y la foto que el lienzo reusa durante un gesto se apaga con cuatro ventanas.\n\n"
            "Girar siempre va a la Perspectiva; las ortogonales quedan clavadas. La fuerza\n"
            "de la perspectiva va en píxeles para no estirarse al alejar. La rueda 3D sale\n"
            "con Shift + clic derecho."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado28/shape101")
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
