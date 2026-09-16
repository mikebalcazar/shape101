"""La versión de shape101  ·  un solo lugar.

Hasta el 31-ago-2026 el número vivía escrito a mano en `build/armar_paquete.py`
y nadie lo subía: ocho instaladores distintos salieron llamándose todos
`DIBUJADOR-0.9.0-setup.exe`. Desde dentro de la app no había manera de saber
cuál estaba corriendo. Eso se acabó aquí:

  · el número se declara **una vez**, en este archivo;
  · `build/armar_paquete.py` lo lee de aquí para el `.nsi` y para el nombre
    del `.exe`;
  · la app lo enseña en el pie y el comando `VERSION` cuenta qué cambió;
  · el armador se niega a repetir versión si el código cambió (ver
    `build/entregas.json`).

Numeración: `mayor.menor.parche`.
  · **parche** — se arregló algo, nada nuevo que aprender.
  · **menor** — hay función nueva o cambió cómo se comporta algo.
  · **mayor** — 1.0.0 el día que el taller dibuje un plano completo aquí sin
    volver a AutoCAD.
"""

from __future__ import annotations

VERSION = "0.4.1"
FECHA = "2026-09-16"

# Qué trae cada entrega, en el idioma del taller y no en el del código.
# La más nueva arriba. Lo que se lista aquí es lo que el comando VERSION
# enseña en la consola.
BITACORA: list[dict] = [
    {
        "version": "0.4.1",
        "fecha": "2026-09-16",
        "cambios": [
            "EXTRUIR ya pregunta el espesor como el resto del programa, con la cajita de "
            "siempre: acepta coma o punto y recuerda lo último que tecleaste. En 0.4.0 el "
            "comando se quedaba muerto sin preguntar nada.",
        ],
    },
    {
        "version": "0.4.0",
        "fecha": "2026-09-15",
        "cambios": [
            "Empieza el 3D. Dibuja un contorno cerrado como siempre, selecciónalo y teclea "
            "EXTRUIR: se levanta y se vuelve una pieza sólida de verdad, con su espesor.",
            "La vista pasa a 3D sola. Arrastrando en el vacío se gira la pieza y la rueda "
            "acerca. Un clic señala una cara —se pone amarilla— y arrastrarla la jala: la "
            "pieza se rehace, no se estira. La medida se toma sobre la dirección a la que la "
            "cara apunta, así que jalar se siente igual mires desde donde mires.",
            "Los vértices del contorno salen como puntos azules. Al mover uno, la pieza "
            "entera se reconstruye y conserva lo que hayas hecho después: un barreno sigue "
            "siendo redondo y una cara jalada sigue jalada.",
            "La pieza se guarda dentro del .101s como cómo se hizo, no como una malla, y sale "
            "en STEP para abrirla en otro CAD o en STL para imprimirla.",
            "Escape vuelve al dibujo; el comando 3D regresa. Esta es la primera versión del "
            "gesto: todavía no hay ejes de arrastre, ni ajuste a rejilla, ni deshacer dentro "
            "del 3D.",
            "El instalador pesa bastante más: el motor de sólidos (OpenCascade) son unos "
            "200 MB. Es el precio de que las piezas sean exactas y se puedan exportar.",
            "Seguridad del botón «Instalar ODA»: el instalador del convertidor sólo se "
            "baja de opendesign.com por https; una liga ajena del puntero se ignora, y si "
            "el puntero declara la huella sha256 se comprueba antes de correr msiexec. "
            "Prueba t023 (28 comprobaciones).",
        ],
    },
    {
        "version": "0.3.0",
        "fecha": "2026-09-14",
        "cambios": [
            "shape101 vuelve a nacer, ahora desde la fuente de draw101 0.20.4. Trae todo lo "
            "que draw101 sabe hacer en 2D; el modelado 3D empieza en la siguiente entrega.",
            "Sus archivos son .101s y sus preferencias, bloques y autoguardado viven en su "
            "propia carpeta: draw101 y shape101 son dos programas distintos que comparten un "
            "abuelo. Ninguno le pisa el trabajo al otro.",
            "La numeración arranca en 0.3.0 porque las versiones 0.1.0 y 0.2.0 de shape101 ya se "
            "publicaron con otro contenido, y un número repetido con contenido distinto es "
            "justo lo que no se debe hacer.",
        ],
    },
]


def bitacora(desde: str | None = None) -> list[dict]:
    """La bitácora, opcionalmente recortada a partir de una versión."""
    if desde is None:
        return BITACORA
    salida = []
    for e in BITACORA:
        salida.append(e)
        if e["version"] == desde:
            break
    return salida


def como_tupla(v: str = VERSION) -> tuple[int, int, int]:
    """`"0.10.0"` → `(0, 10, 0)`. Para comparar sin sorpresas alfabéticas:
    ordenado como texto, 0.9.0 sale *después* de 0.10.0."""
    partes = (v.split("-")[0].split(".") + ["0", "0", "0"])[:3]
    return tuple(int(p) if p.isdigit() else 0 for p in partes)  # type: ignore[return-value]
