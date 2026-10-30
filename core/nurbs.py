"""Curvas NURBS exactas: la misma curva en pantalla, en el osnap y en el DXF.

Hasta 0.21.9 la spline de shape101 no guardaba nudos ni pesos. Se pintaba con
Catmull-Rom (la de puntos de ajuste) o con una B-spline uniforme (la de
control), y al DXF salía **sólo con los puntos**: AutoCAD, la CNC o Rhino la
volvían a interpolar con su propio algoritmo. La curva que se veía no era la
que se cortaba.

La regla que sigue Rhino —y que aquí se adopta— es que una curva libre **es**
su NURBS completa: grado, nudos, pesos y puntos de control. Todo lo demás
(pintarla, engancharle el osnap, escribirla) se deriva de eso, y como el DXF
sabe guardar exactamente esos cuatro datos, el archivo lleva la curva tal
cual, sin que nadie del otro lado tenga que adivinarla.

Lo que hay aquí, todo de libro (De Boor, interpolación global por longitud de
cuerda, subdivisión adaptativa) y escrito para este programa:

- `Nurbs`                 la curva: evaluar, derivar, teselar, cercano, caja.
- `sujeta_uniforme`       la spline CV abierta de siempre (no cambia de forma).
- `periodica_uniforme`    la spline CV cerrada, suave también en la costura.
- `interpolar`            la que pasa por los puntos de ajuste, abierta (de libro).
- `interpolar_cad`        la misma, con el cierre de AutoCAD: la que usa SPLINE.
- `interpolar_cerrada`    la que pasa por los puntos de ajuste, cerrada.

Sin numpy en la evaluación: es lo que corre al pintar y al picar, y una curva
de taller tiene decenas de puntos, no miles. numpy sólo resuelve el sistema de
la interpolación.
"""

from __future__ import annotations

import math

#: Flecha por omisión al teselar: lo más que la poligonal se separa de la curva
#: de verdad, en unidades del dibujo. La misma que usan los arcos para pintarse
#: (`core/dibujo.FLECHA_MAX`): un arco y una spline vecinos se ven igual de finos.
FLECHA = 0.05

#: Hasta dónde se parte un tramo buscando la flecha. 2**12 trozos por tramo de
#: nudos es más de lo que una curva de taller llega a pedir; el tope existe para
#: que una curva degenerada no cuelgue el pintado.
PROFUNDIDAD = 12


class Nurbs:
    """Una curva NURBS de grado `grado` en el plano (o en 3D: se respeta la
    dimensión de los puntos de control que se le den).

    `nudos` tiene `len(control) + grado + 1` valores no decrecientes. `pesos`
    vale None para una B-spline (todos 1), que es el caso de casi todas.
    """

    __slots__ = ("grado", "control", "nudos", "pesos", "dim", "_derivadas", "_bezier")

    def __init__(self, grado: int, control, nudos, pesos=None):
        control = [[float(c) for c in p] for p in control]
        if not control:
            raise ValueError("una curva necesita al menos un punto de control")
        dim = len(control[0])
        if any(len(p) != dim for p in control):
            raise ValueError("todos los puntos de control deben tener la misma dimensión")
        n = len(control)
        if grado < 1 or grado >= n + (1 if n == 1 else 0):
            if not (n == 1 and grado == 0):
                raise ValueError(f"grado {grado} con {n} puntos de control")
        nudos = [float(k) for k in nudos]
        if len(nudos) != n + grado + 1:
            raise ValueError(f"se esperaban {n + grado + 1} nudos y vinieron {len(nudos)}")
        if any(nudos[i] > nudos[i + 1] for i in range(len(nudos) - 1)):
            raise ValueError("los nudos deben ir en orden")
        if nudos[grado] >= nudos[n]:
            raise ValueError("el dominio de la curva está vacío")
        # Un nudo interior repetido más que el grado parte la curva en pedazos
        # sueltos (o la deja sin definir): no es una curva que un CAD dibuje.
        # Una spline así de un DXF se queda conservada, sin tocarla.
        interiores = nudos[grado + 1:n]
        if any(interiores.count(k) > grado for k in set(interiores)):
            raise ValueError("un nudo interior se repite más veces que el grado")
        if pesos is not None:
            pesos = [float(w) for w in pesos]
            if len(pesos) != n:
                raise ValueError("un peso por punto de control")
            if any(w <= 0 for w in pesos):
                raise ValueError("los pesos deben ser positivos")
            if all(abs(w - 1.0) < 1e-12 for w in pesos):
                pesos = None
        self.grado = grado
        self.control = control
        self.nudos = nudos
        self.pesos = pesos
        self.dim = dim
        self._derivadas = None
        self._bezier = None

    # -- lo básico ----------------------------------------------------------
    @property
    def dominio(self) -> tuple[float, float]:
        return self.nudos[self.grado], self.nudos[len(self.control)]

    @property
    def racional(self) -> bool:
        return self.pesos is not None

    def _tramo(self, t: float) -> int:
        """El índice s tal que nudos[s] <= t < nudos[s+1], dentro del dominio."""
        p, n = self.grado, len(self.control)
        k = self.nudos
        if t >= k[n]:
            # La punta derecha cae en el último tramo no vacío.
            s = n - 1
            while s > p and k[s] >= k[n]:
                s -= 1
            return s
        if t <= k[p]:
            s = p
            while s < n - 1 and k[s + 1] <= k[p]:
                s += 1
            return s
        bajo, alto = p, n
        while alto - bajo > 1:
            medio = (bajo + alto) // 2
            if t < k[medio]:
                alto = medio
            else:
                bajo = medio
        return bajo

    def _base(self, s: int, t: float) -> list[float]:
        """Las grado+1 funciones base que no son cero en el tramo s."""
        p, k = self.grado, self.nudos
        N = [1.0] + [0.0] * p
        izq = [0.0] * (p + 1)
        der = [0.0] * (p + 1)
        for j in range(1, p + 1):
            izq[j] = t - k[s + 1 - j]
            der[j] = k[s + j] - t
            guardado = 0.0
            for r in range(j):
                den = der[r + 1] + izq[j - r]
                temp = 0.0 if den == 0 else N[r] / den
                N[r] = guardado + der[r + 1] * temp
                guardado = izq[j - r] * temp
            N[j] = guardado
        return N

    def punto(self, t: float) -> list[float]:
        s = self._tramo(t)
        N = self._base(s, t)
        p, d = self.grado, self.dim
        if self.pesos is None:
            out = [0.0] * d
            for i in range(p + 1):
                c = self.control[s - p + i]
                for j in range(d):
                    out[j] += N[i] * c[j]
            return out
        out = [0.0] * d
        w = 0.0
        for i in range(p + 1):
            idx = s - p + i
            nw = N[i] * self.pesos[idx]
            c = self.control[idx]
            for j in range(d):
                out[j] += nw * c[j]
            w += nw
        return [v / w for v in out]

    def derivadas(self, t: float) -> tuple[list[float], list[float], list[float]]:
        """C(t), C'(t) y C''(t), exactas.

        No por diferencias: una segunda derivada sacada restando primeras
        derivadas que ya eran restas amplifica el ruido hasta que Newton no
        avanza (pasó buscando el cercano: 0.13 de error sobre la curva misma).
        Se deriva la curva en coordenadas homogéneas —la hodógrafa de una
        B-spline es otra B-spline un grado abajo— y la parte racional sale por
        la regla del cociente.
        """
        if self._derivadas is None:
            hom = ([[c * w for c in p] + [w] for p, w in zip(self.control, self.pesos)]
                   if self.pesos is not None else [p + [1.0] for p in self.control])
            d1 = _hodografa(self.grado, self.nudos, hom)
            d2 = _hodografa(*d1) if d1[0] >= 1 else (0, d1[1], [[0.0] * (self.dim + 1)])
            self._derivadas = ((self.grado, self.nudos, hom), d1, d2)
        (p0, k0, c0), (p1, k1, c1), (p2, k2, c2) = self._derivadas
        A = _evaluar(p0, k0, c0, t)
        A1 = _evaluar(p1, k1, c1, t)
        A2 = _evaluar(p2, k2, c2, t) if c2 else [0.0] * (self.dim + 1)
        d = self.dim
        w, w1, w2 = A[d], A1[d], A2[d]
        C = [A[j] / w for j in range(d)]
        D1 = [(A1[j] - w1 * C[j]) / w for j in range(d)]
        D2 = [(A2[j] - 2 * w1 * D1[j] - w2 * C[j]) / w for j in range(d)]
        return C, D1, D2

    def derivada(self, t: float) -> list[float]:
        """La primera derivada C'(t), exacta."""
        return self.derivadas(t)[1]

    # -- lo que piden el pintado y el osnap -----------------------------------
    def nudos_distintos(self) -> list[float]:
        a, b = self.dominio
        salida = [a]
        for k in self.nudos[self.grado + 1:len(self.control)]:
            if a < k < b and k > salida[-1]:
                salida.append(k)
        salida.append(b)
        return salida

    def teselar(self, flecha: float = FLECHA) -> list[list[float]]:
        """La poligonal que no se separa de la curva más de `flecha`.

        Se parte cada tramo de nudos en cuatro de salida (una cúbica cambia de
        curvatura dentro de un tramo) y luego se subdivide donde el arco queda
        más lejos que `flecha` de la cuerda. Es adaptativo: una curva casi recta
        sale con pocos vértices y una muy cerrada con muchos.
        """
        return [p for _, p in self._teselar_t(flecha)]

    def _teselar_t(self, flecha: float) -> list[tuple[float, list[float]]]:
        """Como `teselar`, pero cada vértice con su parámetro.

        Una curva **polinómica** (sin pesos, que son casi todas) se parte en
        segmentos de Bézier y cada uno se muestrea parejo, en bloque con numpy.
        Cuántas muestras no se adivina: para una Bézier de grado p, partida en m
        trozos iguales, la poligonal se separa de la curva a lo más
        p(p-1)/8 · max|Δ²P| / m², con Δ²P las segundas diferencias de sus puntos
        de control. De ahí sale m para la flecha pedida, con garantía. Hacerlo
        punto por punto en Python costaba nueve segundos en un plano de tres
        mil splines; así, una fracción.

        Una curva racional (círculos, cónicas) va por la subdivisión adaptativa,
        que no necesita cota."""
        flecha = max(flecha, 1e-9)
        if self.pesos is None:
            return self._teselar_bezier(flecha)
        return self._teselar_adaptativo(flecha)

    def _segmentos_bezier(self):
        """La curva partida en segmentos de Bézier: (t0s, t1s, puntos), con los
        grado+1 puntos de control de cada segmento en un arreglo de numpy
        (segmentos × (grado+1) × dim). Se calcula una vez por curva."""
        if self._bezier is not None:
            return self._bezier
        import numpy as np

        p = self.grado
        U = list(self.nudos)
        n = len(self.control)
        P = [list(c) + [1.0] for c in self.control] if self.pesos is None else \
            [[c[j] * w for j in range(self.dim)] + [w] for c, w in zip(self.control, self.pesos)]
        sujeta = U[0] == U[p] and U[n] == U[-1]
        # A5.6 supone nudos interiores de multiplicidad hasta p; uno repetido
        # más veces (una curva partida) va por el camino lento.
        interiores = U[p + 1:n]
        if sujeta and all(interiores.count(k) <= p for k in set(interiores)):
            t0s, t1s, Q = _descomponer(p, U, P)
        else:
            # Una cerrada (nudos sin repetir en las puntas): se inserta cada
            # nudo del dominio hasta multiplicidad p. Son pocas; vale la pena
            # la cuenta lenta para no complicar la rápida.
            a, b = self.dominio
            distintos = sorted({k for k in U if a <= k <= b})
            for u in distintos:
                while U.count(u) < p:
                    U, P = _insertar_nudo(p, U, P, u)
            t0s, t1s, Q = [], [], []
            for t0, t1 in zip(distintos, distintos[1:]):
                s = max(i for i, k in enumerate(U) if k == t0)
                t0s.append(t0)
                t1s.append(t1)
                Q.append(P[s - p:s + 1])
        H = np.asarray(Q, dtype=float)                  # segmentos × (p+1) × (dim+1)
        C = H[:, :, :self.dim] / H[:, :, self.dim:]
        self._bezier = (t0s, t1s, C)
        return self._bezier

    def _teselar_bezier(self, flecha: float):
        import numpy as np

        p = self.grado
        t0s, t1s, C = self._segmentos_bezier()
        S = len(t0s)
        if p >= 2:
            M = np.max(np.linalg.norm(C[:, 2:] - 2 * C[:, 1:-1] + C[:, :-2], axis=2), axis=1)
            m = np.ceil(np.sqrt(p * (p - 1) / 8.0 * M / flecha)).astype(int)
        else:
            m = np.ones(S, dtype=int)
        m = np.clip(m, 1, 4096)
        # Los segmentos que piden las mismas muestras se evalúan juntos: una
        # operación de numpy por grupo, no una por segmento.
        trozos = [None] * S
        for mi in np.unique(m).tolist():
            idx = np.nonzero(m == mi)[0]
            pts = np.einsum("jk,skd->sjd", _bernstein(p, mi), C[idx]).tolist()
            for k, i in enumerate(idx.tolist()):
                trozos[i] = (mi, pts[k])
        salida = []
        for i in range(S):
            mi, pts = trozos[i]
            t0, t1 = t0s[i], t1s[i]
            for j in range(0 if i == 0 else 1, mi + 1):
                salida.append((t0 + (t1 - t0) * j / mi, pts[j]))
        return salida

    def _teselar_adaptativo(self, flecha: float) -> list[tuple[float, list[float]]]:
        """Subdivisión donde el arco se separa de la cuerda más que `flecha`."""
        base = self.nudos_distintos()
        semillas = []
        for i in range(len(base) - 1):
            a, b = base[i], base[i + 1]
            for k in range(4):
                semillas.append(a + (b - a) * k / 4)
        semillas.append(base[-1])
        pts = [self.punto(t) for t in semillas]
        salida = [(semillas[0], pts[0])]
        for i in range(len(semillas) - 1):
            self._partir(semillas[i], pts[i], semillas[i + 1], pts[i + 1],
                         flecha, PROFUNDIDAD, salida)
        return salida

    def _partir(self, ta, pa, tb, pb, flecha, prof, salida):
        tm = (ta + tb) / 2
        pm = self.punto(tm)
        lejos = _distancia_a_segmento(pm, pa, pb) > flecha
        if not lejos and prof > 0:
            # Aunque el medio esté sobre la cuerda, los cuartos pueden no
            # estarlo (una S dentro del tramo). Se mira uno más por lado.
            lejos = (_distancia_a_segmento(self.punto((ta + tm) / 2), pa, pb) > flecha
                     or _distancia_a_segmento(self.punto((tm + tb) / 2), pa, pb) > flecha)
        if lejos and prof > 0:
            self._partir(ta, pa, tm, pm, flecha, prof - 1, salida)
            self._partir(tm, pm, tb, pb, flecha, prof - 1, salida)
        else:
            salida.append((tb, pb))

    def cercano(self, q) -> tuple[float, list[float]]:
        """El parámetro y el punto de la curva más cercanos a `q`.

        No se arranca de muestras uniformes en el parámetro: una curva que
        acelera recorre mucho espacio en poco parámetro, y ahí las muestras
        dejan huecos donde Newton cae en el mínimo equivocado (pasó con una CV
        de nueve puntos: 22 unidades de error). Se arranca del segmento más
        cercano de la teselación —que por construcción no deja huecos— y se
        afina con Newton sobre (C(t) - q)·C'(t) = 0 sin salirse del tramo.
        """
        q = list(q)[:self.dim] + [0.0] * max(0, self.dim - len(q))
        x0, y0, x1, y1 = self._caja_control()
        flecha = max(math.hypot(x1 - x0, y1 - y0) * 1e-3, 1e-9)
        tes = self._teselar_t(flecha)
        # Distancia de q a cada segmento de la teselación. El más cercano no
        # basta: donde la curva casi se toca a sí misma, el segmento de la otra
        # rama puede quedar más cerca que el de la rama buena (hasta `flecha`).
        # Se afinan todos los que caen dentro de ese margen.
        dist = []
        for i in range(len(tes) - 1):
            (_, pa), (_, pb) = tes[i], tes[i + 1]
            dist.append(_distancia_a_segmento(q, pa, pb))
        minimo = min(dist)
        candidatos = sorted((d, i) for i, d in enumerate(dist) if d <= minimo + 2 * flecha)[:8]
        mejor_t, mejor_d = tes[0][0], float("inf")
        for _, i in candidatos:
            lo = tes[max(0, i - 1)][0]
            hi = tes[min(len(tes) - 1, i + 2)][0]
            t, d = self._afinar(q, lo, hi)
            if d < mejor_d:
                mejor_t, mejor_d = t, d
        return mejor_t, self.punto(mejor_t)

    def _afinar(self, q, lo, hi) -> tuple[float, float]:
        """El mínimo de |C(t) - q| dentro de [lo, hi]: muestreo y Newton.

        Dentro de la ventana el parámetro no es proporcional al recorrido (la
        curva acelera y frena), así que no se interpola: se muestrea la ventana,
        que es corta, y Newton sólo afina alrededor de la mejor muestra.
        """
        MUESTRAS = 32
        paso = (hi - lo) / MUESTRAS
        ts = [lo + paso * k for k in range(MUESTRAS + 1)]
        ds = [_dist2(self.punto(t), q) for t in ts]
        # Cada mínimo local de las muestras se afina por su lado: dentro de la
        # misma ventana la curva puede hacer un lazo y pasar dos veces cerca.
        minimos = [k for k in range(len(ts))
                   if (k == 0 or ds[k] <= ds[k - 1]) and (k == len(ts) - 1 or ds[k] <= ds[k + 1])]
        mejor_t, mejor_d = ts[0], float("inf")
        for k in minimos:
            t, d = self._newton(q, ts[k], ds[k], max(lo, ts[k] - paso), min(hi, ts[k] + paso))
            if d < mejor_d:
                mejor_t, mejor_d = t, d
        return mejor_t, mejor_d

    def _newton(self, q, t, mejor_d, lo, hi) -> tuple[float, float]:
        """Newton sobre f(t) = (C(t) - q)·C'(t) = 0, con derivadas exactas."""
        for _ in range(40):
            c, d1, d2 = self.derivadas(t)
            r = [c[j] - q[j] for j in range(self.dim)]
            f = sum(r[j] * d1[j] for j in range(self.dim))
            gn = sum(d1[j] * d1[j] for j in range(self.dim))
            df = gn + sum(r[j] * d2[j] for j in range(self.dim))
            if df <= 0:
                # Junto a una cúspide la curvatura vuelve negativo el término
                # completo y Newton no sabe hacia dónde ir. Gauss-Newton (sólo
                # |C'|², siempre positivo) sí: baja despacio pero baja.
                df = gn
            if df <= 0:
                break
            # Si el paso empeora, se acorta a la mitad (hasta diez veces) en vez
            # de rendirse: cerca de la punta o de una curvatura fuerte, Newton
            # entero se pasa de largo.
            paso_n = -f / df
            for _ in range(10):
                nuevo = max(lo, min(hi, t + paso_n))
                dn = _dist2(self.punto(nuevo), q)
                if dn <= mejor_d:
                    break
                paso_n /= 2
            else:
                break
            convergio = abs(nuevo - t) <= (hi - lo) * 1e-13
            t, mejor_d = nuevo, dn
            if convergio:
                break
        return t, mejor_d

    def _caja_control(self):
        xs = [p[0] for p in self.control]
        ys = [p[1] if self.dim > 1 else 0.0 for p in self.control]
        return min(xs), min(ys), max(xs), max(ys)

    def longitud(self, flecha: float = 1e-4) -> float:
        pts = self.teselar(flecha)
        return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

    def caja(self) -> tuple[float, float, float, float]:
        """Caja en XY de los puntos de control: por la propiedad de la
        envolvente convexa contiene a la curva. Deja algo de aire en una curva
        muy jalada, y a cambio no hay que teselar para encuadrar: abrir un plano
        con tres mil splines pedía tres mil teselados sólo para esto."""
        return self._caja_control()

    # -- transformar ----------------------------------------------------------
    def transformada(self, f) -> "Nurbs":
        """La misma curva con `f` aplicada a sus puntos de control. Exacto para
        cualquier transformación afín (mover, rotar, escalar, espejo): una
        NURBS es invariante afín, que es la razón de guardar la curva así."""
        return Nurbs(self.grado, [f(p) for p in self.control], self.nudos, self.pesos)

    def tramo(self, t0: float, t1: float) -> "Nurbs":
        """El pedazo de la curva entre t0 y t1 (t0 < t1, dentro del dominio),
        como otra NURBS sujeta: la **misma** curva, no una aproximación.

        Se inserta cada punta hasta multiplicidad p (Boehm): ahí la curva pasa
        por un punto de control, y lo de en medio son los puntos y nudos del
        pedazo. Es como Rhino parte una curva al recortarla."""
        a, b = self.dominio
        t0, t1 = max(a, t0), min(b, t1)
        if not t0 < t1:
            raise ValueError("el tramo está vacío")
        p = self.grado
        U = list(self.nudos)
        P = [list(c) + [1.0] for c in self.control] if self.pesos is None else \
            [[c[j] * w for j in range(self.dim)] + [w] for c, w in zip(self.control, self.pesos)]
        for u in (t0, t1):
            while U.count(u) < p:
                U, P = _insertar_nudo(p, U, P, u)
        ultimo0 = max(i for i, k in enumerate(U) if k == t0)
        ia = ultimo0 - p + 1                     # las p copias de t0: U[ia .. ia+p-1]
        ib = min(i for i, k in enumerate(U) if k == t1)
        nudos = [t0] + U[ia:ib + p] + [t1]
        H = P[ia - 1:ib]
        control = [[q[j] / q[-1] for j in range(self.dim)] for q in H]
        pesos = [q[-1] for q in H] if self.pesos is not None else None
        return Nurbs(p, control, nudos, pesos)

    def seguida_de(self, otra: "Nurbs") -> "Nurbs":
        """Esta curva y luego `otra`, que empieza donde ésta termina, como una
        sola NURBS. Las dos deben ser sujetas y del mismo grado. En la unión
        queda un nudo de multiplicidad p: la curva pasa por ahí sin cambiar de
        forma (es lo que hace falta para abrir una cerrada por su costura)."""
        p = self.grado
        if otra.grado != p:
            raise ValueError("para seguirse, las dos curvas deben tener el mismo grado")
        if math.dist(self.control[-1], otra.control[0]) > 1e-9 * max(1.0, math.hypot(*self.control[-1][:2])):
            raise ValueError("la segunda curva no empieza donde termina la primera")
        corre = self.nudos[-1] - otra.nudos[0]
        nudos = self.nudos[:-1] + [k + corre for k in otra.nudos[p + 1:]]
        control = self.control + otra.control[1:]
        if self.pesos is None and otra.pesos is None:
            pesos = None
        else:
            w1 = self.pesos or [1.0] * len(self.control)
            w2 = otra.pesos or [1.0] * len(otra.control)
            k = w1[-1] / w2[0]            # mismos pesos en el punto que comparten
            pesos = w1 + [w * k for w in w2[1:]]
        return Nurbs(p, control, nudos, pesos)

    def a_dict(self) -> dict:
        d = {"grado": self.grado, "control": [list(p) for p in self.control],
             "nudos": list(self.nudos)}
        if self.pesos is not None:
            d["pesos"] = list(self.pesos)
        return d


# --- Constructores -----------------------------------------------------------

def sujeta_uniforme(control, grado: int = 3) -> Nurbs:
    """La B-spline por puntos de control **abierta**: arranca en el primero y
    termina en el último (nudos repetidos grado+1 veces en cada punta) y
    uniforme en medio. Es exactamente la que pintaba `_bspline` desde el 6-sep,
    así que una spline CV vieja no cambia de forma al abrirse."""
    control = [list(p) for p in control]
    n = len(control)
    if n < 2:
        raise ValueError("una spline necesita al menos dos puntos")
    k = max(1, min(grado, n - 1))
    interiores = n - k - 1
    nudos = ([0.0] * (k + 1)
             + [(i + 1) / (interiores + 1) for i in range(interiores)]
             + [1.0] * (k + 1))
    return Nurbs(k, control, nudos)


def periodica_uniforme(control, grado: int = 3) -> Nurbs:
    """La B-spline por puntos de control **cerrada**: el lazo da la vuelta sin
    esquina en la costura. Se repiten los primeros `grado` puntos al final y
    los nudos son uniformes sin repetir: así la curva es igual de suave en la
    costura que en cualquier otro lado.

    Lo que había antes (los mismos puntos repetidos, pero con nudos sujetos y
    un segmento recto para cerrar) dejaba un pico en el primer punto."""
    base = [list(p) for p in control]
    if len(base) > 1 and _dist2(base[0], base[-1]) < 1e-24:
        base = base[:-1]
    n = len(base)
    if n < 3:
        return sujeta_uniforme(base + base[:1], grado)
    k = max(1, min(grado, n - 1))
    pts = base + base[:k]
    m = len(pts)
    nudos = [float(i) for i in range(m + k + 1)]
    return Nurbs(k, pts, nudos)


def _parametros_cuerda(pts) -> list[float]:
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + math.dist(pts[i - 1], pts[i]))
    total = d[-1]
    if total <= 0:
        return [i / (len(pts) - 1) for i in range(len(pts))]
    return [v / total for v in d]


def _sin_repetidos(pts, tol=1e-9):
    salida = [list(pts[0])]
    for p in pts[1:]:
        if math.dist(p, salida[-1]) > tol:
            salida.append(list(p))
    return salida


def interpolar(ajuste, grado: int = 3) -> Nurbs:
    """La NURBS de grado `grado` que **pasa** por los puntos de ajuste, abierta.

    Interpolación global: parámetros por longitud de cuerda (el ritmo de la
    curva sigue la distancia entre puntos, no su número) y nudos por promedio
    de esos parámetros. Es el método de cuerda que también usan AutoCAD y
    Rhino por omisión; aun así, el DXF no depende de que coincidan: se escriben
    los puntos de control y los nudos que salen de aquí.
    """
    import numpy as np

    pts = _sin_repetidos([list(p) for p in ajuste])
    n = len(pts)
    if n < 2:
        raise ValueError("una spline necesita al menos dos puntos distintos")
    p = max(1, min(grado, n - 1))
    u = _parametros_cuerda(pts)
    nudos = [0.0] * (p + 1)
    for j in range(1, n - p):
        nudos.append(sum(u[j:j + p]) / p)
    nudos += [1.0] * (p + 1)
    # La matriz de las funciones base en cada parámetro.
    molde = Nurbs(p, pts, nudos)        # sólo para usar _tramo y _base
    A = np.zeros((n, n))
    for i, t in enumerate(u):
        s = molde._tramo(t)
        N = molde._base(s, t)
        for r in range(p + 1):
            A[i, s - p + r] = N[r]
    Q = np.array(pts, dtype=float)
    P = np.linalg.solve(A, Q)
    return Nurbs(p, P.tolist(), nudos)


def interpolar_cad(ajuste) -> Nurbs:
    """La spline por puntos de ajuste **abierta**, como la arma AutoCAD.

    Con los mismos puntos, la interpolación de libro (`interpolar`) y la de
    AutoCAD se separan hasta 55 unidades en una curva de un metro: AutoCAD
    cierra el sistema pidiendo curvatura cero en las puntas, siempre en grado
    3. Hasta 0.21.9 el DXF de shape101 llevaba sólo los puntos de ajuste, así
    que en AutoCAD esas splines siempre se vieron con este método; usarlo aquí
    también es lo que hace que una spline vieja abra en shape101 igual que
    en AutoCAD. La cuenta es de ezdxf (`fit_points_to_cad_cv`), que ya va
    dentro del programa.
    """
    from ezdxf.math import fit_points_to_cad_cv

    pts = _sin_repetidos([list(p)[:2] for p in ajuste])
    if len(pts) < 3:
        return interpolar(pts, 3)
    b = fit_points_to_cad_cv([(p[0], p[1], 0.0) for p in pts])
    return Nurbs(b.degree, [[v.x, v.y] for v in b.control_points], list(b.knots()))


def interpolar_cerrada(ajuste, grado: int = 3) -> Nurbs:
    """La NURBS que pasa por los puntos de ajuste y **se cierra suave** sobre el
    primero, sin pico en la costura.

    Es la interpolación periódica: los parámetros por cuerda dan la vuelta
    completa (incluido el tramo de regreso al primer punto), los nudos son esos
    mismos parámetros repetidos con su periodo, y el sistema se resuelve
    cíclico. Los primeros `grado` puntos de control se repiten al final.
    """
    import numpy as np

    pts = _sin_repetidos([list(p) for p in ajuste])
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-9:
        pts = pts[:-1]
    n = len(pts)
    if n < 3:
        return interpolar(pts + pts[:1], grado)
    p = max(1, min(grado, n - 1))
    cerrado = pts + pts[:1]
    u = _parametros_cuerda(cerrado)[:-1]      # n parámetros en [0, 1)
    L = 1.0

    def U(j):
        vueltas, r = divmod(j, n)
        return u[r] + vueltas * L

    m = n + p                                  # puntos de control con la vuelta
    nudos = [U(k - p) for k in range(m + p + 1)]
    molde = Nurbs(p, [[0.0] * len(pts[0])] * m, nudos)
    A = np.zeros((n, n))
    for i, t in enumerate(u):
        s = molde._tramo(t)
        N = molde._base(s, t)
        for r in range(p + 1):
            A[i, (s - p + r) % n] += N[r]
    Q = np.array(pts, dtype=float)
    P = np.linalg.solve(A, Q).tolist()
    # Los nudos de la vuelta anterior salen negativos. La curva es la misma con
    # todos corridos, y hay lectores de DXF que no esperan un nudo bajo cero.
    base = nudos[0]
    return Nurbs(p, P + P[:p], [k - base for k in nudos])


# --- Utilidades ---------------------------------------------------------------

def _descomponer(p, U, P):
    """Una NURBS sujeta partida en segmentos de Bézier, en una sola pasada
    (Piegl y Tiller, «The NURBS Book», algoritmo A5.6). P en homogéneas.
    Devuelve los t de inicio y fin de cada segmento y sus puntos."""
    n = len(P) - 1
    m = n + p + 1
    dim = len(P[0])
    a, b = p, p + 1
    Q = [[list(P[i]) for i in range(p + 1)]]
    t0s = []
    t1s = []
    alfas = [0.0] * (p + 1)
    while b < m:
        i = b
        while b < m and U[b + 1] == U[b]:
            b += 1
        mult = b - i + 1
        actual = Q[-1]
        siguiente = [[0.0] * dim for _ in range(p + 1)] if b < m else None
        if mult < p:
            numer = U[b] - U[a]
            for j in range(p, mult, -1):
                alfas[j - mult - 1] = numer / (U[a + j] - U[a])
            r = p - mult
            for j in range(1, r + 1):
                guardar = r - j
                s = mult + j
                for k in range(p, s - 1, -1):
                    al = alfas[k - s]
                    actual[k] = [al * actual[k][d] + (1 - al) * actual[k - 1][d] for d in range(dim)]
                if siguiente is not None:
                    siguiente[guardar] = list(actual[p])
        t0s.append(U[a])
        t1s.append(U[b])
        if siguiente is not None:
            for k in range(p - mult, p + 1):
                siguiente[k] = list(P[b - p + k])
            Q.append(siguiente)
            a = b
            b += 1
    return t0s, t1s, Q


def _insertar_nudo(p, U, P, u):
    """Inserta el nudo u una vez (Boehm): la misma curva, un punto de control
    más. P va en coordenadas homogéneas."""
    k = max(i for i in range(len(U) - 1) if U[i] <= u and u < U[i + 1]) \
        if u < U[-1] else max(i for i in range(len(U)) if U[i] < u)
    mult = U.count(u)
    Q = [list(q) for q in P[:k - p + 1]]
    for i in range(k - p + 1, k - mult + 1):
        den = U[i + p] - U[i]
        al = 0.0 if den == 0 else (u - U[i]) / den
        Q.append([al * P[i][j] + (1 - al) * P[i - 1][j] for j in range(len(P[0]))])
    Q += [list(q) for q in P[k - mult:]]
    return U[:k + 1] + [u] + U[k + 1:], Q


_BERNSTEIN: dict = {}


def _bernstein(p: int, m: int):
    """La matriz (m+1) × (p+1) de las bases de Bernstein en u = j/m."""
    clave = (p, m)
    B = _BERNSTEIN.get(clave)
    if B is None:
        import numpy as np
        u = np.linspace(0.0, 1.0, m + 1)[:, None]
        i = np.arange(p + 1)[None, :]
        coef = np.array([math.comb(p, k) for k in range(p + 1)], dtype=float)[None, :]
        B = coef * u ** i * (1 - u) ** (p - i)
        if len(_BERNSTEIN) > 512:
            _BERNSTEIN.clear()
        _BERNSTEIN[clave] = B
    return B


def _hodografa(p, nudos, control):
    """La derivada de una B-spline (no racional) de grado p: otra de grado p-1
    con los nudos sin sus puntas y Q_i = p (P_{i+1} - P_i) / (u_{i+p+1} - u_{i+1})."""
    q = []
    for i in range(len(control) - 1):
        den = nudos[i + p + 1] - nudos[i + 1]
        f = 0.0 if den == 0 else p / den
        q.append([f * (control[i + 1][j] - control[i][j]) for j in range(len(control[0]))])
    return p - 1, nudos[1:-1], q


def _evaluar(p, nudos, control, t):
    """Una B-spline no racional cualquiera (grado 0 incluido) en t."""
    n = len(control)
    if n == 0:
        return []
    a, b = nudos[p], nudos[n]
    t = max(a, min(b, t))
    # Tramo: el último con nudos[s] <= t, dentro de [p, n-1] y no vacío.
    s = p
    while s < n - 1 and nudos[s + 1] <= t and not (t >= b and nudos[s + 1] >= b):
        s += 1
    N = [1.0] + [0.0] * p
    izq = [0.0] * (p + 1)
    der = [0.0] * (p + 1)
    for j in range(1, p + 1):
        izq[j] = t - nudos[s + 1 - j]
        der[j] = nudos[s + j] - t
        guardado = 0.0
        for r in range(j):
            den = der[r + 1] + izq[j - r]
            temp = 0.0 if den == 0 else N[r] / den
            N[r] = guardado + der[r + 1] * temp
            guardado = izq[j - r] * temp
        N[j] = guardado
    d = len(control[0])
    out = [0.0] * d
    for i in range(p + 1):
        c = control[s - p + i]
        for j in range(d):
            out[j] += N[i] * c[j]
    return out


def _dist2(a, b) -> float:
    return sum((a[i] - b[i]) ** 2 for i in range(min(len(a), len(b))))


def _distancia_a_segmento(q, a, b) -> float:
    d = len(a)
    ab = [b[i] - a[i] for i in range(d)]
    aq = [q[i] - a[i] for i in range(d)]
    l2 = sum(v * v for v in ab)
    if l2 == 0:
        return math.sqrt(sum(v * v for v in aq))
    t = max(0.0, min(1.0, sum(ab[i] * aq[i] for i in range(d)) / l2))
    return math.sqrt(sum((aq[i] - t * ab[i]) ** 2 for i in range(d)))
