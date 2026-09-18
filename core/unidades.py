"""Traer un dibujo ajeno a milímetros  ·  shape101.

shape101 trabaja en **milímetros**. Los planos que le mandan al taller no
siempre. El primer DWG real que entró —un export de Revit, `I5103.dwg`— venía
en **metros** (`$INSUNITS = 6`), y sin darse cuenta el programa lo habría
tratado como milímetros: un mueble de 0.6 en vez de 600, una cota que dice «1»
donde debería decir «1000».

Ese error no truena, no se ve raro en pantalla —el dibujo se ve idéntico, sólo
cambia el número— y sale a la luz cuando alguien corta una pieza. Por eso el
archivo se convierte al abrirlo, y se avisa.

Se guarda el factor en el documento (`factor_unidades`) para poder deshacerlo al
exportar: si el plano vino en metros, se devuelve en metros. Cambiarle las
unidades a alguien en su propio archivo es tan grosero como devolvérselo sin
cotas.

**Los bloques no se tocan.** Su contenido está en las unidades del bloque; lo
que se escala es la `escala` de cada inserción. Es el mismo truco que usa
AutoCAD al insertar un dibujo de otras unidades, y evita tener que reescribir
176 definiciones de bloque para multiplicar por mil.
"""

from __future__ import annotations

#: Códigos $INSUNITS del DXF → cuántos milímetros vale una unidad.
#: Sólo los que aparecen en planos de arquitectura y de taller; el resto se
#: trata como «no sé» y no se toca nada, que es más seguro que adivinar.
MM_POR_UNIDAD = {
    1: 25.4,        # pulgadas
    2: 304.8,       # pies
    4: 1.0,         # milímetros  ← lo nuestro
    5: 10.0,        # centímetros
    6: 1000.0,      # metros
    8: 0.0254,      # micras
    9: 0.001,       # milésimas de pulgada
    10: 914.4,      # yardas
    13: 0.000001,   # nanómetros
    14: 0.0001,     # decímetros… (DXF los llama así)
}

#: Entre qué tamaños, ya en milímetros, es creíble un plano. Diez milímetros
#: es un herraje; medio kilómetro es un conjunto urbano. Fuera de ahí, el
#: encabezado miente.
SENSATO_MIN = 10.0
SENSATO_MAX = 500_000.0

#: Las unidades en que se puede **trabajar** (Mike, 7-sep-2026): nombre corto
#: → milímetros por unidad, y su código $INSUNITS.
MM_POR_NOMBRE = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
INSUNITS_POR_NOMBRE = {"mm": 4, "cm": 5, "m": 6}
NOMBRE_POR_INSUNITS = {4: "mm", 5: "cm", 6: "m"}
#: Decimales que pide una cota en cada unidad: 600 mm, 60.0 cm, 0.600 m.
DECIMALES_POR_NOMBRE = {"mm": 2, "cm": 1, "m": 3}

NOMBRE = {
    1: "pulgadas", 2: "pies", 4: "milímetros", 5: "centímetros",
    6: "metros", 8: "micras", 9: "milésimas de pulgada", 10: "yardas",
    13: "nanómetros", 14: "decímetros",
}

#: Campos de cada tipo de entidad que son **longitudes** y hay que escalar.
#: Los ángulos, los nombres, los estilos y las razones no llevan unidades.
PUNTOS = {          # listas de puntos [x, y] (o [x, y, bulge])
    "polilinea": ["puntos"],
    "spline": ["puntos_ajuste", "puntos_control"],
    "solido": ["puntos"],
    "cota": ["puntos"],
    "linea": ["p1", "p2"],          # puntos sueltos, se tratan aparte
}
PUNTO_SUELTO = {
    "linea": ["p1", "p2"],
    "circulo": ["centro"],
    "arco": ["centro"],
    "elipse": ["centro", "eje_mayor"],
    "punto": ["p"],
    "texto": ["p"],
    "textom": ["p"],
    "insercion": ["p"],
    "imagen": ["p"],
}
LISTA_DE_PUNTOS = {
    "polilinea": ["puntos"],
    "spline": ["puntos_ajuste", "puntos_control"],
    "solido": ["puntos"],
    "cota": ["puntos"],
}
LARGOS = {          # escalares que son longitudes
    "circulo": ["radio"],
    "arco": ["radio"],
    "texto": ["altura"],
    "textom": ["altura", "ancho"],
    "cota": ["medida"],
    "imagen": ["ancho", "alto"],
}


def _punto(p: list, k: float) -> list:
    """Escala un punto conservando el bulge, que no es una longitud."""
    fuera = [p[0] * k, p[1] * k]
    if len(p) > 2:
        fuera += list(p[2:])        # el bulge y lo que venga detrás, tal cual
    return fuera


def escalar_entidad(e, k: float) -> None:
    t = e.tipo
    for campo in PUNTO_SUELTO.get(t, []):
        v = getattr(e, campo, None)
        if v:
            setattr(e, campo, _punto(list(v), k))
    for campo in LISTA_DE_PUNTOS.get(t, []):
        v = getattr(e, campo, None)
        if v:
            setattr(e, campo, [_punto(list(p), k) for p in v])
    for campo in LARGOS.get(t, []):
        v = getattr(e, campo, None)
        if v:
            setattr(e, campo, float(v) * k)

    if t == "cruda":
        # El dibujo de apoyo se escala con ella; si no, la cota ajena se queda
        # mil veces más chica que el plano al que pertenece.
        e.dibujo = [[_punto(list(p), k) for p in linea] for linea in (e.dibujo or [])]
        for tx in (e.textos or []):
            tx["p"] = _punto(list(tx["p"]), k)
            if tx.get("altura"):
                tx["altura"] = float(tx["altura"]) * k
    elif t == "rayado":
        e.rutas = [[_punto(list(p), k) for p in ruta] for ruta in e.rutas]
    elif t == "insercion":
        # El bloque se queda en sus unidades; lo que crece es la inserción.
        e.escala = [e.escala[0] * k, e.escala[1] * k]


def a_milimetros(doc, insunits: int | None) -> dict:
    """Lleva el documento a milímetros. Devuelve qué se hizo, para el informe.

    Si no se reconoce la unidad —o ya está en milímetros— no se toca nada: en
    la duda, es mejor un plano con el tamaño del archivo que un plano con el
    tamaño que nosotros supusimos.
    """
    k = MM_POR_UNIDAD.get(insunits or 0)
    if k is None:
        return {"convertido": False, "motivo": "unidad desconocida",
                "insunits": insunits}
    if k == 1.0:
        return {"convertido": False, "motivo": "ya viene en milímetros",
                "insunits": insunits}

    # Freno de mano: hay archivos que declaran una unidad y están dibujados en
    # otra. `ezdxf.new()` sin más pone $INSUNITS = 6 (metros) aunque el dibujo
    # esté en milímetros — lo hacen nuestras propias pruebas — y hacerle caso
    # convertiría una línea de 1000 mm en una de un kilómetro.
    #
    # Un plano de arquitectura o de taller mide entre un centímetro y medio
    # kilómetro. Si la conversión deja algo fuera de esa horquilla, el que está
    # mal es el encabezado: se deja el dibujo como viene y se dice. Adivinar
    # menos es mejor que adivinar mal.
    ext = doc.extension()
    if ext:
        mayor = max(ext[2] - ext[0], ext[3] - ext[1]) * k
        if mayor > SENSATO_MAX or (mayor and mayor < SENSATO_MIN):
            return {"convertido": False, "insunits": insunits,
                    "motivo": "el encabezado no cuadra con el tamaño del dibujo",
                    "unidad": NOMBRE.get(insunits, f"código {insunits}"),
                    "medida_absurda": mayor}

    silencio = doc.historial.silencio
    doc.historial.silencio = True
    try:
        for e in doc.entidades.values():
            escalar_entidad(e, k)
    finally:
        doc.historial.silencio = silencio

    # Se tocaron las entidades por fuera de `Documento.modificar`: la caché de
    # teselado ya no vale nada.
    doc.olvidar()
    doc.factor_unidades = k
    return {"convertido": True, "factor": k, "insunits": insunits,
            "unidad": NOMBRE.get(insunits, f"código {insunits}")}


def cambiar(doc, nueva: str, escalar: bool = True) -> dict:
    """Cambia la unidad de trabajo del dibujo  ·  Mike, 7-sep-2026.

    Con `escalar` (lo normal) el dibujo conserva su tamaño real: la mesa de
    600 mm pasa a medir 0.6 m — se escalan entidades, ventanas de las hojas y
    estilos de cota, y las cotas pasan a los decimales de la unidad. Sin
    `escalar`, los números se quedan y sólo cambia lo que significan: es para
    el plano que se dibujó en metros con la unidad mal puesta.
    """
    nueva = str(nueva or "").lower()
    if nueva not in MM_POR_NOMBRE:
        raise ValueError(f"Unidad desconocida: {nueva!r}. Vale mm, cm o m.")
    vieja = doc.unidades if doc.unidades in MM_POR_NOMBRE else "mm"
    if nueva == vieja:
        return {"unidades": nueva, "factor": 1.0, "escalado": False}
    k = MM_POR_NOMBRE[vieja] / MM_POR_NOMBRE[nueva]      # unidades nuevas por unidad vieja
    if escalar:
        silencio = doc.historial.silencio
        doc.historial.silencio = True
        try:
            for e in doc.entidades.values():
                escalar_entidad(e, k)
            for lay in (doc.layouts or []):
                for v in (lay.get("ventanas") or []):
                    c = v.get("centro") or [0, 0]
                    v["centro"] = [c[0] * k, c[1] * k]
            for est in doc.estilos_cota.values():
                est["factor_escala"] = float(est.get("factor_escala", 1.0) or 1.0) * k
                est["decimales"] = DECIMALES_POR_NOMBRE[nueva]
        finally:
            doc.historial.silencio = silencio
        doc.olvidar()
    else:
        for est in doc.estilos_cota.values():
            est["decimales"] = DECIMALES_POR_NOMBRE[nueva]
    doc.unidades = nueva
    doc.sucio = True
    return {"unidades": nueva, "factor": k if escalar else 1.0, "escalado": bool(escalar)}
