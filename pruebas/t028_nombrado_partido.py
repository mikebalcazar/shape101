"""Cuando una operación parte una cara en dos  ·  0.17.0

El rumbo de shape101 llama al nombrado topológico *«el riesgo que gobierna
todo»*, y dice que hay que medirlo antes de la etapa C. Se midió el 19-sep
sobre un tablero con una muesca, y salieron dos defectos:

1. **El nombre base saltaba de un trozo al otro al cambiar una cota.** El
   trozo se elegía «el más cercano a la cara vieja», y la cara vieja era la
   entera, cuyo centro se mueve al estirar la pieza. Medido: `lado[0]` era el
   trozo izquierdo con 600 y 450 de ancho, y el **derecho** con 900 y 2000.
   Una cara jalada se iba al otro lado de la pieza sin avisar. **No fallaba:
   se equivocaba en silencio**, que es peor.
2. **Jalar una cara ya partida dejaba a su hermana sin nombre**, y con ella
   sin nombre sus aristas y sus vértices.

Lo que esta prueba fija, entonces:

- Partir una cara no deja ninguna cara sin nombre, ni en una pieza ni en dos.
- **El mismo trozo se queda con el mismo nombre a cualquier medida.** Es la
  comprobación que sostiene todo lo demás: sin ella, el historial miente.
- Lo que se hizo sobre un trozo sigue en ese trozo cuando la pieza cambia de
  tamaño.
- Las aristas y los vértices siguen nombrados después de partir.
"""
from __future__ import annotations

from pruebas import comun

DESCRIPCION = "nombrado cuando una cara se parte en dos (el riesgo de la etapa C)"

FONDO, ESPESOR = 400.0, 18.0
ANCHOS = (450.0, 600.0, 900.0, 2000.0)


def _con_muesca(ancho=600.0, extra=None):
    """Un tablero con una muesca que entra por el lado de y=0 y parte `lado[0]`
    en dos trozos: el de la izquierda y el de la derecha."""
    ops = [
        {"op": "boceto", "entidades": [{"tipo": "polilinea", "cerrada": True,
         "puntos": [[0, 0, 0], [ancho, 0, 0], [ancho, FONDO, 0], [0, FONDO, 0]]}]},
        {"op": "extruir", "mm": ESPESOR},
        {"op": "restar", "mm": ESPESOR, "entidades": [{"tipo": "polilinea", "cerrada": True,
         "puntos": [[200, -10, 0], [400, -10, 0], [400, 100, 0], [200, 100, 0]]}]},
    ]
    return ops + (extra or [])


def correr(r: comun.Reporte) -> None:
    from core.solido import historial

    _nadie_se_queda_sin_nombre(r, historial)
    _el_mismo_trozo_el_mismo_nombre(r, historial)
    _jalar_un_trozo_no_borra_al_otro(r, historial)
    _una_pieza_partida_en_dos(r, historial)
    _aristas_y_vertices(r, historial)


def _mapa(reg) -> dict:
    """`nombre → (centro, área)` de las caras del sólido, por posición."""
    porIdx = reg.nombrador.nombres_en(reg.solido)
    out = {}
    for i, c in enumerate(reg.solido.faces()):
        n = porIdx[i]
        cen = c.center()
        out[n] = (round(cen.X, 2), round(cen.Y, 2), round(cen.Z, 2), round(c.area, 1))
    return out


def _sin_nombre(reg) -> int:
    porIdx = reg.nombrador.nombres_en(reg.solido)
    return sum(1 for i in range(len(reg.solido.faces())) if not porIdx[i])


# --- 1 ----------------------------------------------------------------------

def _nadie_se_queda_sin_nombre(r: comun.Reporte, historial) -> None:
    reg = historial.regenerar(_con_muesca())
    caras = len(reg.solido.faces())
    r.igual(caras, 10, "un tablero con una muesca tiene diez caras")
    r.igual(_sin_nombre(reg), 0, "y las diez tienen nombre")
    m = _mapa(reg)
    r.cierto("lado[0]" in m and "lado[0]~2" in m,
             "la cara partida da dos nombres: el base y su hermano «~2»")
    r.igual(len(m), caras, "y no hay dos caras compartiendo un nombre")


# --- 2 · la que sostiene todo lo demás --------------------------------------

def _el_mismo_trozo_el_mismo_nombre(r: comun.Reporte, historial) -> None:
    """A cualquier medida, `lado[0]` tiene que ser el mismo trozo.

    El trozo de la izquierda es el que va de x=0 a x=200: su centro está en
    x=100 pase lo que pase con el ancho del tablero. El de la derecha se
    estira, así que su centro se mueve. Si el nombre base saltara, esto lo
    caza.
    """
    for ancho in ANCHOS:
        reg = historial.regenerar(_con_muesca(ancho))
        m = _mapa(reg)
        r.igual(_sin_nombre(reg), 0, f"con {ancho:.0f} de ancho, ninguna cara sin nombre")
        r.casi(m["lado[0]"][0], 100.0,
               f"con {ancho:.0f} de ancho, «lado[0]» sigue siendo el trozo de la izquierda", 1e-6)
        r.cierto(m["lado[0]~2"][0] > 200.0,
                 f"con {ancho:.0f}, «lado[0]~2» es el de la derecha")

    # Y lo que de verdad importa: una operación puesta sobre un trozo sigue en
    # ese trozo cuando la pieza cambia de tamaño.
    jalado = [{"op": "empujar_cara", "cara": "lado[0]", "mm": 10}]
    chica = historial.regenerar(_con_muesca(600.0, jalado))
    grande = historial.regenerar(_con_muesca(2000.0, jalado))
    r.casi(_mapa(chica)["lado[0]"][1], -10.0,
           "el trozo jalado salió 10 mm en la pieza de 600", 1e-6)
    r.casi(_mapa(grande)["lado[0]"][1], -10.0,
           "y en la de 2000 es el mismo trozo el que sale, no el otro", 1e-6)
    r.casi(_mapa(grande)["lado[0]"][0], 100.0,
           "y sigue estando en la izquierda, donde se jaló", 1e-6)


# --- 3 ----------------------------------------------------------------------

def _jalar_un_trozo_no_borra_al_otro(r: comun.Reporte, historial) -> None:
    reg = historial.regenerar(_con_muesca(600.0, [
        {"op": "empujar_cara", "cara": "lado[0]", "mm": 10}]))
    r.igual(_sin_nombre(reg), 0,
            "jalar un trozo no deja a su hermano sin nombre")
    m = _mapa(reg)
    r.cierto("lado[0]~2" in m, "el hermano conserva su nombre")
    r.casi(m["lado[0]~2"][1], 0.0, "y se queda donde estaba: no se movió con el otro", 1e-6)

    # Y se puede seguir trabajando sobre el hermano, por su nombre.
    dos = historial.regenerar(_con_muesca(600.0, [
        {"op": "empujar_cara", "cara": "lado[0]", "mm": 10},
        {"op": "empujar_cara", "cara": "lado[0]~2", "mm": 20}]))
    r.igual(_sin_nombre(dos), 0, "y jalar después al hermano tampoco pierde nada")
    n = _mapa(dos)
    r.casi(n["lado[0]"][1], -10.0, "cada trozo se fue por su lado: el primero a −10")
    r.casi(n["lado[0]~2"][1], -20.0, "y el segundo a −20", 1e-6)


# --- 4 ----------------------------------------------------------------------

def _una_pieza_partida_en_dos(r: comun.Reporte, historial) -> None:
    """Una ranura pasante deja dos sólidos. No se arregla aquí —una pieza que
    se parte en dos es otra conversación— pero **no se pierde ni un nombre**,
    que es lo que haría imposible seguir trabajando."""
    ops = [
        {"op": "boceto", "entidades": [{"tipo": "polilinea", "cerrada": True,
         "puntos": [[0, 0, 0], [600, 0, 0], [600, FONDO, 0], [0, FONDO, 0]]}]},
        {"op": "extruir", "mm": ESPESOR},
        {"op": "restar", "mm": ESPESOR, "entidades": [{"tipo": "polilinea", "cerrada": True,
         "puntos": [[280, -10, 0], [320, -10, 0], [320, FONDO + 10, 0], [280, FONDO + 10, 0]]}]},
    ]
    reg = historial.regenerar(ops)
    r.igual(len(reg.solido.solids()), 2, "la ranura pasante parte la pieza en dos sólidos")
    r.igual(_sin_nombre(reg), 0, "y aun así ninguna cara se queda sin nombre")
    m = _mapa(reg)
    r.igual(len(m), len(reg.solido.faces()), "cada cara tiene un nombre suyo")
    for base in ("arriba", "abajo", "lado[0]", "lado[2]"):
        r.cierto(f"{base}~2" in m, f"«{base}» se partió y su hermano tiene nombre")


# --- 5 ----------------------------------------------------------------------

def _aristas_y_vertices(r: comun.Reporte, historial) -> None:
    """Las aristas y los vértices se llaman por las caras que los forman. Si
    partir una cara dejara caras sin nombre, se caerían también ellos."""
    limpio = historial.regenerar([
        {"op": "boceto", "entidades": [{"tipo": "polilinea", "cerrada": True,
         "puntos": [[0, 0, 0], [600, 0, 0], [600, FONDO, 0], [0, FONDO, 0]]}]},
        {"op": "extruir", "mm": ESPESOR}])
    r.igual(len(limpio.nombrador.aristas(limpio.solido)), 12,
            "un tablero limpio tiene doce aristas nombradas")

    reg = historial.regenerar(_con_muesca())
    aristas = reg.nombrador.aristas(reg.solido)
    vertices = reg.nombrador.vertices(reg.solido)
    r.cierto(len(aristas) >= 20,
             "con la muesca hay más aristas, y siguen nombradas",
             f"{len(aristas)} aristas")
    r.cierto(any("lado[0]~2" in n for n in aristas),
             "las aristas del trozo hermano también tienen nombre")
    r.cierto(len(vertices) >= 12,
             "y los vértices siguen nombrados", f"{len(vertices)} vértices")
