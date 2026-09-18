"""El mandadero · recado 24: 0.9.0 — las cuatro ventanas.

Decisión de Mike (17-sep): como Rhino, cuatro ventanas 2×2 —superior, frontal,
lateral y perspectiva— con cámara fija cada una; clic activa, doble clic en el
título maximiza. `ui/ventanas.js` ya está en `main`, probado con node; aquí se
engancha al lienzo con cuatro parches:

1. **Las dos conversiones** suman y restan el origen de la ventana activa. Cada
   cámara trae `ox`, `oy`; en la de siempre valen cero y nada cambia.
2. **El zoom con la rueda** también: el cursor llega en coordenadas del lienzo,
   y la ventana empieza donde empieza.
3. **El pintado** recorre las cuatro, cada una recortada, con su título y el
   borde de la activa. La primera vez adopta la cámara de siempre como ventana
   superior y encuadra las otras tres a lo que hay.
4. **El ratón**: clic en una ventana la activa; doble clic en su título la
   maximiza o la devuelve.

En 0.9.0 se dibuja sobre XY en las cuatro: en la frontal y la lateral el plano
se ve de canto. El plano por ventana es el paso siguiente, porque cada línea
del dibujo tiene que saber en qué plano vive, y eso toca el documento.
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
RAMA = "claude/cuatro-ventanas"
VERSION = "0.9.0"
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


PINTAR_VIEJO = """  if (estado.modo !== "papel" && typeof Visor !== "undefined") {
    return Visor.pintarPlano(c, {
      ancho: lienzo.clientWidth, alto: lienzo.clientHeight, fondo,
      lienzoColor: T.lienzo, oscuro, escala: estado.vista.escala, trazos: estado.trazos,
      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,
      rx: estado.vista.rx || 0, rz: estado.vista.rz || 0,
      colorDe: (hex) => colorDeTrazo(hex, oscuro),
    });
  }"""

PINTAR_NUEVO = """  if (estado.modo !== "papel" && typeof Visor !== "undefined" && typeof Ventanas !== "undefined") {
    // Las cuatro ventanas, cada una con su cámara y recortada a su sitio. La
    // primera vez, la cámara de siempre pasa a ser la ventana superior y las
    // otras tres se encuadran a lo que hay.
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    Ventanas.repartir(w, h);
    Ventanas.adoptar(puntosDelDibujo());
    if (fondo) { c.clearRect(0, 0, w, h); c.fillStyle = T.lienzo; c.fillRect(0, 0, w, h); }
    Ventanas.pintarTodas(c, (cc, v) => Visor.pintarPlano(cc, {
      ancho: v.w, alto: v.h, fondo: false, lienzoColor: T.lienzo, oscuro,
      escala: v.escala, trazos: estado.trazos,
      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,
      rx: v.rx || 0, rz: v.rz || 0,
      colorDe: (hex) => colorDeTrazo(hex, oscuro),
    }), oscuro);
    return;
  }"""

PUNTOS = """/** Las cuatro esquinas de lo que hay dibujado, en el plano de trabajo. Es lo
 *  que se le da a las ventanas para que se encuadren solas. */
function puntosDelDibujo() {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const t of estado.trazos || []) for (const p of (t.puntos || [])) {
    if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
    if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
  }
  if (!isFinite(x0)) return [];
  return [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]];
}

function dibujarPlano(c, fondo = true) {"""

RATON = """lienzo.addEventListener("mousedown", (e) => {
  // Cuatro ventanas: clic en una la activa; doble clic en su título la
  // maximiza o la devuelve. Se decide antes que nada, porque todo lo demás
  // trabaja sobre la ventana activa.
  if (typeof Ventanas !== "undefined") {
    const cajaV = lienzo.getBoundingClientRect();
    const vx0 = e.clientX - cajaV.left, vy0 = e.clientY - cajaV.top;
    const t = Ventanas.enTitulo(vx0, vy0);
    if (t >= 0) {
      if (e.detail >= 2) Ventanas.maximizar(t); else Ventanas.activar(t);
      invalidarPlano(); pintar(); e.preventDefault(); return;
    }
    const i = Ventanas.bajo(vx0, vy0);
    if (i >= 0 && i !== Ventanas.activa) { Ventanas.activar(i); invalidarPlano(); pintar(); }
  }
  // Botón derecho: la rueda si se arrastra, Enter si se suelta sin mover."""

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Cuatro ventanas, como Rhino: superior, perspectiva, frontal y lateral, cada una "
            "con su cámara. Clic en una la activa; doble clic en su título la maximiza y otro "
            "doble clic la devuelve. Todo —dibujar, zoom, pan, orbitar— trabaja sobre la "
            "ventana activa, que se ve con el borde marcado.",
            "Al abrir, la ventana superior conserva lo que estabas mirando y las otras tres se "
            "encuadran solas a lo que hay.",
            "Todavía se dibuja sobre el suelo (XY) en las cuatro: en la frontal y la lateral "
            "el plano se ve de canto. Dibujar sobre el plano de cada ventana es el paso "
            "siguiente. La perspectiva de la cuarta ventana es aún isométrica.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado24")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    vista = shape / "ui" / "vista.js"
    # 1 · las conversiones con el origen de la ventana
    parchar(vista, [
        ("  if (!v.rx && !v.rz) return [(x - v.x) * v.escala, (v.y - y) * v.escala];",
         "  if (!v.rx && !v.rz) return [(x - v.x) * v.escala + (v.ox || 0), (v.y - y) * v.escala + (v.oy || 0)];"),
        ("  return [(ux - v.x) * v.escala, (v.y - vy) * v.escala];",
         "  return [(ux - v.x) * v.escala + (v.ox || 0), (v.y - vy) * v.escala + (v.oy || 0)];"),
        ("  if (!v.rx && !v.rz) return [px / v.escala + v.x, v.y - py / v.escala];",
         "  if (!v.rx && !v.rz) return [(px - (v.ox || 0)) / v.escala + v.x, v.y - (py - (v.oy || 0)) / v.escala];"),
        ("  const ux = px / v.escala + v.x;\n  const vy = v.y - py / v.escala;",
         "  const ux = (px - (v.ox || 0)) / v.escala + v.x;\n  const vy = v.y - (py - (v.oy || 0)) / v.escala;"),
    ], "(v.ox || 0)", "ui/vista.js (conversiones con el origen de la ventana)")
    # 2 · el zoom con la rueda
    parchar(vista, [
        ("  const ux = px / v.escala + v.x, vy = v.y - py / v.escala;\n"
         "  v.escala = Math.min(500, Math.max(0.002, v.escala * factor));\n"
         "  v.x = ux - px / v.escala;                            // el punto bajo el cursor\n"
         "  v.y = vy + py / v.escala;                            // se queda quieto",
         "  const ox = v.ox || 0, oy = v.oy || 0;                // la ventana empieza donde empieza\n"
         "  const ux = (px - ox) / v.escala + v.x, vy = v.y - (py - oy) / v.escala;\n"
         "  v.escala = Math.min(500, Math.max(0.002, v.escala * factor));\n"
         "  v.x = ux - (px - ox) / v.escala;                     // el punto bajo el cursor\n"
         "  v.y = vy + (py - oy) / v.escala;                     // se queda quieto"),
    ], "la ventana empieza donde empieza", "ui/vista.js (zoom con el origen de la ventana)")
    # 3 · el pintado recorre las cuatro
    parchar(vista, [
        (PINTAR_VIEJO, PINTAR_NUEVO),
        ("function dibujarPlano(c, fondo = true) {", PUNTOS),
    ], "Ventanas.pintarTodas", "ui/vista.js (pintar las cuatro)")
    # 4 · el ratón activa y maximiza
    parchar(vista, [
        ('lienzo.addEventListener("mousedown", (e) => {\n  // Botón derecho: la rueda si se arrastra, Enter si se suelta sin mover.', RATON),
    ], "Ventanas.enTitulo", "ui/vista.js (clic activa, doble clic maximiza)")

    parchar(shape / "ui" / "index.html", [
        ('<script src="visor.js"></script>', '<script src="visor.js"></script>\n<script src="ventanas.js"></script>'),
    ], "ventanas.js", "ui/index.html (carga las ventanas)")

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

    for js in ("vista.js", "ventanas.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("vista.js y ventanas.js pasan node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, las cuatro ventanas\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: las cuatro ventanas\n\n"
            "Como Rhino: superior, perspectiva, frontal y lateral, cada una con su cámara.\n"
            "La ventana activa ES estado.vista, así que dibujar, zoom, pan y orbitar siguen\n"
            "funcionando sobre la activa sin enterarse de que hay tres más. Las dos\n"
            "conversiones y el zoom suman y restan el origen de la ventana; en la de siempre\n"
            "valen cero.\n\n"
            "Todavía se dibuja sobre XY en las cuatro: el plano por ventana es el paso\n"
            "siguiente, porque toca el documento."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado24/shape101")
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
