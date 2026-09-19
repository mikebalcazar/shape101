"""Mover puntos de un sólido y volverlo a coser  ·  0.14.0

Mike, el 19-sep: *«debería ser un sólido, cada contorno independiente (un loft
como dices). Todas las aristas son independientes y todos los puntos también.
Para generar el sólido se generan superficies entre cada región creada por las
aristas»*.

Eso es lo que hace este módulo. Se le dan puntos del sólido y a dónde van; cada
cara se vuelve a armar desde su propio contorno con los extremos ya corridos, y
las caras se cosen en una cáscara que se cierra en un sólido.

**Cuando una cara se alabea** —deja de ser plana porque uno solo de sus cuatro
puntos se movió— no se fuerza un plano: se pone la superficie **reglada** entre
sus dos lados opuestos, que pasa exactamente por los cuatro puntos. Forzar el
plano sería mentir sobre la pieza, y en un taller esa mentira se corta en la
madera. Ver `_alabeada`, que cuenta por qué no se rellena el contorno.

Medido el 19-sep sobre un tablero de 600 × 400 × 18:

  · mover un vértice          → sólido válido, 6 caras, la caja queda 650 × 400 × 18
  · mover una arista entera   → válido, volumen exacto (4 680 000 mm³)
  · subir una arista de abajo → válido, volumen exacto (3 120 000 mm³)
  · dos ediciones encadenadas → válido
  · mover también en Z        → válido; la pieza deja de ser prisma y aguanta

**El orden de las caras se conserva a propósito.** Las caras del sólido nuevo
salen en el mismo orden que las del viejo, y por eso los nombres se pueden
pasar por posición en vez de por superficie. Hace falta: una cara alabeada deja
de ser un plano y pasa a ser una superficie reglada, y por superficie ya no se
reconocería —se perderían los nombres y con ellos el historial—.
"""
from __future__ import annotations

TOL = 1e-6


def _iguales(a, b, tol: float = TOL) -> bool:
    return (a - b).length < tol


def mover(solido, movimientos: list, nombres_de_cara: list | None = None,
          tol: float = TOL):
    """Rehace `solido` con esos puntos corridos.

    `movimientos` es [((x, y, z), (dx, dy, dz)), ...] en coordenadas del
    kernel. `nombres_de_cara` es la lista de nombres de las caras del sólido
    viejo, **en su orden**; si viene, se devuelve el mapa nombre → cara nueva.

    Devuelve (solido_nuevo, caras_por_nombre, alabeadas).
    """
    from build123d import Edge, Face, Shell, Solid, Vector, Wire

    if not movimientos:
        raise ValueError("no hay nada que mover")
    destinos = [(Vector(*p), Vector(*d)) for p, d in movimientos]

    def corrido(p):
        for origen, d in destinos:
            if _iguales(p, origen, tol):
                return p + d
        return p

    caras_viejas = list(solido.faces())
    if nombres_de_cara is not None and len(nombres_de_cara) != len(caras_viejas):
        raise ValueError("la lista de nombres no cuadra con las caras del sólido")

    caras, nombres_nuevos, alabeadas = [], [], 0
    for i, f in enumerate(caras_viejas):
        aristas = []
        for e in f.edges():
            if not _es_recta(e):
                # Un arco o un círculo de verdad —el filo de un redondeo, el
                # borde de un barreno— no se deforma moviendo un extremo. Si lo
                # que se está moviendo es justo uno de sus extremos, se dice en
                # voz alta en vez de sacar una pieza retorcida.
                if any(_iguales(corrido(q), q, tol) is False
                       for q in (e.start_point(), e.end_point())):
                    raise ValueError(
                        "ese punto es de una arista curva (un redondeo o un "
                        "barreno). Mover puntos de curvas todavía no está.")
                aristas.append(e)
                continue
            a, b = corrido(e.start_point()), corrido(e.end_point())
            if _iguales(a, b, tol):
                continue                      # la arista se cerró sobre sí misma
            aristas.append(Edge.make_line(a, b))
        if len(aristas) < 3:
            raise ValueError(
                "ese movimiento cierra una cara de la pieza. Muévelo menos, o "
                "muévelo en otra dirección.")
        contornos = Wire.combine(aristas)
        if not contornos:
            raise ValueError("una cara se quedó sin contorno al mover")
        w = contornos[0]
        try:
            caras.append(Face(w))                       # sigue siendo plana
        except Exception:
            caras.append(_alabeada(w, aristas))
            alabeadas += 1
        nombres_nuevos.append(nombres_de_cara[i] if nombres_de_cara else None)

    solido_nuevo = Solid(Shell(caras))
    valido = solido_nuevo.is_valid
    if not (valido if isinstance(valido, bool) else valido()):
        raise ValueError("la pieza no cierra con ese movimiento")

    por_nombre = {}
    if nombres_de_cara is not None:
        # Por posición, no por superficie: ver el encabezado.
        for nombre, cara in zip(nombres_nuevos, solido_nuevo.faces()):
            if nombre:
                por_nombre[nombre] = cara
    return solido_nuevo, por_nombre, alabeadas


def punto_de(v) -> tuple:
    """Un vértice o un punto de build123d, como tres números planos."""
    return (round(v.X, 6), round(v.Y, 6), round(v.Z, 6))


def _encadenar(aristas: list) -> list:
    """Las aristas en el orden en que se recorre el contorno.

    `Face.edges()` las devuelve en el orden del kernel, que no es el del
    recorrido. Para construir una superficie reglada hace falta saber cuáles
    son **opuestas**, y eso sólo se sabe encadenándolas por sus extremos.
    """
    restantes = list(aristas)
    cadena = [restantes.pop(0)]
    punta = cadena[-1].end_point()
    while restantes:
        for k, e in enumerate(restantes):
            if _iguales(e.start_point(), punta):
                cadena.append(restantes.pop(k))
                punta = cadena[-1].end_point()
                break
            if _iguales(e.end_point(), punta):
                cadena.append(restantes.pop(k).reversed())
                punta = cadena[-1].end_point()
                break
        else:
            return []                      # no cierra: no se puede encadenar
    return cadena


def _alabeada(w, aristas: list):
    """Una cara que dejó de ser plana.

    Con cuatro lados rectos —el caso de todas las caras de una pieza de
    taller— la superficie correcta es la **reglada** entre los dos lados
    opuestos: pasa exactamente por los cuatro puntos y no se sale de ellos.

    La alternativa, rellenar el contorno (`make_surface`), se **infla**: medido
    el 19-sep sobre la cara lateral de un tablero al jalarle una esquina 50 mm,
    la cara rellenada se iba de z = −39.53 a 18 cuando la pieza mide 18 de
    espesor. Una pieza que sobresale 39 mm de donde dice que está no se puede
    cortar. El reglado se queda en 0..18, que es lo que hay.

    Para cualquier otra cara —más de cuatro lados, o con un hueco— se rellena,
    que es lo único que hay, y el que llama se entera por la cuenta de
    alabeadas.
    """
    from build123d import Face
    cadena = _encadenar(list(aristas))
    if len(cadena) == 4 and all(e.geom_type.name == "LINE" for e in cadena):
        try:
            # Opuestas, y la segunda al revés: así el reglado va de lado a
            # lado y no cruzado en moño.
            return Face.make_surface_from_curves(cadena[0], cadena[2].reversed())
        except Exception:
            pass
    return Face.make_surface(w)


def _es_recta(e, tol: float = 1e-4) -> bool:
    """¿Esta arista es un segmento recto, aunque el kernel la llame otra cosa?

    Hace falta preguntarlo así: la superficie reglada que se pone en una cara
    alabeada **reescribe sus bordes como BSPLINE**, aunque geométricamente
    sigan siendo rectas. Medido el 19-sep: tras la primera edición, dos de las
    aristas de la pieza salían BSPLINE. Mirando sólo el nombre del tipo, la
    segunda edición las dejaba sin mover y el contorno de la cara ya no
    cerraba: «Face can only be created with closed wires».

    Así que se mide, no se pregunta: si el punto de en medio cae sobre la recta
    que une los extremos, es una recta.
    """
    if e.geom_type.name == "LINE":
        return True
    try:
        a, b, m = e.start_point(), e.end_point(), e.position_at(0.5)
    except Exception:
        return False
    largo = (b - a).length
    if largo < 1e-9:
        return False
    return ((a + b) * 0.5 - m).length <= max(tol, largo * tol)
