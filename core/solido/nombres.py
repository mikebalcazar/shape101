"""Referencias estables a caras y aristas  ·  el punto más difícil del
proyecto, según el documento de la prueba de concepto. Aquí se miden dos
maneras y se dice cuál sobrevive a un cambio de abajo.

1. **Huella geométrica** (`huella`): centro + normal + área con tolerancia.
   Es lo que sugiere el documento como alternativa. Sirve para reconocer «la
   misma cara» dentro de una regeneración, y se mide si sirve cuando cambia
   una cota del boceto de abajo (spoiler: no, porque las caras se mueven).

2. **Nombres por derivación** (`Nombrador`): cada cara recibe un nombre que
   dice de dónde salió, no dónde está:
     - al extruir un boceto: `arriba`, `abajo` y `lado[i]`, con `i` el índice
       de la arista del boceto que la generó (el orden de las entidades del
       .t101d, que no cambia cuando cambia una cota);
     - tras una operación (restar, redondear, empujar), una cara que **conserva
       su superficie** (mismo plano, o mismo cilindro) conserva su nombre;
     - las caras nuevas se nombran por la operación y por lo que las produjo:
       un redondeo, por las dos caras que separaba la arista;
     - una cara empujada hereda su nombre (la operación lo declara).
   Una arista se nombra por las dos caras que separa: `lado[1]|arriba`.

Por qué «misma superficie» y no «misma cara»: un redondeo o un barreno
recortan las caras vecinas —cambian su área y su centro— pero no su plano ni
su cilindro. Es la identidad que un kernel B-rep sí conserva.
"""
from __future__ import annotations

import math

from build123d import Face, Edge, GeomType, Shape, Vector
from OCP.BRep import BRep_Tool
from OCP.GeomAdaptor import GeomAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder

TOL_DIST = 1e-4
TOL_ANG = 1e-6


# ---------------------------------------------------------------- superficie
def superficie(cara: Face) -> tuple:
    """Los parámetros de la superficie soporte, como números planos (sin
    objetos Vector: se comparan miles de veces por operación y el costo de
    construirlos era la mitad del tiempo de regenerar; medido con cProfile
    el 13-sep: 0.73 s de 1.45 s con 30 operaciones)."""
    ad = GeomAdaptor_Surface(BRep_Tool.Surface_s(cara.wrapped))
    tipo = ad.GetType()
    if tipo == GeomAbs_Plane:
        pl = ad.Plane()
        n = pl.Axis().Direction()
        p = pl.Location()
        nx, ny, nz = n.X(), n.Y(), n.Z()
        # Orientación canónica, NO la de la cara: al restar una herramienta,
        # las paredes del hueco quedan con la normal al revés de la cara de la
        # herramienta que las produjo, y aun así son la misma superficie.
        # Dos caras opuestas sobre el mismo plano se distinguen por cercanía.
        for c in (nx, ny, nz):
            if abs(c) > 1e-9:
                if c < 0:
                    nx, ny, nz = -nx, -ny, -nz
                break
        d = nx * p.X() + ny * p.Y() + nz * p.Z()
        return ("plano", nx, ny, nz, d)
    if tipo == GeomAbs_Cylinder:
        cy = ad.Cylinder()
        ax = cy.Axis()
        p, v = ax.Location(), ax.Direction()
        return ("cilindro", p.X(), p.Y(), p.Z(), v.X(), v.Y(), v.Z(), cy.Radius())
    return ("otra", id(cara))


def misma_superficie(a: tuple, b: tuple) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] == "plano":
        return (a[1] * b[1] + a[2] * b[2] + a[3] * b[3] > 1 - TOL_ANG) and abs(a[4] - b[4]) < TOL_DIST
    if a[0] == "cilindro":
        if abs(a[7] - b[7]) > TOL_DIST:
            return False
        dot = a[4] * b[4] + a[5] * b[5] + a[6] * b[6]
        if abs(abs(dot) - 1) > TOL_ANG:
            return False
        # distancia del punto del eje a al eje b
        wx, wy, wz = a[1] - b[1], a[2] - b[2], a[3] - b[3]
        t = wx * b[4] + wy * b[5] + wz * b[6]
        return math.sqrt((wx - t * b[4]) ** 2 + (wy - t * b[5]) ** 2 + (wz - t * b[6]) ** 2) < TOL_DIST
    return False


# ------------------------------------------------------------------- huella
def _donde(cara: Face) -> tuple:
    """Dónde está esta cara y cuánto mide. Sin la normal, a propósito.

    `huella` lleva la normal, y para una cara plana es la mejor identidad que
    hay. Pero desde la 0.14.0 una cara puede ser **reglada** —se alabea al
    mover un punto— y entonces no tiene una sola normal: `normal_at()` da un
    valor distinto según dónde se pregunte, y la huella deja de casar consigo
    misma. Medido el 19-sep: tras dos ediciones encadenadas, `lado[1]` perdía
    su nombre y con él el de sus cuatro aristas; de doce aristas nombradas
    quedaban ocho.

    Centro y área alcanzan para reconocer **la misma cara del mismo sólido**,
    que es para lo único que se usa esto.
    """
    c = cara.center()
    return (round(c.X, 3), round(c.Y, 3), round(c.Z, 3), round(cara.area, 2))


def huella(cara: Face) -> tuple:
    c = cara.center()
    n = cara.normal_at()
    return (round(c.X, 3), round(c.Y, 3), round(c.Z, 3), round(n.X, 4), round(n.Y, 4), round(n.Z, 4), round(cara.area, 2))


def por_huella(caras: list[Face], h: tuple, tol_dist=0.5, tol_area=0.01) -> Face | None:
    """La cara cuya huella coincide con `h` (centro a < tol_dist, misma normal,
    área a < 1 %). None si ninguna o si hay más de una."""
    hallazgos = []
    for f in caras:
        hf = huella(f)
        if math.dist(hf[:3], h[:3]) > tol_dist:
            continue
        if abs(hf[3] * h[3] + hf[4] * h[4] + hf[5] * h[5] - 1) > 1e-3:
            continue
        if h[6] and abs(hf[6] - h[6]) / h[6] > tol_area:
            continue
        hallazgos.append(f)
    return hallazgos[0] if len(hallazgos) == 1 else None


def _orden(cara: Face) -> tuple:
    """El orden en que se reparten los trozos de una cara partida.

    Tiene que ser **geométrico y no del kernel**: el kernel devuelve las caras
    en el orden en que las fue creando, que cambia con la operación. El centro,
    eje por eje, no cambia de orden cuando la pieza se estira, y por eso el
    mismo trozo se queda con el mismo nombre al cambiar una cota.
    """
    c = cara.center()
    return (round(c.X, 4), round(c.Y, 4), round(c.Z, 4), round(cara.area, 4))


# ---------------------------------------------------------------- nombrador
class Nombrador:
    """Lleva `nombre → cara` para el sólido vigente y lo rehace tras cada
    operación por identidad de superficie."""

    def __init__(self):
        self.caras: dict[str, Face] = {}

    # -- consultas -----------------------------------------------------------
    def cara(self, nombre: str) -> Face:
        try:
            return self.caras[nombre]
        except KeyError:
            raise KeyError(f"no hay una cara llamada «{nombre}»; hay: {sorted(self.caras)}")

    def nombre_de(self, cara: Face) -> str | None:
        s = superficie(cara)
        for n, f in self.caras.items():
            if misma_superficie(s, superficie(f)):
                return n
        return None

    def nombres_en(self, solido: Shape) -> dict:
        """`índice de cara → nombre`, para las caras de **este** sólido.

        Primero por dónde está cada cara, contra las que ya se tienen
        guardadas, y sólo después por superficie. El orden importa: desde la
        0.14.0 una cara puede dejar de ser plana —se alabea al mover un punto y
        pasa a ser una superficie reglada—, y por superficie no se
        reconocería. Con eso se perderían su nombre, los de sus aristas y los
        de sus vértices, que es justo el historial que este archivo existe para
        sostener.
        """
        guardadas = {}
        for nombre, f in self.caras.items():
            try:
                guardadas.setdefault(_donde(f), nombre)
            except Exception:
                continue
        out = {}
        for i, f in enumerate(solido.faces()):
            n = None
            try:
                n = guardadas.get(_donde(f))
            except Exception:
                n = None
            out[i] = n if n else self.nombre_de(f)
        return out

    def aristas(self, solido: Shape) -> dict[str, Edge]:
        """`nombreA|nombreB → arista` para cada arista entre dos caras nombradas."""
        out = {}
        caras = list(solido.faces())
        nombres = self.nombres_en(solido)
        for e in solido.edges():
            vecinas = [nombres[i] for i, f in enumerate(caras) if _cara_tiene(f, e)]
            vecinas = [v for v in vecinas if v]
            if len(vecinas) == 2:
                out["|".join(sorted(vecinas))] = e
        return out

    def vertices(self, solido: Shape) -> dict:
        """`nombreA|nombreB|nombreC → vértice` para cada punto donde se juntan
        tres o más caras nombradas.

        Es la misma idea que los nombres de arista, un piso más abajo: un punto
        no se llama por dónde está —eso cambia en cuanto se mueve algo— sino
        por **qué caras lo forman**. Así, mover una cota del boceto no le
        cambia el nombre a la esquina, y una esquina jalada sigue jalada.

        Si dos puntos distintos comparten las mismas caras —pasa en piezas con
        huecos— se desempatan por posición, en orden, y eso también es estable
        mientras la topología no cambie.
        """
        caras = list(solido.faces())
        nombres = self.nombres_en(solido)
        crudo: dict = {}
        for v in solido.vertices():
            vecinas = sorted({nombres[i] for i, f in enumerate(caras)
                              if nombres[i] and _cara_toca(f, v)})
            if len(vecinas) < 3:
                continue
            crudo.setdefault("|".join(vecinas), []).append(v)
        out = {}
        for nombre, vs in crudo.items():
            if len(vs) == 1:
                out[nombre] = vs[0]
                continue
            for k, v in enumerate(sorted(vs, key=lambda q: (round(q.X, 6), round(q.Y, 6),
                                                            round(q.Z, 6)))):
                out[f"{nombre}#{k}"] = v
        return out

    def vertice(self, solido: Shape, nombre: str):
        todos = self.vertices(solido)
        if nombre in todos:
            return todos[nombre]
        # Por si llega con las caras en otro orden: el nombre es un conjunto.
        base, _, sufijo = nombre.partition("#")
        clave = "|".join(sorted(base.split("|"))) + (f"#{sufijo}" if sufijo else "")
        try:
            return todos[clave]
        except KeyError:
            raise KeyError(f"no hay un vértice llamado «{nombre}»; hay: {sorted(todos)}")

    def arista(self, solido: Shape, nombre: str) -> Edge:
        todas = self.aristas(solido)
        clave = "|".join(sorted(nombre.split("|")))
        try:
            return todas[clave]
        except KeyError:
            raise KeyError(f"no hay una arista llamada «{nombre}»; hay: {sorted(todas)}")

    # -- bautizos -------------------------------------------------------------
    def bautizar_extrusion(self, solido: Shape, aristas_boceto: list[Edge], espesor: float, prefijo: str = ""):
        """Nombra las caras de un sólido recién extruido de un boceto."""
        self.caras = {}
        medios = [a.position_at(0.5) for a in aristas_boceto]
        for f in solido.faces():
            n = f.normal_at()
            if abs(n.Z) > 1 - TOL_ANG:
                nombre = "arriba" if (n.Z > 0) == (espesor > 0) else "abajo"
            else:
                # la arista inferior de la cara lateral es una arista del boceto
                mejor, dist = None, 1e9
                for i, m in enumerate(medios):
                    for e in f.edges():
                        d = (e.position_at(0.5) - m).length
                        if d < dist:
                            mejor, dist = i, d
                nombre = f"lado[{mejor}]"
            self.caras[prefijo + nombre] = f

    def rebautizar(self, solido_nuevo: Shape, nuevas: dict[str, Face] | None = None,
                   heredan: dict[str, str] | None = None) -> list[str]:
        """Tras una operación: las caras del sólido nuevo que conservan
        superficie conservan nombre; `nuevas` trae nombres para las demás
        (por superficie, se resuelven contra el sólido nuevo); `heredan` dice
        «la cara con este nombre ahora es la que tenga la superficie de esta
        otra cara». Devuelve los nombres que se quedaron sin cara.

        Dos caras distintas pueden compartir superficie (dos cajeados en la
        misma fila comparten el plano de su pared): por eso, cuando varias
        caras nuevas casan con el mismo nombre viejo, se queda con el nombre
        **la más cercana** a la cara vieja y las otras siguen buscando. Se
        midió el 13-sep: sin esto, 11 cajeados dejaban 22 caras nombradas de
        50, porque las paredes coplanares se pisaban el nombre."""
        libres = list(solido_nuevo.faces())
        superficies = {id(f): superficie(f) for f in libres}
        asignadas: dict[str, Face] = {}

        def _siguiente(base: str) -> str:
            k = 2
            while f"{base}~{k}" in asignadas:
                k += 1
            return f"{base}~{k}"

        def repartir(diccionario: dict[str, Face]):
            # Primero, quién compite con quién. Un nombre que es el **único**
            # que casa con dos o más caras no está compitiendo: su cara se
            # partió. Un nombre que comparte candidatos con otro sí compite, y
            # ahí manda la cercanía (el caso de los cajeados coplanares).
            candidatos = {}
            for nombre, vieja in diccionario.items():
                sv = superficie(vieja)
                casan = [f for f in libres if misma_superficie(superficies[id(f)], sv)]
                if casan:
                    candidatos[nombre] = casan

            solos, disputados = [], []
            for nombre, casan in candidatos.items():
                otros = [n for n, c in candidatos.items()
                         if n != nombre and any(f in casan for f in c)]
                (solos if not otros else disputados).append(nombre)

            # --- la cara se partió: se reparte por POSICIÓN, no por cercanía.
            #
            # Aquí estaba el defecto que hacía que el historial se equivocara
            # en silencio. Con «la más cercana a la vieja», el nombre base
            # saltaba de un trozo al otro al cambiar una cota: medido el
            # 19-sep sobre un tablero con una muesca, `lado[0]` era el trozo
            # izquierdo con 600 y 450 de ancho, y el **derecho** con 900 y
            # 2000. Una cara jalada se iba al otro lado de la pieza sin avisar.
            #
            # Con el orden del centro, el mismo trozo se queda con el mismo
            # nombre a cualquier medida: comprobado con 450, 600, 900 y 2000.
            for nombre in solos:
                casan = [f for f in candidatos[nombre] if f in libres]
                if not casan:
                    continue
                casan.sort(key=_orden)
                asignadas[nombre] = casan[0]
                libres.remove(casan[0])
                for f in casan[1:]:
                    asignadas[_siguiente(nombre)] = f
                    libres.remove(f)

            for nombre in disputados:
                casan = [f for f in candidatos[nombre] if f in libres]
                if not casan:
                    continue
                cv = diccionario[nombre].center()
                elegida = min(casan, key=lambda f: ((f.center() - cv).length, _orden(f)))
                asignadas[nombre] = elegida
                libres.remove(elegida)

        repartir(self.caras)
        repartir(nuevas or {})
        # Lo que sobra con la MISMA superficie que una cara ya nombrada es una
        # continuación de ésa (el kernel no siempre funde dos caras coplanares
        # o coaxiales tras una booleana): se llama «nombre~2», «nombre~3»…
        # También en orden de posición, por lo mismo de arriba.
        for f in sorted(libres, key=_orden):
            sf = superficies[id(f)]
            base = next((n for n, g in asignadas.items() if "~" not in n and misma_superficie(sf, superficie(g))), None)
            if base:
                asignadas[_siguiente(base)] = f
                libres.remove(f)
        k = 0
        for f in sorted(libres, key=_orden):
            while f"anonima[{k}]" in asignadas:      # nunca pisar un nombre que ya existe
                k += 1
            asignadas[f"anonima[{k}]"] = f
            k += 1
        for viejo, nuevo_ in (heredan or {}).items():
            if nuevo_ not in asignadas:
                continue
            # La cara que ya tenía ese nombre no se tira: se corre a un
            # «~k». Antes se perdía, y con ella el nombre de sus aristas y sus
            # vértices. Medido el 19-sep: jalar `lado[0]` con la cara ya
            # partida dejaba el otro trozo sin nombre.
            desplazada = asignadas.get(viejo)
            asignadas[viejo] = asignadas.pop(nuevo_)
            if desplazada is not None and desplazada is not asignadas[viejo]:
                asignadas[_siguiente(viejo)] = desplazada
        perdidas = [n for n in self.caras if n not in asignadas]
        self.caras = asignadas
        return perdidas


def _cara_toca(cara: Face, vertice) -> bool:
    """¿Ese punto es uno de los vértices de esta cara? Se compara por posición
    con la misma tolerancia que todo lo demás: dos objetos distintos del kernel
    pueden ser el mismo punto del mundo."""
    p = (vertice.X, vertice.Y, vertice.Z)
    for v in cara.vertices():
        if (abs(p[0] - v.X) < TOL_DIST and abs(p[1] - v.Y) < TOL_DIST
                and abs(p[2] - v.Z) < TOL_DIST):
            return True
    return False


def _extremos(e: Edge) -> tuple:
    """Los dos extremos de una arista, ordenados: sirven de identidad sin
    depender de cómo esté parametrizada."""
    a, b = e.start_point(), e.end_point()
    pa = (round(a.X, 4), round(a.Y, 4), round(a.Z, 4))
    pb = (round(b.X, 4), round(b.Y, 4), round(b.Z, 4))
    return (pa, pb) if pa <= pb else (pb, pa)


def _cara_tiene(cara: Face, arista: Edge) -> bool:
    """¿Esta arista es una de las de esta cara?

    Se compara por **extremos**, no por el punto de en medio. Desde la 0.14.0
    la misma arista puede llegar como LINE desde una cara y como BSPLINE desde
    la de al lado —la superficie reglada de una cara alabeada reescribe sus
    bordes—, y un BSPLINE no tiene su punto medio geométrico en el parámetro
    0.5: la parametrización no es uniforme. Medido el 19-sep: por el punto
    medio, las cuatro aristas de la cara reglada se quedaban sin nombre y de
    doce nombradas quedaban ocho.

    Un círculo completo tiene los dos extremos en el mismo sitio, así que el
    largo sigue entrando en la comparación para no confundir dos que se cierren
    sobre el mismo punto.
    """
    ext = _extremos(arista)
    for e in cara.edges():
        if _extremos(e) == ext and abs(e.length - arista.length) < TOL_DIST:
            return True
    return False
