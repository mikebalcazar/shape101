"""El historial regenerable de un cuerpo 3D.

Un cuerpo no guarda geometría: guarda **cómo se hizo**. Una lista de
operaciones en JSON que se vuelve a ejecutar cuando algo cambia. Por eso se
puede mover un punto del boceto y que el sólido entero se rehaga bien, en vez
de quedar con una cara estirada y el resto igual.

Cada operación trae un **id** propio y estable. Las que consumen a otra la
señalan por ese id y no por su lugar en la lista (ver «la identidad de cada
operación», más abajo).

Operaciones:
  {"id": "0", "op": "boceto",   "entidades": [...las del dibujo...]}
  {"id": "1", "op": "extruir",  "mm": 18, "perfil": "0"}   sin «perfil»: el boceto de antes
  {"id": "2", "op": "restar",   "entidades": [...], "mm": 18}  barreno/cajeado: se extruye y se resta
  {"id": "3", "op": "redondear", "aristas": ["lado[0]|lado[1]", ...], "r": 20}
  {"id": "4", "op": "empujar_cara", "cara": "arriba", "mm": 10}  positivo = hacia afuera
  {"id": "5", "op": "mover_vertice", "vertice": "abajo|lado[0]|lado[3]", "d": [dx, dy, dz]}
  {"id": "6", "op": "mover_arista",  "arista": "lado[1]|arriba",         "d": [dx, dy, dz]}

Las referencias a caras y aristas son **nombres por derivación**
(`nombres.py`): así una cota del boceto puede cambiar y «arriba», «lado[2]» o
«lado[1]|lado[2]» siguen significando lo mismo. Sin eso, jalar una cara después
de editar el boceto jala la cara equivocada, que es el error clásico de los
modeladores con historial y la razón de que este módulo exista.

Viene de la 0.2.0, el camino que se desechó. Lo que se desechó fue la app, no
el motor: esto estaba escrito y medido. Lo único que se le quitó al traerlo fue
el lector de archivos `.t101d` sueltos —aquí las entidades salen del dibujo que
está abierto, no de un archivo aparte—.
"""
from __future__ import annotations

import json
import pathlib
import time

from build123d import Axis, Face, Wire, extrude, fillet, loft, revolve, sweep

from core.solido import boceto, nombres, planos, remallar


class Regenerado:
    def __init__(self, solido, nombrador: nombres.Nombrador, tiempos: list[dict], estado=None):
        self.solido = solido
        self.nombrador = nombrador
        self.tiempos = tiempos          # [{op, ms}]
        self.estado = estado

    @property
    def ms(self) -> float:
        return sum(t["ms"] for t in self.tiempos)


def _entidades(op: dict) -> list[dict]:
    if "entidades" in op:
        return op["entidades"]
    raise ValueError("un boceto lleva sus entidades adentro")


OPERACIONES = {"boceto", "extruir", "revolver", "barrer", "loft", "extruir_cara",
               "restar", "redondear", "empujar_cara",
               "mover_vertice", "mover_arista"}


# --- la identidad de cada operación  ·  0.19.0 ------------------------------
#
# Hasta la 0.18.0 una operación se señalaba por su **lugar** en la lista. Eso
# alcanza mientras el historial sea una fila —boceto, extruir, barreno,
# redondeo— y cada paso use lo que dejó el anterior. Deja de alcanzar en
# cuanto una operación necesita **más de una entrada**:
#
#     loft      N perfiles a la vez
#     barrer    un perfil **y** un camino
#     revolver  un perfil **y** un eje
#
# Con la lista plana lo único que se podía decir era «el boceto que quedó
# pendiente», y pendiente sólo puede haber uno. Con un id se puede decir cuál.
#
# De paso se arregla algo que ya estaba mal: los nombres derivados llevaban el
# **índice** adentro —`restar[2]/lado[1]`—, así que meter un paso a la mitad
# renombraba caras que nadie había tocado. Ahora llevan el id, que no se mueve
# aunque la lista crezca por arriba.
#
# Los archivos de antes no se rompen. A una operación sin id se le pone el
# número que ya tenía —la de la posición 2 se queda con el id `"2"`—, así que
# `restar[2]/lado[1]` sigue significando exactamente lo mismo que significaba.
# Los ids nuevos tienen otra forma (`o7`) y por eso jamás chocan con los
# heredados.

# Dónde puede una operación nombrar a otra. Una clave por línea y no un
# `op.values()` a lo bruto: un texto que *parece* un id —el nombre de una cara,
# por ejemplo— no debe contar como referencia.
REFERENCIA_UNA = ("perfil", "camino", "sobre")
REFERENCIA_VARIAS = ("perfiles",)


def _ids_usados(operaciones) -> set:
    fuera = set()
    for op in operaciones:
        k = op.get("id")
        if k not in (None, ""):
            fuera.add(str(k))
    return fuera


def id_libre(operaciones, prefijo: str = "o") -> str:
    """Un id que no esté usado en esta lista."""
    usados = _ids_usados(operaciones)
    k = len(operaciones) + 1
    while f"{prefijo}{k}" in usados:
        k += 1
    return f"{prefijo}{k}"


def asegurar_ids(operaciones: list) -> list[dict]:
    """Una copia de la lista donde **toda** operación trae su `id`.

    Se llama en cada puerta de entrada —al regenerar y al armar operaciones
    nuevas— para que nunca circule una lista a medias. Es barato y quita de en
    medio la pregunta «¿ésta ya tiene id?».
    """
    ops = json.loads(json.dumps(list(operaciones)))
    vistos: set = set()
    for i, op in enumerate(ops):
        k = op.get("id")
        k = None if k in (None, "") else str(k)
        if k is None or k in vistos:          # sin id, o repetido a mano
            # Los ids de más adelante están apartados: si a la operación 2 le
            # falta el id y la 5 ya se llama "2", inventarle "2" a ésta le
            # robaría el nombre a la otra y se caerían las referencias.
            apartados = vistos | _ids_usados(ops[i + 1:])
            k = str(i)
            n = 1
            while k in apartados:
                k, n = f"o{n}", n + 1
        op["id"] = k
        vistos.add(k)
    return ops


def referencias_de(op: dict) -> set:
    """A qué otras operaciones señala ésta."""
    fuera = set()
    for clave in REFERENCIA_UNA:
        v = op.get(clave)
        if v not in (None, ""):
            fuera.add(str(v))
    for clave in REFERENCIA_VARIAS:
        for v in (op.get(clave) or []):
            if v not in (None, ""):
                fuera.add(str(v))
    return fuera


def quien_usa(operaciones: list, id_: str) -> list[str]:
    """Los ids de las operaciones que señalan a ésa. Vacío si nadie.

    Cuenta también lo **sobreentendido**: un `extruir` sin «perfil» usa el
    último boceto pendiente, aunque no lo diga. Así están guardados todos los
    archivos de antes de la 0.19.0, y sobreentendido no se puede comprobar si
    no se hace explícito en algún lado. Ese lado es éste.
    """
    id_ = str(id_)
    return [k for k, usa in enlaces(operaciones).items() if id_ in usa]


# Las que hacen un cuerpo de la nada a partir de uno o varios bocetos. La
# primera de éstas es el nacimiento de la pieza y no se puede quitar.
CREAN_SOLIDO = ("extruir", "revolver", "barrer", "loft")

# De ésas, las que se conforman con **el boceto de antes** si no dicen cuál.
# `loft` no está: un loft sin decir qué perfiles no significa nada.
CONSUMEN_PERFIL = ("extruir", "revolver", "barrer")


def enlaces(operaciones: list) -> dict:
    """`{id: los ids que usa}`, con lo sobreentendido ya resuelto."""
    ops = asegurar_ids(operaciones)
    fuera: dict = {}
    pendiente = None
    for op in ops:
        usa = referencias_de(op)
        clase = op.get("op")
        if clase in CONSUMEN_PERFIL and op.get("perfil") in (None, ""):
            if pendiente is not None:
                usa.add(pendiente)
            pendiente = None
        elif clase in CONSUMEN_PERFIL:
            pendiente = None
        if clase == "boceto":
            pendiente = str(op["id"])
        fuera[str(op["id"])] = usa
    return fuera


def nace_el_solido(operaciones: list) -> str | None:
    """El id de la operación que hace el sólido de la nada. Sin ella no hay
    pieza, y por eso es la única que no se puede quitar por sí misma."""
    for op in asegurar_ids(operaciones):
        if op.get("op") in CREAN_SOLIDO:
            return str(op["id"])
    return None


class Estado:
    def __init__(self):
        self.solido = None
        self.nom = nombres.Nombrador()
        self.boceto_pendiente = None
        self.tiempos: list[dict] = []
        self.ops: list[dict] = []
        # Cada boceto que ya pasó, por su id. `boceto_pendiente` sigue ahí para
        # los archivos de antes, que no dicen de cuál hablan; esto es para los
        # que sí lo dicen, y para las operaciones que necesitan dos.
        self.bocetos: dict[str, dict] = {}


def _perfil_de(est: "Estado", op: dict, i: int) -> dict:
    """El boceto que esta operación consume: sus entidades y su plano.

    Si la operación dice cuál —`"perfil": "s1"`—, ése, aunque haya veinte
    bocetos antes. Si no lo dice, el último que quedó pendiente: así se
    trabajó hasta la 0.18.0 y así están guardados los archivos de entonces.
    """
    ref = op.get("perfil")
    if ref in (None, ""):
        if est.boceto_pendiente is None:
            raise ValueError(f"op {i}: {op.get('op')} sin boceto antes")
        return est.boceto_pendiente
    perfil = est.bocetos.get(str(ref))
    if perfil is None:
        raise ValueError(f"op {i}: no hay un boceto «{ref}» antes de esta operación")
    return perfil


def _papel(op: dict) -> dict:
    """Un boceto suelto —el círculo que trae un barreno adentro— visto como
    perfil, para que todo lo de abajo trate igual a los dos casos."""
    return {"entidades": _entidades(op), "plano": op.get("plano")}


def _en_su_plano(est: "Estado", perfil: dict):
    """La cara y las aristas del boceto, ya puestas donde viven.

    El boceto se dibuja siempre en papel plano —(u, v)— y el plano dice dónde
    cae ese papel. Devuelve también la perpendicular del papel, que es hacia
    donde extruye y la que decide cuál cara es «arriba».
    """
    from build123d import Vector

    ents = perfil["entidades"]
    cara = boceto.cara_de(ents)
    aristas = [a for e in ents for a in boceto.aristas_de(e)]
    spec = perfil.get("plano")
    if planos.es_el_suelo(spec):
        return cara, aristas, Vector(0, 0, 1)
    pl = planos.plano_de(spec, est.nom, est.solido)
    return (pl.from_local_coords(cara),
            [pl.from_local_coords(a) for a in aristas],
            Vector(pl.z_dir))


def _alambre_en_su_plano(est: "Estado", perfil: dict) -> "Wire":
    """El camino de un barrido: un boceto **abierto**, puesto en su plano.

    Va aparte de `_en_su_plano` porque un camino no es una cara: `cara_de` se
    negaría por no cerrar, y con razón. Un camino que cierra también vale —un
    anillo—, sólo que aquí nunca se le pide que cierre.
    """
    ents = perfil["entidades"]
    aristas = [a for e in ents for a in boceto.aristas_de(e)]
    if not aristas:
        raise ValueError("el camino de un barrido no trae geometría")
    spec = perfil.get("plano")
    if not planos.es_el_suelo(spec):
        pl = planos.plano_de(spec, est.nom, est.solido)
        aristas = [pl.from_local_coords(a) for a in aristas]
    return Wire(aristas)


def _eje_de(est: "Estado", op: dict, perfil: dict) -> "Axis":
    """El eje de giro de un revolucionado.

    Dos maneras de decirlo, y las dos hacen falta:

      "eje": {"a": [u0, v0], "b": [u1, v1]}        en el papel del boceto
      "eje": {"origen": [x,y,z], "direccion": [...]}   en el espacio

    La primera es como se trabaja: el eje se traza en el mismo dibujo que el
    perfil, y si el boceto se mueve de plano el eje se va con él. La segunda
    es para cuando el eje no está en el papel. Sin decir nada, el eje es la
    vertical del papel por su origen, que es el caso de la mayoría de las
    piezas torneadas.
    """
    from build123d import Vector

    spec = op.get("eje") or {}
    if "direccion" in spec or "origen" in spec:
        o = Vector(*planos._vec(spec.get("origen", [0, 0, 0])))
        d = Vector(*planos._vec(spec.get("direccion", [0, 1, 0])))
        if d.length < 1e-12:
            raise ValueError("el eje de un revolucionado no puede tener dirección cero")
        return Axis(o, d)
    a = planos._vec(spec.get("a", [0, 0]), 2) + (0.0,)
    b = planos._vec(spec.get("b", [0, 1]), 2) + (0.0,)
    pl = planos.plano_de(perfil.get("plano"), est.nom, est.solido)
    pa, pb = pl.from_local_coords(Vector(*a)), pl.from_local_coords(Vector(*b))
    d = pb - pa
    if d.length < 1e-12:
        raise ValueError("el eje de un revolucionado necesita dos puntos distintos")
    return Axis(pa, d)


def _paso(est: Estado, i: int, op: dict) -> None:
    t0 = time.perf_counter()
    clase = op["op"]
    nom, solido = est.nom, est.solido
    if clase == "boceto":
        est.boceto_pendiente = {"entidades": _entidades(op), "plano": op.get("plano")}
        est.bocetos[str(op["id"])] = est.boceto_pendiente
    elif clase == "extruir":
        perfil = _perfil_de(est, op, i)
        cara, aristas_b, normal = _en_su_plano(est, perfil)
        solido = extrude(cara, amount=op["mm"])
        nom.bautizar_extrusion(solido, aristas_b, op["mm"], normal=normal)
        est.boceto_pendiente = None
    elif clase == "revolver":
        # Torneado: el perfil gira alrededor de un eje. Lo que sale es un
        # cuerpo nuevo, no una modificación del que hubiera.
        perfil = _perfil_de(est, op, i)
        cara, _, _ = _en_su_plano(est, perfil)
        eje = _eje_de(est, op, perfil)
        grados = float(op.get("grados", 360.0))
        if not (0 < grados <= 360):
            raise ValueError("un revolucionado gira entre 0 y 360 grados")
        solido = revolve(cara, eje, revolution_arc=grados)
        nom.bautizar_cuerpo(solido, eje=(eje.direction.X, eje.direction.Y, eje.direction.Z))
        est.boceto_pendiente = None
    elif clase == "barrer":
        # El perfil recorre un camino. Perfil **y** camino: la razón por la
        # que las operaciones necesitaban id.
        perfil = _perfil_de(est, op, i)
        ref = op.get("camino")
        if ref in (None, ""):
            raise ValueError(f"op {i}: un barrido necesita decir por qué camino («camino»)")
        cam = est.bocetos.get(str(ref))
        if cam is None:
            raise ValueError(f"op {i}: no hay un boceto «{ref}» antes de esta operación")
        cara, _, _ = _en_su_plano(est, perfil)
        camino = _alambre_en_su_plano(est, cam)
        solido = sweep(cara, path=camino)
        arranque = camino.start_point()
        remate = camino.end_point()
        nom.bautizar_cuerpo(solido, eje=(remate.X - arranque.X, remate.Y - arranque.Y,
                                         remate.Z - arranque.Z))
        est.boceto_pendiente = None
    elif clase == "loft":
        # Varias secciones y una piel que pasa por todas. N perfiles a la vez:
        # la otra razón por la que hacían falta los ids.
        refs = [str(k) for k in (op.get("perfiles") or [])]
        if len(refs) < 2:
            raise ValueError(f"op {i}: un loft necesita al menos dos perfiles")
        caras = []
        for ref in refs:
            perfil = est.bocetos.get(ref)
            if perfil is None:
                raise ValueError(f"op {i}: no hay un boceto «{ref}» antes de esta operación")
            caras.append(_en_su_plano(est, perfil)[0])
        solido = loft(caras, ruled=bool(op.get("reglado", False)))
        a, b = caras[0].center(), caras[-1].center()
        nom.bautizar_cuerpo(solido, eje=(b.X - a.X, b.Y - a.Y, b.Z - a.Z))
        est.boceto_pendiente = None
    elif clase == "extruir_cara":
        # Mike, 19-sep: «extrude face es un sólido nuevo a partir de una cara
        # nueva. no sería estirar la cara, sería aumentar un sólido a partir
        # del perfil de la cara». Por eso se **suma**: la cara se queda donde
        # está y encima nace material.
        if solido is None:
            raise ValueError(f"op {i}: extruir_cara sin una pieza antes")
        cara = nom.cara(op["cara"])
        mm = float(op.get("mm", 0))
        if mm == 0:
            raise ValueError("una extrusión de cero no hace nada")
        pieza = extrude(cara, amount=mm)
        nom_p = nombres.Nombrador()
        n = cara.normal_at()
        nom_p.bautizar_extrusion(pieza, list(cara.edges()), mm,
                                 prefijo=f"crecer[{op['id']}]/", normal=n)
        solido = solido + pieza if op.get("unir", True) else pieza
        nom.rebautizar(solido, nuevas=nom_p.caras)
    elif clase == "restar":
        # Las entidades pueden venir adentro —un barreno se guarda con su
        # círculo— o señalar a un boceto de antes.
        perfil = _papel(op) if "entidades" in op else _perfil_de(est, op, i)
        cara, aristas_b, normal = _en_su_plano(est, perfil)
        herramienta = extrude(cara, amount=op["mm"])
        nom_h = nombres.Nombrador()
        nom_h.bautizar_extrusion(herramienta, aristas_b, op["mm"], prefijo=f"restar[{op['id']}]/", normal=normal)
        solido = solido - herramienta
        nom.rebautizar(solido, nuevas=nom_h.caras)
    elif clase == "redondear":
        aristas = [nom.arista(solido, a) for a in op["aristas"]]
        nuevo = fillet(aristas, radius=op["r"])
        candidatas = [f for f in nuevo.faces() if nom.nombre_de(f) is None]
        nuevas = {f"redondeo[{op['id']}]/{na}": f for na, f in zip(op["aristas"], _ordenar_redondeos(candidatas, aristas))}
        solido = nuevo
        nom.rebautizar(solido, nuevas=nuevas)
    elif clase == "empujar_cara":
        cara = nom.cara(op["cara"])
        mm = op["mm"]
        if mm != 0:
            if mm > 0:
                pieza = extrude(cara, amount=abs(mm))
                solido = solido + pieza
                movida = Face(pieza.faces().sort_by(lambda f: f.normal_at().dot(cara.normal_at()))[-1].wrapped)
            else:
                pieza = extrude(cara, amount=-abs(mm))
                solido = solido - pieza
                movida = Face(pieza.faces().sort_by(lambda f: f.normal_at().dot(cara.normal_at()))[0].wrapped)
            nom.rebautizar(solido, nuevas={"__movida__": movida}, heredan={op["cara"]: "__movida__"})
    elif clase in ("mover_vertice", "mover_arista"):
        # Mover un punto o una arista del **sólido**, no del boceto.
        #
        # Mike lo pidió así el 19-sep: cada punto y cada arista independientes.
        # Que apunten a un nombre y no a un índice es lo que hace que esto siga
        # siendo un historial: cambias una cota del boceto y la esquina que
        # jalaste sigue siendo esa esquina.
        if solido is None:
            raise ValueError(f"op {i}: {clase} sin una pieza antes")
        d = op.get("d") or [0, 0, 0]
        if clase == "mover_vertice":
            v = nom.vertice(solido, op["vertice"])
            puntos = [remallar.punto_de(v)]
        else:
            a = nom.arista(solido, op["arista"])
            puntos = [remallar.punto_de(a.start_point()), remallar.punto_de(a.end_point())]
        if not all(abs(k) < 1e-9 for k in d):       # mover cero no es mover
            # Por `nombres_en`, no por `nombre_de`: una cara que ya se alabeó
            # en una edición anterior es una superficie reglada, y por
            # superficie no se reconocería. Medido el 19-sep: con `nombre_de`,
            # la segunda edición encadenada dejaba a `lado[1]` sin nombre y con
            # él se iban sus cuatro aristas y cuatro de los ocho vértices.
            porIndice = nom.nombres_en(solido)
            viejos = [porIndice[k] for k in range(len(solido.faces()))]
            solido, caras, _ = remallar.mover(solido, [(p, tuple(d)) for p in puntos], viejos)
            nom.caras = caras
    else:
        raise ValueError(f"op {i}: no conozco «{clase}»")
    est.solido = solido
    est.ops.append(op)
    est.tiempos.append({"op": f"{i}:{clase}", "ms": (time.perf_counter() - t0) * 1000})


def regenerar(operaciones: list[dict]) -> Regenerado:
    """Desde cero, siempre. La caché por operación vive en el cuerpo."""
    est = Estado()
    for i, op in enumerate(asegurar_ids(operaciones)):
        _paso(est, i, op)
    return Regenerado(est.solido, est.nom, est.tiempos, est)


def extender(reg: "Regenerado", op: dict) -> Regenerado:
    """Una operación más sobre lo ya regenerado: lo que hace la app cuando lo
    que cambia es la última. Devuelve el mismo Regenerado, actualizado."""
    est = reg.estado
    op = dict(op)
    if op.get("id") in (None, ""):
        op["id"] = id_libre(est.ops)
    _paso(est, len(est.ops), op)
    reg.solido, reg.nombrador, reg.tiempos = est.solido, est.nom, est.tiempos
    return reg


def _ordenar_redondeos(caras_nuevas, aristas):
    """Cada cara de redondeo va con la arista que la produjo: la más cercana."""
    out = []
    restantes = list(caras_nuevas)
    for a in aristas:
        m = a.position_at(0.5)
        mejor = min(restantes, key=lambda f: (f.center() - m).length)
        restantes.remove(mejor)
        out.append(mejor)
    return out


def cargar(ruta) -> list[dict]:
    return json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))


def guardar(operaciones: list[dict], ruta) -> None:
    pathlib.Path(ruta).write_text(json.dumps(operaciones, ensure_ascii=False, indent=1), encoding="utf-8")
