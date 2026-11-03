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

from build123d import Axis, Face, Wire, chamfer, extrude, fillet, loft, revolve, sweep

from core.solido import boceto, nombres, planos, remallar, superficies


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
               "primitiva",
               "restar", "redondear", "chaflan", "empujar_cara", "red", "barrer2", "mover_polo",
               "mover_vertice", "mover_arista"}


# --- sólidos directos  ·  0.21.8 --------------------------------------------
#
# Mike, 25-sep: «necesito los comandos para generar sólidos directo (prisma,
# cilindro, pirámide, etc.)». Una primitiva es una operación de nacimiento sin
# boceto: se arma en el papel de su plano —(u, v) sobre el plano, w hacia la
# normal— apoyada en w = 0, y se lleva al mundo como cualquier boceto. Sus
# medidas son campos que se tocan en el historial, igual que el espesor de una
# extrusión.
FORMAS = ("caja", "cilindro", "cono", "esfera", "piramide")


def _primitiva(op: dict):
    """El sólido de una primitiva, en el papel de su plano (sin llevar)."""
    from build123d import Align, Box, Cone, Cylinder, Face, Pos, Sphere, Vertex, Wire, loft

    forma = op.get("forma")
    u, v = [float(k) for k in (op.get("base") or [0, 0])[:2]]
    alto = float(op.get("alto", 0) or 0)
    radio = float(op.get("radio", 0) or 0)
    ancho, fondo = float(op.get("ancho", 0) or 0), float(op.get("fondo", 0) or 0)
    abajo = (Align.MIN, Align.MIN, Align.MIN)
    centrado = (Align.CENTER, Align.CENTER, Align.MIN)
    if forma == "caja":
        if min(ancho, fondo, alto) <= 0:
            raise ValueError("un prisma necesita ancho, fondo y alto mayores que cero")
        s = Box(ancho, fondo, alto, align=abajo)
    elif forma == "cilindro":
        if radio <= 0 or alto <= 0:
            raise ValueError("un cilindro necesita radio y alto mayores que cero")
        s = Cylinder(radio, alto, align=centrado)
    elif forma == "cono":
        radio2 = float(op.get("radio2", 0) or 0)
        if radio <= 0 or alto <= 0 or radio2 < 0:
            raise ValueError("un cono necesita radio y alto mayores que cero")
        s = Cone(radio, radio2, alto, align=centrado)
    elif forma == "esfera":
        if radio <= 0:
            raise ValueError("una esfera necesita radio mayor que cero")
        s = Sphere(radio).moved(Pos(0, 0, radio))      # apoyada en el plano
    elif forma == "piramide":
        if min(ancho, fondo, alto) <= 0:
            raise ValueError("una pirámide necesita ancho, fondo y alto mayores que cero")
        base = Face(Wire.make_rect(ancho, fondo)).moved(Pos(ancho / 2, fondo / 2, 0))
        s = loft([base, Vertex(ancho / 2, fondo / 2, alto)])
    else:
        raise ValueError(f"no conozco la forma «{forma}»; valen {', '.join(FORMAS)}")
    return s.moved(Pos(u, v, 0))


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
REFERENCIA_VARIAS = ("perfiles", "bordes", "curvas")


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


def _una_sola_cara(cara, que: str):
    """Revolver, barrer y hacer un loft piden un solo contorno exterior: con
    dos piezas separadas no hay una forma clara de seguirlas."""
    from build123d import Face
    if not isinstance(cara, Face):
        raise ValueError(f"para {que} el boceto debe tener una sola pieza (un contorno exterior)")
    return cara


def _en_su_plano(est: "Estado", perfil: dict):
    """La cara y las aristas del boceto, ya puestas donde viven.

    El boceto se dibuja siempre en papel plano —(u, v)— y el plano dice dónde
    cae ese papel. Devuelve también la perpendicular del papel, que es hacia
    donde extruye y la que decide cuál cara es «arriba».
    """
    from build123d import Vector

    ents = boceto.soldadas(perfil["entidades"])
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
    ents = boceto.soldadas(perfil["entidades"])
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
        eje = _eje_de(est, op, perfil)
        grados = float(op.get("grados", 360.0))
        if not (0 < grados <= 360):
            raise ValueError("un revolucionado gira entre 0 y 360 grados")
        if op.get("superficie"):
            # Un perfil abierto gira y deja una superficie de revolución, no un
            # sólido (como el Revolve de Rhino con una curva abierta).
            solido = superficies.revolucion(_alambre_en_su_plano(est, perfil), eje, grados)
        else:
            cara, _, _ = _en_su_plano(est, perfil)
            cara = _una_sola_cara(cara, "revolver")
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
        camino = _alambre_en_su_plano(est, cam)
        if op.get("superficie"):
            solido = superficies.barrido(_alambre_en_su_plano(est, perfil), camino)
        else:
            cara, _, _ = _en_su_plano(est, perfil)
            cara = _una_sola_cara(cara, "barrer")
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
            if op.get("superficie"):
                caras.append(_alambre_en_su_plano(est, perfil))
            else:
                caras.append(_una_sola_cara(_en_su_plano(est, perfil)[0], "hacer un loft"))
        if op.get("superficie"):
            # Secciones abiertas: la piel es una superficie (fase D1).
            solido = superficies.loft(caras, reglado=bool(op.get("reglado", False)))
        else:
            solido = loft(caras, ruled=bool(op.get("reglado", False)))
        a, b = caras[0].center(), caras[-1].center()
        nom.bautizar_cuerpo(solido, eje=(b.X - a.X, b.Y - a.Y, b.Z - a.Z))
        est.boceto_pendiente = None
    elif clase == "red":
        # Superficie por su borde: varias curvas que cierran un lazo, y un
        # parche que pasa por todas (el NetworkSrf / EdgeSrf de Rhino, fase D1).
        refs = [str(k) for k in (op.get("bordes") or [])]
        if len(refs) < 2:
            raise ValueError(f"op {i}: una red necesita al menos dos curvas de borde")
        alambres = []
        for ref in refs:
            perfil = est.bocetos.get(ref)
            if perfil is None:
                raise ValueError(f"op {i}: no hay un boceto «{ref}» antes de esta operación")
            alambres.append(_alambre_en_su_plano(est, perfil))
        solido = superficies.red(alambres)
        nom.bautizar_cuerpo(solido, eje=(0, 0, 1))
        est.boceto_pendiente = None
    elif clase == "barrer2":
        # Barrido por dos rieles (fase D1b): tres curvas abiertas, en cualquier
        # orden. El perfil es la que toca a las otras dos con sus puntas; cada
        # riel se orienta para arrancar donde toca al perfil.
        refs = [str(k) for k in (op.get("curvas") or [])]
        if len(refs) != 3:
            raise ValueError(f"op {i}: un barrido por dos rieles quiere tres curvas: un perfil y dos rieles")
        alambres = []
        for ref in refs:
            perfil = est.bocetos.get(ref)
            if perfil is None:
                raise ValueError(f"op {i}: no hay un boceto «{ref}» antes de esta operación")
            alambres.append(_alambre_en_su_plano(est, perfil))
        from core import tolerancia
        tol = tolerancia.kernel_mm()
        perfil_w, riel1, riel2 = superficies.papeles_dos_rieles(alambres, tol)
        solido, _ = superficies.barrido_dos_rieles(perfil_w, riel1, riel2, tol / 10)
        nom.bautizar_cuerpo(solido, eje=(0, 0, 1))
        est.boceto_pendiente = None
    elif clase == "primitiva":
        # Un sólido de la nada, en el plano de la ventana donde se pidió.
        from build123d import Vector
        s = _primitiva(op)
        spec = planos.del_dibujo(op.get("plano"))
        if planos.es_el_suelo(spec):
            n = Vector(0, 0, 1)
        else:
            pl = planos.plano_de(spec, est.nom, est.solido)
            s = pl.from_local_coords(s)
            n = Vector(pl.z_dir)
        solido = s
        nom.bautizar_cuerpo(solido, eje=(n.X, n.Y, n.Z))
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
        try:
            nuevo = fillet(aristas, radius=op["r"])
        except Exception as exc:
            # El kernel sólo dice «falló, prueba uno menor», en inglés. Se le
            # pregunta cuál es el más grande que cabe y se dice ése.
            try:
                maximo = solido.max_fillet(aristas, tolerance=0.01, max_iterations=40)
            except Exception:
                maximo = None
            if maximo:
                raise ValueError(f"un redondeo de {op['r']} no cabe en esas aristas: "
                                 f"el más grande que cabe es {maximo:.2f}") from exc
            raise ValueError(f"un redondeo de {op['r']} no cabe en esas aristas") from exc
        candidatas = [f for f in nuevo.faces() if nom.nombre_de(f) is None]
        nuevas = {f"redondeo[{op['id']}]/{na}": f for na, f in zip(op["aristas"], _ordenar_redondeos(candidatas, aristas))}
        solido = nuevo
        nom.rebautizar(solido, nuevas=nuevas)
    elif clase == "chaflan":
        # El chaflán (fase C3): la arista se corta en plano a la distancia `d`
        # de cada cara, como el ChamferEdge de Rhino. Se nombra igual que un
        # redondeo, para que jalar o borrar después encuentre su cara.
        aristas = [nom.arista(solido, a) for a in op["aristas"]]
        d = float(op["d"])
        try:
            nuevo = chamfer(aristas, length=d)
        except Exception as exc:
            raise ValueError(f"un chaflán de {d} no cabe en esas aristas: el más grande que cabe "
                             f"es {_max_chaflan(aristas, d):.2f}") from exc
        candidatas = [f for f in nuevo.faces() if nom.nombre_de(f) is None]
        nuevas = {f"chaflan[{op['id']}]/{na}": f for na, f in zip(op["aristas"], _ordenar_redondeos(candidatas, aristas))}
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
    elif clase == "mover_polo":
        # Un punto de control de una superficie, corrido (fase D2). Como
        # mover_vertice, apunta a la cara por su nombre: si se cambia algo de
        # antes en el historial, el polo sigue siendo el de esa cara.
        if solido is None:
            raise ValueError(f"op {i}: mover_polo sin una superficie antes")
        if solido.solids():
            raise ValueError("los puntos de control se mueven en superficies, no en sólidos: "
                             "en un sólido abrirían la pieza")
        cara = nom.cara(op["cara"])
        d = [float(k) for k in (op.get("d") or [0, 0, 0])]
        if not all(abs(k) < 1e-12 for k in d):
            solido, nueva = superficies.mover_polo(solido, cara, int(op["i"]), int(op["j"]), d)
            nom.rebautizar(solido, nuevas={op["cara"]: nueva})
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


def _max_chaflan(aristas, d: float) -> float:
    """El chaflán más grande que cabe, por bisección: build123d no trae un
    max_chamfer como trae max_fillet. Doce intentos dan la centésima en una
    pieza de un metro."""
    bajo, alto = 0.0, d
    for _ in range(12):
        medio = (bajo + alto) / 2
        try:
            chamfer(aristas, length=medio)
            bajo = medio
        except Exception:
            alto = medio
    return bajo


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
