"""Las imágenes de shape101: el icono y las tres del instalador.

Mike, el 16-sep, viendo la pantalla de instalación con el icono de draw101:
*«podemos hacer una pantalla de instalación con diseño, algo que refleje más el
concepto de shape101»*. Eligió **una pieza sólida en 3D, sobria**.

Así que eso es: una pieza en isometría, con las tres caras en los mismos tres
tonos de madera con los que la app pinta los sólidos (`ui/cuerpos.js`). Quien
instala ve lo que va a ver después trabajando; no es decoración suelta.

Se dibuja con polígonos y nada más. Sin fuentes raras, sin imágenes traídas de
fuera, sin una biblioteca de dibujo: el armado corre en una máquina limpia y
todo lo que haga falta bajar es una vuelta más que puede fallar.

    python build/imagenes.py

Deja en `build/`:

  · icon.png              1024×1024, con transparencia — la fuente de todo
  · icon.ico              256…16, todos los tamaños que pide Windows
  · installerHeader.bmp   150×57  — la franja de arriba del instalador
  · installerSidebar.bmp  164×314 — la columna de bienvenida y de fin
  · uninstallerSidebar.bmp  la misma, para desinstalar

Los BMP son 24 bits sin alfa a propósito: el NSIS de electron-builder no
entiende otra cosa, y un PNG disfrazado de .bmp se ve como un cuadro negro.
"""
from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw

AQUI = pathlib.Path(__file__).resolve().parent

# Los mismos tres tonos que `ui/cuerpos.js` usa para las caras de una pieza,
# según a dónde miren. Si allá cambian, aquí también.
CLARO = (214, 180, 133)
MEDIO = (176, 143, 100)
OSCURO = (128, 101, 68)
CANTO = (74, 58, 38)

# El fondo de las pantallas del instalador: el mismo gris azulado oscuro del
# tema de la app, para que instalar y trabajar se sientan del mismo programa.
FONDO = (28, 31, 38)
FONDO2 = (38, 43, 53)
TINTA = (232, 233, 238)
ACENTO = (255, 211, 90)


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    """Isometría de libro: x se va a la derecha y abajo, y a la izquierda y
    abajo, z hacia arriba. Es la proyección con la que se miden muebles."""
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    return ((x - y) * c, (x + y) * s - z)


def _pieza(d: ImageDraw.ImageDraw, cx: float, cy: float, escala: float,
           ancho: float = 1.0, fondo_: float = 0.66, alto: float = 0.30,
           canto: int = 0) -> None:
    """Una pieza de taller en isometría: un tablero con su espesor.

    Tres caras y nada más. La de arriba clara, la de la izquierda media, la de
    la derecha oscura: es lo que hace que un sólido se lea como sólido y no
    como una mancha, y es exactamente lo que hace el visor.
    """
    a, f, h = ancho, fondo_, alto
    # El centro se saca de la caja de lo proyectado, no del centro del cubo:
    # en isometría no son el mismo punto, y de ahí salía una pieza recargada
    # abajo a la derecha con medio icono en blanco.
    esquinas = [(x, y, z) for x in (0, a) for y in (0, f) for z in (0, h)]
    uvs = [_iso(*e) for e in esquinas]
    u0 = (min(u for u, _ in uvs) + max(u for u, _ in uvs)) / 2
    v0 = (min(v for _, v in uvs) + max(v for _, v in uvs)) / 2

    def P(x, y, z):
        u, v = _iso(x, y, z)
        return (cx + (u - u0) * escala, cy + (v - v0) * escala)

    arriba = [P(0, 0, h), P(a, 0, h), P(a, f, h), P(0, f, h)]
    izq = [P(0, f, h), P(a, f, h), P(a, f, 0), P(0, f, 0)]
    der = [P(a, 0, h), P(a, f, h), P(a, f, 0), P(a, 0, 0)]
    for poligono, color in ((izq, MEDIO), (der, OSCURO), (arriba, CLARO)):
        d.polygon(poligono, fill=color, outline=CANTO if canto else None, width=canto or 1)


def icono(lado: int = 1024) -> Image.Image:
    im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # El canto se engorda con el tamaño: a 16 píxeles una línea de un píxel
    # desaparece y la pieza se vuelve tres manchas pegadas.
    _pieza(d, lado * 0.5, lado * 0.52, lado * 0.60, canto=max(2, lado // 128))
    return im


def _degradado(ancho: int, alto: int) -> Image.Image:
    """El fondo de las pantallas: oscuro arriba, un poco menos abajo. Sobrio,
    que fue lo que Mike pidió."""
    im = Image.new("RGB", (ancho, alto), FONDO)
    d = ImageDraw.Draw(im)
    for y in range(alto):
        k = y / max(1, alto - 1)
        d.line([(0, y), (ancho, y)],
               fill=tuple(round(FONDO[i] + (FONDO2[i] - FONDO[i]) * k) for i in range(3)))
    return im


def _texto(d: ImageDraw.ImageDraw, xy, texto: str, color, tam: int) -> None:
    """El nombre, con la fuente que haya. No se baja ninguna: si la máquina del
    armado no trae más que la de PIL, se usa ésa y se ve digno igual."""
    from PIL import ImageFont
    fuente = None
    for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if pathlib.Path(ruta).exists():
            fuente = ImageFont.truetype(ruta, tam)
            break
    d.text(xy, texto, fill=color, font=fuente or ImageFont.load_default())


def cabecera(ancho: int = 150, alto: int = 57) -> Image.Image:
    """La franja de arriba, la que se ve mientras se copian los archivos: la
    que Mike mandó en la captura."""
    im = _degradado(ancho, alto)
    d = ImageDraw.Draw(im)
    _pieza(d, ancho - 28, alto * 0.50, alto * 0.50)
    _texto(d, (10, 12), "shape101", TINTA, 15)
    _texto(d, (11, 32), "modelado 3D", (150, 156, 170), 10)
    return im


def columna(ancho: int = 164, alto: int = 314) -> Image.Image:
    """La columna de bienvenida y de fin."""
    im = _degradado(ancho, alto)
    d = ImageDraw.Draw(im)
    _pieza(d, ancho * 0.5, alto * 0.30, ancho * 0.52, canto=1)
    d.line([(16, alto * 0.62), (ancho - 16, alto * 0.62)], fill=ACENTO, width=2)
    _texto(d, (18, alto * 0.66), "shape101", TINTA, 20)
    _texto(d, (19, alto * 0.74), "piezas sólidas,", (150, 156, 170), 11)
    _texto(d, (19, alto * 0.78), "a la medida", (150, 156, 170), 11)
    _texto(d, (19, alto - 26), "Taller 101", (110, 116, 130), 10)
    return im


def main() -> int:
    grande = icono()
    grande.save(AQUI / "icon.png")
    # Windows pide el icono en varios tamaños dentro del mismo archivo: si sólo
    # va el de 256, el explorador lo encoge él y se ve sucio en la barra.
    grande.save(AQUI / "icon.ico",
                sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    cabecera().save(AQUI / "installerHeader.bmp", "BMP")
    col = columna()
    col.save(AQUI / "installerSidebar.bmp", "BMP")
    col.save(AQUI / "uninstallerSidebar.bmp", "BMP")
    for n in ("icon.png", "icon.ico", "installerHeader.bmp", "installerSidebar.bmp",
              "uninstallerSidebar.bmp"):
        print(f"  {n}: {(AQUI / n).stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
