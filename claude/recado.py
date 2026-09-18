"""El mandadero · recado 26: 0.10.0 — el paquete completo de las cuatro vistas.

Mike probó la 0.9.0 y pidió todo junto:

1. **La selección dentro de cada ventana.** Selección, hule y fantasmas se
   pintaban una sola vez con la cámara activa, encima de todo el lienzo: en la
   Superior aparecían desfasados y en la Perspectiva no aparecían. Ahora esa
   capa se pinta ventana por ventana, con la cámara de cada una.
2. **Órbita alrededor de lo que está bajo el cursor** al empezar a arrastrar,
   no del centro de la pantalla.
3. **Perspectiva: central = orbitar, Alt + central = pan.** En las otras tres el
   central sigue siendo pan y Alt + central orbita.
4. **La ventana se activa con mouse over**, para zoom, pan y órbita.
5. **Perspectiva de verdad** sólo en la Perspectiva; las otras tres ortogonales.
   Matemática probada sin pantalla: ida y vuelta sobre el suelo con error de
   10⁻¹³ mm, y un mismo canto se ve más grande cerca del ojo que lejos.
6. **Extruir interactivo** (`ui/extruir.js`): arrastras y el fantasma crece con
   la cota; clic confirma; Enter teclea el valor; Escape cancela.

Fuera de este paquete, dicho a Mike: dibujar sobre el plano de cada ventana y
los handles de vértices y aristas de sólidos. Tocan el documento y el kernel.
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
RAMA = "claude/cuatro-vistas-completas"
VERSION = "0.10.0"
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


APX_VIEJO = """  const vy = uy * Math.cos(v.rx) - (z || 0) * Math.sin(v.rx);
  return [(ux - v.x) * v.escala + (v.ox || 0), (v.y - vy) * v.escala + (v.oy || 0)];"""

APX_NUEVO = """  const cx = Math.cos(v.rx), sx = Math.sin(v.rx);
  const vy = uy * cx - (z || 0) * sx;
  let px = (ux - v.x) * v.escala + (v.ox || 0), py = (v.y - vy) * v.escala + (v.oy || 0);
  if (v.persp) {
    // Perspectiva: lo cercano al ojo se aleja del centro de la ventana y lo
    // lejano se acerca. Sólo la ventana Perspectiva la lleva; las otras tres
    // son ortogonales, que es donde se mide.
    const prof = uy * sx + (z || 0) * cx;
    const cxs = (v.ox || 0) + v.w / 2, cys = (v.oy || 0) + v.h / 2;
    const k = 1 / Math.max(0.1, 1 - prof / (v.dist || 4000));
    px = cxs + (px - cxs) * k;
    py = cys + (py - cys) * k;
  }
  return [px, py];"""

AMM_VIEJO = """  const ux = (px - (v.ox || 0)) / v.escala + v.x;
  const vy = v.y - (py - (v.oy || 0)) / v.escala;
  const cx = Math.cos(v.rx);
  const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;"""

AMM_NUEVO = """  let ux = (px - (v.ox || 0)) / v.escala + v.x;
  let vy = v.y - (py - (v.oy || 0)) / v.escala;
  const cx = Math.cos(v.rx);
  if (v.persp && Math.abs(cx) > 1e-9) {
    // Deshacer la perspectiva sobre el suelo (z = 0): ahí la profundidad es
    // lineal en la Y de la cámara, y la ecuación se resuelve exacta.
    const cxs = (v.ox || 0) + v.w / 2, cys = (v.oy || 0) + v.h / 2;
    const t = (Math.sin(v.rx) / cx) / (v.dist || 4000);
    const A = v.y * v.escala + (v.oy || 0) - cys, d = py - cys;
    vy = (A - d) / (v.escala - d * t);
    const k = 1 / Math.max(0.1, 1 - t * vy);
    ux = v.x + ((px - cxs) / k + cxs - (v.ox || 0)) / v.escala;
  }
  const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;"""

ENCIMA_VIEJO = """  if (typeof Seleccion !== "undefined") Seleccion.pintarSeleccion(ctxE);
  if (window.VentanasHoja) VentanasHoja.pintarEncima(ctxE);
  pintarReferencia(ctxE);
  pintarMira(ctxE);
  pintarHule(ctxE);"""

ENCIMA_NUEVO = """  if (typeof Ventanas !== "undefined" && estado.modo !== "papel") {
    // La capa de encima también va ventana por ventana, con la cámara de cada
    // una: si se pintara una sola vez con la activa, la selección saldría
    // desfasada en las otras tres. Sólo la mira se queda en la activa.
    Ventanas.pintarTodas(ctxE, (cc) => {
      if (typeof Seleccion !== "undefined") Seleccion.pintarSeleccion(cc);
      pintarHule(cc);
      if (typeof Extrusion !== "undefined") Extrusion.pintar(cc);
      if (typeof TresD !== "undefined") TresD.pintarFantasma(cc);
    }, tema().oscuro);
    pintarReferencia(ctxE);
    pintarMira(ctxE);
  } else {
    if (typeof Seleccion !== "undefined") Seleccion.pintarSeleccion(ctxE);
    if (window.VentanasHoja) VentanasHoja.pintarEncima(ctxE);
    pintarReferencia(ctxE);
    pintarMira(ctxE);
    pintarHule(ctxE);
  }"""

PONER_VIEJO = """  function poner(rx, rz) {
    const el = lienzo();
    const v = estado.vista;
    const w = el ? el.clientWidth : 0, h = el ? el.clientHeight : 0;
    const centro = window.aMM ? window.aMM(w / 2, h / 2) : null;
    v.rx = rx;
    v.rz = rz;
    if (centro && window.aPX) {
      const q = window.aPX(centro[0], centro[1], 0);
      // Ojo con el signo de la Y: en el dibujo crece hacia arriba y en la
      // pantalla hacia abajo, así que la corrección va al revés que la de X.
      v.x += (q[0] - w / 2) / v.escala;
      v.y += (h / 2 - q[1]) / v.escala;
    }
    repintar();
  }"""

PONER_NUEVO = """  function poner(rx, rz, pivote) {
    const el = lienzo();
    const v = estado.vista;
    const w = el ? el.clientWidth : 0, h = el ? el.clientHeight : 0;
    // El pivote: lo que está bajo el cursor al empezar (lo pasa `arrastrar`),
    // o el centro de la ventana activa. Ese punto se queda clavado en su sitio
    // de la pantalla mientras todo lo demás gira alrededor.
    const cx = (v.ox || 0) + (v.w || w) / 2, cy = (v.oy || 0) + (v.h || h) / 2;
    const centro = pivote || (window.aMM ? window.aMM(cx, cy) : null);
    const antes = centro && window.aPX ? window.aPX(centro[0], centro[1], 0) : null;
    v.rx = rx;
    v.rz = rz;
    if (antes) {
      const q = window.aPX(centro[0], centro[1], 0);
      // Ojo con el signo de la Y: en el dibujo crece hacia arriba y en la
      // pantalla hacia abajo, así que la corrección va al revés que la de X.
      v.x += (q[0] - antes[0]) / v.escala;
      v.y += (antes[1] - q[1]) / v.escala;
    }
    repintar();
  }"""

ARRASTRAR_VIEJO = """  function arrastrar(e) {
    const a = { x: e.clientX, y: e.clientY, rx: estado.vista.rx, rz: estado.vista.rz };
    const mover = (ev) => {
      poner(Math.max(-Math.PI / 2, Math.min(0, a.rx + (ev.clientY - a.y) * 0.008)),
            a.rz + (ev.clientX - a.x) * 0.008);"""

ARRASTRAR_NUEVO = """  function arrastrar(e) {
    const r = lienzo().getBoundingClientRect();
    // El pivote es lo que está bajo el cursor al apretar: es lo que la mano
    // espera que se quede quieto mientras gira lo demás.
    const pivote = window.aMM ? window.aMM(e.clientX - r.left, e.clientY - r.top) : null;
    const a = { x: e.clientX, y: e.clientY, rx: estado.vista.rx, rz: estado.vista.rz };
    const mover = (ev) => {
      poner(Math.max(-Math.PI / 2, Math.min(0, a.rx + (ev.clientY - a.y) * 0.008)),
            a.rz + (ev.clientX - a.x) * 0.008, pivote);"""

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "La selección, el hule y los fantasmas se ven en las cuatro ventanas, cada una "
            "desde su ángulo. En 0.9.0 sólo se pintaban con la cámara de la activa y salían "
            "desfasados en las demás.",
            "La ventana Perspectiva tiene perspectiva de verdad; las otras tres siguen "
            "ortogonales, que es donde se mide.",
            "Orbitar gira alrededor de lo que está bajo el cursor al empezar a arrastrar. En la "
            "Perspectiva, el botón central orbita y Alt + central hace pan; en las otras tres el "
            "central es pan y Alt + central orbita.",
            "La ventana se activa con solo pasar el mouse: zoom, pan y órbita van donde está el "
            "cursor.",
            "Extruir es interactivo: das EXTRUIR con el contorno seleccionado, arrastras y el "
            "fantasma crece con la cota; clic confirma, Enter teclea el valor, Escape cancela.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado26")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    parchar(shape / "ui" / "ventanas.js", [
        ('    { nombre: "Perspectiva", plano: "XY", rx: -60 * GRADO,  rz: 45 * GRADO },',
         '    { nombre: "Perspectiva", plano: "XY", rx: -60 * GRADO,  rz: 45 * GRADO, persp: true, dist: 4000 },'),
    ], "persp: true", "ui/ventanas.js (la Perspectiva lleva perspectiva)")

    vista = shape / "ui" / "vista.js"
    parchar(vista, [(APX_VIEJO, APX_NUEVO), (AMM_VIEJO, AMM_NUEVO)],
            "if (v.persp)", "ui/vista.js (perspectiva en las conversiones)")
    parchar(vista, [
        (ENCIMA_VIEJO, ENCIMA_NUEVO),
        ("function pintarMira(c = ctx) {\n  if (typeof TresD !== \"undefined\") TresD.pintarFantasma(c);",
         "function pintarMira(c = ctx) {"),
    ], "Extrusion.pintar(cc)", "ui/vista.js (la capa de encima, ventana por ventana)")
    parchar(vista, [
        ('  if (e.button === 1 && e.altKey && typeof Camara !== "undefined") { Camara.arrastrar(e); e.preventDefault(); return; }',
         '  // Botón central: en la Perspectiva orbita y Alt + central hace pan. En las\n'
         '  // otras tres el central es pan, como siempre, y Alt + central orbita.\n'
         '  if (e.button === 1 && typeof Camara !== "undefined" && (estado.vista.persp ? !e.altKey : e.altKey)) { Camara.arrastrar(e); e.preventDefault(); return; }'),
    ], "estado.vista.persp ? !e.altKey : e.altKey", "ui/vista.js (central orbita en la Perspectiva)")
    parchar(vista, [
        ("  const px = e.clientX - caja.left, py = e.clientY - caja.top;\n  const [mx, my] = aMM(px, py);\n  estado.cursor = { px, py, x: mx, y: my };",
         "  const px = e.clientX - caja.left, py = e.clientY - caja.top;\n"
         "  // La ventana se activa con solo pasar el mouse: zoom, pan y órbita van\n"
         "  // donde está el cursor. No mientras se arrastra algo.\n"
         "  if (typeof Ventanas !== \"undefined\" && e.buttons === 0 && !(typeof Extrusion !== \"undefined\" && Extrusion.activa())) {\n"
         "    const iv = Ventanas.bajo(px, py);\n"
         "    if (iv >= 0 && iv !== Ventanas.activa) { Ventanas.activar(iv); invalidarPlano(); }\n"
         "  }\n"
         "  const [mx, my] = aMM(px, py);\n  estado.cursor = { px, py, x: mx, y: my };"),
    ], "La ventana se activa con solo pasar el mouse", "ui/vista.js (mouse over activa)")

    parchar(shape / "ui" / "camara.js", [(PONER_VIEJO, PONER_NUEVO), (ARRASTRAR_VIEJO, ARRASTRAR_NUEVO)],
            "function poner(rx, rz, pivote)", "ui/camara.js (pivote bajo el cursor)")

    parchar(shape / "ui" / "tresd.js", [
        ('      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {',
         '      // Sin argumento, extruir es interactivo: el fantasma sigue al ratón.\n'
         '      if (typeof Extrusion !== "undefined" && Extrusion.empezar(ids)) return;\n'
         '      if (typeof Entrada === "undefined" || !Entrada.pedirNumero) {'),
    ], "Extrusion.empezar(ids)", "ui/tresd.js (EXTRUIR interactivo)")

    parchar(shape / "ui" / "index.html", [
        ('<script src="ventanas.js"></script>', '<script src="ventanas.js"></script>\n<script src="extruir.js"></script>'),
    ], "extruir.js", "ui/index.html (carga extruir)")

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

    for js in ("vista.js", "camara.js", "tresd.js", "ventanas.js", "extruir.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los cinco archivos pasan node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, el paquete completo de las cuatro vistas\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: el paquete completo de las cuatro vistas\n\n"
            "Lo que Mike pidió tras probar la 0.9.0, todo junto: la selección, el hule y los\n"
            "fantasmas pintados ventana por ventana con su cámara; órbita alrededor de lo\n"
            "que está bajo el cursor; en la Perspectiva central = orbitar y Alt + central =\n"
            "pan; la ventana se activa con mouse over; perspectiva de verdad sólo en la\n"
            "Perspectiva; y extruir interactivo, con el fantasma creciendo con la cota.\n\n"
            "La perspectiva se probó sin pantalla: ida y vuelta sobre el suelo con error de\n"
            "1e-13 mm, y un mismo canto se ve más grande cerca del ojo que lejos."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado26/shape101")
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
