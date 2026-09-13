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

    def aristas(self, solido: Shape) -> dict[str, Edge]:
        """`nombreA|nombreB → arista` para cada arista entre dos caras nombradas."""
        out = {}
        caras = list(solido.faces())
        nombres = {i: self.nombre_de(f) for i, f in enumerate(caras)}
        for e in solido.edges():
            vecinas = [nombres[i] for i, f in enumerate(caras) if _cara_tiene(f, e)]
            vecinas = [v for v in vecinas if v]
            if len(vecinas) == 2:
                out["|".join(sorted(vecinas))] = e
        return out

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

        def repartir(diccionario: dict[str, Face]):
            for nombre, vieja in diccionario.items():
                sv = superficie(vieja)
                casan = [f for f in libres if misma_superficie(superficies[id(f)], sv)]
                if not casan:
                    continue
                if len(casan) == 1:
                    elegida = casan[0]
                else:
                    cv = vieja.center()
                    elegida = min(casan, key=lambda f: (f.center() - cv).length)
                asignadas[nombre] = elegida
                libres.remove(elegida)

        repartir(self.caras)
        repartir(nuevas or {})
        # Lo que sobra con la MISMA superficie que una cara ya nombrada es una
        # continuación de ésa (el kernel no siempre funde dos caras coplanares
        # o coaxiales tras una booleana): se llama «nombre~2», «nombre~3»…
        for f in list(libres):
            sf = superficies[id(f)]
            base = next((n for n, g in asignadas.items() if "~" not in n and misma_superficie(sf, superficie(g))), None)
            if base:
                k = 2
                while f"{base}~{k}" in asignadas:
                    k += 1
                asignadas[f"{base}~{k}"] = f
                libres.remove(f)
        k = 0
        for f in libres:
            while f"anonima[{k}]" in asignadas:      # nunca pisar un nombre que ya existe
                k += 1
            asignadas[f"anonima[{k}]"] = f
            k += 1
        for viejo, nuevo in (heredan or {}).items():
            if nuevo in asignadas:
                asignadas[viejo] = asignadas.pop(nuevo)
        perdidas = [n for n in self.caras if n not in asignadas]
        self.caras = asignadas
        return perdidas


def _cara_tiene(cara: Face, arista: Edge) -> bool:
    m = arista.position_at(0.5)
    for e in cara.edges():
        if (e.position_at(0.5) - m).length < TOL_DIST and abs(e.length - arista.length) < TOL_DIST:
            return True
    return False
