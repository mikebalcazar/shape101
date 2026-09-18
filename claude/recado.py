"""El mandadero · recado 20: 0.8.0 — el visor pinta siempre.

Mike, tras probar la 0.7.0 (todo funcionó): «ya no ocupemos un plano 2D, sólo
entorpece el workflow. Dibujemos el 2D directo sobre el suelo del 3D». Y que
orbitar sea Alt + botón central.

Dos pintores para el mismo espacio —el viejo con cachés de planta, el visor sin
ellas, y la app cambiando de uno a otro según el ángulo— era la frontera lenta.
Ahora pinta el visor siempre. El modo **papel** (las hojas de impresión, de
donde sale el PDF) sigue con el viejo: es otro oficio y no tiene 3D.

Para que el visor pueda pintar en planta le faltaban dos cosas del viejo:
la **rejilla** (ahora proyectada: girada se ve en perspectiva, con los ejes
marcados para saber dónde está el cero) y los **textos** (en su punto, con su
altura, ángulo y alineación; girados se pintan de frente a quien mira, para
que se lean). Las dos van aquí como parches al visor, los mismos que se
probaron en la máquina del chat con un lienzo de mentira.
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
RAMA = "claude/el-visor-pinta-siempre"
VERSION = "0.8.0"
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


REJILLA_Y_TEXTOS = '''  /** La rejilla, sobre el plano de trabajo y proyectada: girada se ve en
   *  perspectiva, que es lo que dice dónde está el suelo. El paso se elige
   *  para que las líneas queden a 12 px o más; más juntas son ruido. */
  function dibujarRejilla(c, ctx) {
    if (ctx.rejilla === false) return;
    const { aPX, escala } = ctx;
    const pasos = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
    const paso = pasos.find((p) => p * escala >= 12) || 10000;
    const lim = ctx.extension || { x0: -500, y0: -500, x1: 500, y1: 500 };
    const x0 = Math.floor(lim.x0 / paso) * paso, x1 = Math.ceil(lim.x1 / paso) * paso;
    const y0 = Math.floor(lim.y0 / paso) * paso, y1 = Math.ceil(lim.y1 / paso) * paso;
    if ((x1 - x0) / paso > 400 || (y1 - y0) / paso > 400) return;   // un plano enorme: sin rejilla
    c.save();
    c.lineWidth = 1;
    c.strokeStyle = ctx.oscuro ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.07)";
    c.beginPath();
    for (let x = x0; x <= x1; x += paso) { const a = aPX(x, y0, 0), b = aPX(x, y1, 0); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); }
    for (let y = y0; y <= y1; y += paso) { const a = aPX(x0, y, 0), b = aPX(x1, y, 0); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); }
    c.stroke();
    // Los ejes, un poco más marcados: sin ellos no se sabe dónde está el cero.
    c.strokeStyle = ctx.oscuro ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.2)";
    c.beginPath();
    let a = aPX(x0, 0, 0), b = aPX(x1, 0, 0); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]);
    a = aPX(0, y0, 0); b = aPX(0, y1, 0); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]);
    c.stroke();
    c.restore();
  }

  /** Los textos, como los pintaba el lienzo viejo: en su punto, con su altura,
   *  su ángulo y su alineación. Girada la vista se pintan de frente a quien
   *  mira (no tumbados sobre el plano): se leen, que es para lo que están. */
  function dibujarTextos(c, ctx, textos) {
    const { aPX, colorDe, escala } = ctx;
    const girada = !!(ctx.rx || ctx.rz);
    for (const t of textos) {
      const alturaPX = t.altura * escala;
      const q = aPX(t.p[0], t.p[1], 0);
      c.save();
      c.translate(q[0], q[1]);
      if (t.rotacion && !girada) c.rotate(-t.rotacion * Math.PI / 180);
      c.fillStyle = colorDe(t.color);
      c.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
      c.textAlign = t.alineacion === "CENTRO" ? "center" : t.alineacion === "DER" ? "right" : "left";
      const lineas = String(t.texto).split("\\n");
      for (let i = 0; i < lineas.length; i++) c.fillText(lineas[i], 0, i * alturaPX * 1.25);
      c.restore();
    }
  }

  function dibujarSuelo(c, ctx) {'''

ORBITA_ARRASTRE = '''  /** Orbitar arrastrando desde un botón del ratón, sin entrar en un modo:
   *  Alt + botón central, idea de Mike (17-sep). Se suelta el botón y se
   *  acabó. Lo llama el lienzo desde su propio mousedown. */
  function arrastrar(e) {
    const a = { x: e.clientX, y: e.clientY, rx: estado.vista.rx, rz: estado.vista.rz };
    const mover = (ev) => {
      poner(Math.max(-Math.PI / 2, Math.min(0, a.rx + (ev.clientY - a.y) * 0.008)),
            a.rz + (ev.clientX - a.x) * 0.008);
      ev.preventDefault();
      ev.stopPropagation();
    };
    const soltar = () => {
      window.removeEventListener("mousemove", mover, true);
      window.removeEventListener("mouseup", soltar, true);
    };
    window.addEventListener("mousemove", mover, true);
    window.addEventListener("mouseup", soltar, true);
  }

  return { poner, ver, enPlanta, empezarAOrbitar, terminar, arrastrar, VISTAS };'''

BITACORA = '''BITACORA: list[dict] = [
    {
        "version": "%s",
        "fecha": "%s",
        "cambios": [
            "Ya no hay un plano 2D aparte: el dibujo vive sobre el suelo del 3D y el visor "
            "nuevo pinta siempre, también en planta. Dos pintores para el mismo espacio era lo "
            "que hacía lento girar. Las hojas de impresión siguen como estaban.",
            "Orbitar es Alt + botón central del ratón, arrastrando. ORBITAR sigue existiendo "
            "para quien no tenga botón central.",
            "La rejilla se ve también girada, en perspectiva, con los ejes marcados para "
            "saber dónde está el cero. Los textos vuelven a verse girados, de frente a quien "
            "mira.",
        ],
    },
'''


def main() -> int:
    t_shape = os.environ.get("TOKEN_SHAPE101")
    if not t_shape:
        print("falta TOKEN_SHAPE101")
        return 1
    tmp = pathlib.Path("/tmp/recado20")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shape = tmp / "shape101"
    correr(["git", "clone", "--depth", "1",
            f"https://x-access-token:{t_shape}@github.com/{DUENO}/shape101", str(shape)])
    correr(["git", "config", "user.name", "shape101 (recado)"], cwd=shape)
    correr(["git", "config", "user.email", "mike@forespot.com"], cwd=shape)
    correr(["git", "checkout", "-B", RAMA], cwd=shape)

    # 1 · el visor gana rejilla y textos
    parchar(shape / "ui" / "visor.js", [
        ("""      dibujarSuelo(c, ctx);
      for (const t of ctx.trazos || []) {
        if (t.clase === "imagen") continue;""",
         """      dibujarSuelo(c, ctx);
      dibujarRejilla(c, ctx);
      const textos = [];
      for (const t of ctx.trazos || []) {
        if (t.clase === "imagen") continue;
        if (t.texto !== undefined && t.altura) {
          if (t.altura * escala >= 4) textos.push(t);   // más chico no se lee
          continue;
        }"""),
        ("""      c.setLineDash([]);
      if (typeof Cuerpos !== "undefined") Cuerpos.pintar(c, ctx.oscuro);""",
         """      c.setLineDash([]);
      dibujarTextos(c, ctx, textos);
      if (typeof Cuerpos !== "undefined") Cuerpos.pintar(c, ctx.oscuro);"""),
        ("  function dibujarSuelo(c, ctx) {", REJILLA_Y_TEXTOS),
        ("""    if (!isFinite(x0)) { x0 = -500; y0 = -500; x1 = 500; y1 = 500; }
    const mx = (x1 - x0) * 0.25 + 50, my = (y1 - y0) * 0.25 + 50;""",
         """    if (!isFinite(x0)) { x0 = -500; y0 = -500; x1 = 500; y1 = 500; }
    const mx = (x1 - x0) * 0.25 + 50, my = (y1 - y0) * 0.25 + 50;
    ctx.extension = { x0: x0 - mx, y0: y0 - my, x1: x1 + mx, y1: y1 + my };"""),
    ], "function dibujarRejilla", "ui/visor.js (rejilla y textos)")

    # 2 · el visor pinta siempre (menos en papel), y Alt + central orbita
    vista = shape / "ui" / "vista.js"
    parchar(vista, [
        ('  if ((estado.vista.rx || estado.vista.rz) && typeof Visor !== "undefined") {',
         '  // El visor pinta siempre. Sólo el modo papel —las hojas, de donde sale el\n'
         '  // PDF— se queda con el pintado viejo: es otro oficio y no tiene 3D.\n'
         '  if (estado.modo !== "papel" && typeof Visor !== "undefined") {'),
        ("      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,",
         "      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,\n"
         "      rx: estado.vista.rx || 0, rz: estado.vista.rz || 0,"),
        ("  if (esPan(e)) {",
         "  // Alt + botón central: orbitar. Sin Alt, el central sigue siendo pan.\n"
         "  if (e.button === 1 && e.altKey && typeof Camara !== \"undefined\") { Camara.arrastrar(e); e.preventDefault(); return; }\n"
         "  if (esPan(e)) {"),
    ], "Camara.arrastrar(e)", "ui/vista.js (el visor pinta siempre; Alt + central orbita)")
    parchar(shape / "ui" / "camara.js", [
        ("  return { poner, ver, enPlanta, empezarAOrbitar, terminar, VISTAS };", ORBITA_ARRASTRE),
    ], "function arrastrar(e)", "ui/camara.js (orbitar arrastrando)")

    # 3 · la versión
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

    for js in ("vista.js", "camara.js", "visor.js"):
        correr(["node", "--check", str(shape / "ui" / js)])
    anotar("los tres archivos tocados pasan node --check")

    (shape / "claude" / "ultimo-recado.md").write_text(
        "# Último recado\n\n*Lo escribe `claude/recado.py` al correr en Actions.*\n\n"
        f"- corrido: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n"
        f"- recado: {VERSION}, el visor pinta siempre\n\n```\n" + "\n".join(lineas) + "\n```\n", encoding="utf-8")

    correr(["git", "add", "-A"], cwd=shape)
    correr(["git", "commit", "-m",
            f"{VERSION}: el visor pinta siempre; Alt + botón central orbita\n\n"
            "Mike, tras probar la 0.7.0: «ya no ocupemos un plano 2D, sólo entorpece el\n"
            "workflow; dibujemos el 2D directo sobre el suelo del 3D». Dos pintores para el\n"
            "mismo espacio era la frontera lenta. Ahora pinta el visor siempre; el modo\n"
            "papel, de donde sale el PDF, sigue con el viejo.\n\n"
            "El visor gana la rejilla proyectada con sus ejes y los textos, de frente a\n"
            "quien mira cuando la vista está girada."],
           cwd=shape)
    correr(["git", "push", "origin", "HEAD:main"], cwd=shape)
    correr(["git", "push", "-f", "origin", f"HEAD:{DESTINO}"], cwd=shape)
    anotar(f"main actualizado y {DESTINO} creada: el armado de {VERSION} arranca")
    return 0


def avisar_del_fracaso(error: str) -> None:
    shape = pathlib.Path("/tmp/recado20/shape101")
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
