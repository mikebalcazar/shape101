"""El documento: capas, bloques y entidades  ·  features 45-49 y 10.

Todo cambio pasa por aquí. Ninguna herramienta toca las listas directamente:
así el historial se entera de todo sin que cada herramienta se acuerde de
avisarle, y así el `.t101d` siempre guarda un estado coherente.
"""

from __future__ import annotations

import copy
from typing import Iterable

from . import capas as mod_capas
from . import config
from . import entidades as ent_mod
from .capas import Capa
from .entidades import Bloque, Entidad
from .historial import Historial, _Contexto


class CapaBloqueada(Exception):
    pass


class CapaEnUso(Exception):
    pass


ESTILO_TEXTO_T101 = {
    "nombre": "T101",
    "fuente": "Raleway",
    "archivo": "Raleway-400.ttf",
    "altura": 0.0,          # 0 = la altura la pone cada texto
    "ancho": 1.0,
    "oblicuo": 0.0,
}

ESTILO_COTA_T101 = {
    "nombre": "T101",
    "estilo_texto": "T101",
    # Las medidas del estilo son **milímetros de papel**, como el DIMTXT de
    # AutoCAD: lo que mide el texto impreso. Lo que se ve en el modelo es eso
    # multiplicado por `factor_escala` (el DIMSCALE).
    "altura_texto": 2.5,
    "flecha": "ARCHTICK",       # la palomita de arquitectura
    "tam_flecha": 2.5,          # igual que el texto, como pidió Mike
    "ext_linea": 1.25,          # cuánto sobresale la línea de extensión
    "hueco_origen": 0.625,      # separación entre la pieza y la línea
    "decimales": 0,             # el taller trabaja en milímetros enteros
    "sufijo": "",
    # 2.5 × 12 = 30 mm de texto en el dibujo, que es lo que Mike pidió ver
    # mientras traza. Con el 1.0 de antes el texto medía 2.5 mm dentro de un
    # plano de varios metros: no se leía sin acercarse hasta el ridículo.
    #
    # Se sube esto y no la altura porque al colocar el dibujo en una hoja el
    # motor ajusta este factor solo a la escala de la ventana (`papel.py`).
    # Con altura 30 y factor 20, una hoja a 1:20 sacaría letras de 60 cm.
    "factor_escala": 12.0,
}


class Documento:
    """Un dibujo completo."""

    def __init__(self, con_plantilla: bool = True):
        self.nombre = "Sin título"
        self.cliente = ""
        self.unidad = config.UNIDAD
        self.capas: dict[str, Capa] = mod_capas.plantilla() if con_plantilla else {"0": Capa("0")}
        self.capa_activa = "0"
        self.bloques: dict[str, Bloque] = {}
        self.entidades: dict[str, Entidad] = {}
        self.orden: list[str] = []          # orden de dibujo
        self.estilos_texto = {"T101": dict(ESTILO_TEXTO_T101)}
        self.estilos_cota = {"T101": dict(ESTILO_COTA_T101)}
        # Hojas de impresión  ·  F6. Viven en el documento, no en las
        # preferencias: el plano y su formato son la misma cosa, y quien recibe
        # el .t101d tiene que poder imprimirlo igual.
        self.layouts: list[dict] = []
        self.origen_t101x = None            # de qué proyecto de Taller 101 vino
        # Referencias externas del archivo: nombre del bloque → ruta que dice
        # el DWG. Es lo que permite ir a buscar el archivo y montar su dibujo
        # (ver `core/dxf_lector.py`, `_resolver_xrefs`).
        self.xrefs: dict[str, str] = {}
        # El DXF del que se abrió, si se abrió de uno. Es lo que permite
        # devolver el archivo con todo lo que no modelamos intacto.
        #
        # **No se guarda en memoria como texto.** El DWG de Mondelez son 222 MB
        # de DXF: tenerlos de cadena costaba 8 segundos al abrir y esos 222 MB
        # dentro del proceso, para algo que sólo se usa al exportar. Se guarda
        # el archivo en disco y se lee cuando hace falta (ver `origen_dxf`).
        self._origen_dxf: str | None = None
        self.origen_dxf_ruta: str | None = None
        # Si vino de un DWG, de cuál. El DXF de paso es un intermedio y no se
        # le enseña a nadie: lo que el taller recibió se llamaba .dwg.
        self.origen_dwg: str | None = None
        # Si el archivo venía en otra unidad, por cuánto se multiplicó para
        # traerlo a milímetros, y qué código $INSUNITS traía. Sirve para
        # devolverlo como vino: cambiarle las unidades a alguien en su propio
        # archivo es tan grosero como devolvérselo sin cotas.
        self.factor_unidades: float = 1.0
        self.insunits_origen: int | None = None
        # En qué unidad se dibuja: "mm" (lo de siempre), "cm" o "m". Todo lo
        # que se teclea, se ve y se acota va en esa unidad; el DXF sale con el
        # $INSUNITS que corresponde. Mike, 7-sep-2026. Ver core/unidades.py.
        self.unidades: str = "mm"
        self.historial = Historial()
        # La extensión del dibujo, guardada por espacio. Calcularla recorre
        # todas las entidades (250 ms en un plano de 15 000) y se pedía **dos
        # veces por operación**, moviera una línea o mil: era medio segundo de
        # espera fijo en cada cosa que se hacía. Se invalida sola: toda
        # mutación pasa por `sucio = True` (ver la propiedad abajo).
        self._extension_cache: dict[str, tuple | None] = {}
        self.sucio = False                  # hay cambios sin guardar
        # Qué tocó el último deshacer/rehacer, para poder repintar por parche.
        self.ultimos_tocados: list[str] = []
        self.ultimo_toco_capas = False
        # Caché de lo ya teselado, entidad por entidad. Ver `olvidar()`.
        self.cache: dict[str, dict] = {}

    @classmethod
    def nuevo(cls) -> "Documento":
        """Un dibujo nuevo **para trabajar**: nace en la unidad de la casa (cm
        desde 0.20.1, Mike: «quiero que las medidas por default sean cm»), con
        el estilo de cota y los decimales ya ajustados. `Documento()` a secas
        sigue en milímetros: es lo que usan la importación y las pruebas del
        motor; un archivo que se abre conserva su unidad."""
        from . import unidades as _uni
        doc = cls()
        if config.UNIDADES_OMISION in ("mm", "cm", "m") and config.UNIDADES_OMISION != "mm":
            _uni.cambiar(doc, config.UNIDADES_OMISION, escalar=True)
            est = doc.estilos_cota.get("T101")
            if est:
                est["factor_escala"] = round(float(est["factor_escala"]), 6)
            doc.historial = Historial()
            doc.sucio = False
        return doc

    # =====================================================================
    # El DXF de origen  ·  en disco, no en memoria
    # =====================================================================
    @property
    def origen_dxf(self) -> str | None:
        """El texto del DXF original. Se lee del disco la primera vez que se
        pide y no se guarda: quien lo pide es el exportador, una vez."""
        if self._origen_dxf is not None:
            return self._origen_dxf
        if self.origen_dxf_ruta:
            try:
                import pathlib as _p
                return _p.Path(self.origen_dxf_ruta).read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                return None
        return None

    @origen_dxf.setter
    def origen_dxf(self, valor: str | None) -> None:
        self._origen_dxf = valor
        if valor is not None:
            self.origen_dxf_ruta = None

    @property
    def tiene_origen(self) -> bool:
        """¿Hay DXF de origen? Sin leerlo: preguntarlo con `if doc.origen_dxf`
        se traía los 222 MB a memoria nada más para ver si había algo."""
        if self._origen_dxf:
            return True
        if not self.origen_dxf_ruta:
            return False
        import pathlib as _p
        return _p.Path(self.origen_dxf_ruta).exists()

    # =====================================================================
    # Caché de teselado
    # =====================================================================
    # Teselar una entidad —convertir un arco en las rayas que se pintan— es lo
    # caro del programa, y la mayoría de las veces se vuelve a hacer sobre
    # entidades que no cambiaron: prender una capa, reabrir el índice, repintar
    # una hoja. La caché guarda ese trabajo.
    #
    # **La regla es olvidar de más, nunca de menos.** Una caché que se queda
    # con un trazo viejo enseña un dibujo que no es el del archivo, y eso es
    # peor que ser lento: se descubre midiendo una pieza ya cortada. Por eso
    # todo camino que modifica algo llama a `olvidar()`, y cuando hay duda se
    # olvida el documento entero — recalcular cuesta milisegundos.
    #
    # Que esto sea posible se debe a una decisión vieja: **todo cambio pasa por
    # los métodos de esta clase.** Si las herramientas tocaran las listas
    # directamente, no habría dónde poner la invalidación.

    def olvidar(self, ids=None) -> None:
        """Olvida lo teselado de esas entidades, o de todas si no se dan ids.

        También sus cajas guardadas (ver `extension`): toda mutación de una
        entidad pasa por aquí, así que es el sitio exacto para tirarlas.
        """
        cajas = self.__dict__.setdefault("_cajas_cache", {})
        if ids is None:
            self.cache.clear()
            cajas.clear()
            self.__dict__.pop("_pesados_cache", None)
            self.__dict__.pop("_cajas_bloque", None)
            return
        for i in ids:
            self.cache.pop(i, None)
            cajas.pop(i, None)

    def cacheable(self, e) -> bool:
        """¿Se puede guardar lo teselado de esta entidad?

        Sólo si su dibujo depende de **ella y de su capa**, y de nada más. Una
        **cota** no cumple: se dibuja con su estilo (`estilos_cota`), y cambiar
        un estilo cambia las doscientas cotas del plano sin tocar ninguna. Las
        pruebas t008 y t009 lo cazaron el mismo día que se puso la caché — un
        estilo cambiado que no se veía en pantalla, que es exactamente la clase
        de error silencioso que esta caché podría haber introducido.

        Las cotas son pocas en un plano; las líneas, polilíneas, rayados y
        bloques son casi todo. Dejarlas fuera cuesta poco y quita de golpe toda
        una familia de errores posibles.
        """
        if e.tipo == "cota":
            return False
        if e.tipo == "insercion":
            bl = self.bloques.get(e.bloque)
            if bl is not None and any(s.tipo == "cota" for s in bl.entidades):
                return False
        return True

    def olvidar_capa(self, nombre: str) -> None:
        """El color y el grosor se heredan de la capa: si cambia, sus entidades
        se vuelven a teselar."""
        self.olvidar([e.id for e in self.entidades.values() if e.capa == nombre])

    # =====================================================================
    # Transacciones
    # =====================================================================
    def transaccion(self, nombre: str) -> _Contexto:
        return _Contexto(self.historial, nombre)

    # =====================================================================
    # Entidades
    # =====================================================================
    def agregar(self, entidad: Entidad) -> Entidad:
        capa = self.capas.get(entidad.capa)
        if capa is None:
            entidad.capa = self.capa_activa if self.capa_activa in self.capas else "0"
            capa = self.capas[entidad.capa]
        if capa.bloqueada:
            raise CapaBloqueada(f"La capa «{capa.nombre}» está bloqueada")
        self.entidades[entidad.id] = entidad
        self.orden.append(entidad.id)
        self.olvidar([entidad.id])
        self.historial.anotar(("ent+", entidad.id, entidad.a_dict(), len(self.orden) - 1))
        self.sucio = True
        return entidad

    def borrar(self, id_: str) -> None:
        ent = self.entidades.get(id_)
        if ent is None:
            return
        if self.capas[ent.capa].bloqueada:
            raise CapaBloqueada(f"La capa «{ent.capa}» está bloqueada")
        i = self.orden.index(id_)
        self.olvidar([id_])
        self.historial.anotar(("ent-", id_, ent.a_dict(), i))
        del self.entidades[id_]
        del self.orden[i]
        self.sucio = True

    def modificar(self, id_: str, cambios: dict) -> Entidad:
        ent = self.entidades[id_]
        if self.capas[ent.capa].bloqueada:
            raise CapaBloqueada(f"La capa «{ent.capa}» está bloqueada")
        antes = ent.a_dict()
        self.olvidar([id_])
        for k, v in cambios.items():
            if k in ("id", "tipo"):
                continue
            if not hasattr(ent, k):
                raise AttributeError(f"«{k}» no es propiedad de {ent.tipo}")
            setattr(ent, k, v)
        despues = ent.a_dict()
        if antes != despues:
            self.historial.anotar(("ent~", id_, antes, despues))
            self.sucio = True
        return ent

    def lista(self) -> list[Entidad]:
        return [self.entidades[i] for i in self.orden]

    def visibles(self, espacio: str = "") -> list[Entidad]:
        """Lo que se ve en un espacio: `""` el modelo, o el nombre de una hoja.

        El espacio se filtra aquí y no en cada sitio que recorre entidades: es
        la única forma de que una nota puesta en una hoja no aparezca también
        en el modelo, a 100 mm del origen, donde nadie la puso.
        """
        out = []
        for i in self.orden:
            e = self.entidades[i]
            if getattr(e, "espacio", "") != espacio:
                continue
            c = self.capas.get(e.capa)
            if e.visible and c is not None and c.visible:
                out.append(e)
        return out

    # =====================================================================
    # Capas  ·  feature 45
    # =====================================================================
    def capa_agregar(self, capa: Capa) -> Capa:
        capa.nombre = mod_capas.validar_nombre(capa.nombre)
        if capa.nombre in self.capas:
            raise ValueError(f"Ya existe la capa «{capa.nombre}»")
        capa.grosor = mod_capas.grosor_valido(capa.grosor)
        self.capas[capa.nombre] = capa
        self.historial.anotar(("capa+", capa.nombre, capa.a_dict()))
        self.sucio = True
        return capa

    #: Propiedades de capa que las entidades **heredan** y que por tanto
    #: cambian cómo se dibujan. Prender o apagar una capa no está aquí a
    #: propósito: cambia si se ve, no cómo se ve, y volver a teselar un plano
    #: entero por encender una capa es justo lo que hacía que apagar y prender
    #: capas fuera lento.
    HEREDADAS = {"color", "grosor", "tipo_linea", "nombre"}

    def capa_modificar(self, nombre: str, cambios: dict) -> Capa:
        capa = self.capas[nombre]
        if set(cambios) & self.HEREDADAS:
            self.olvidar_capa(nombre)
        antes = capa.a_dict()
        nuevo_nombre = cambios.get("nombre", nombre)
        if nuevo_nombre != nombre:
            if nombre == "0":
                raise ValueError("La capa 0 no se renombra")
            nuevo_nombre = mod_capas.validar_nombre(nuevo_nombre)
            if nuevo_nombre in self.capas:
                raise ValueError(f"Ya existe la capa «{nuevo_nombre}»")
        for k, v in cambios.items():
            if k == "grosor":
                v = mod_capas.grosor_valido(int(v))
            if k == "nombre":
                continue
            setattr(capa, k, v)
        if nuevo_nombre != nombre:
            del self.capas[nombre]
            capa.nombre = nuevo_nombre
            self.capas[nuevo_nombre] = capa
            for e in self.entidades.values():
                if e.capa == nombre:
                    e.capa = nuevo_nombre
            if self.capa_activa == nombre:
                self.capa_activa = nuevo_nombre
        despues = capa.a_dict()
        if antes != despues:
            self.historial.anotar(("capa~", nombre, antes, despues))
            self.sucio = True
        return capa

    def capa_borrar(self, nombre: str) -> None:
        if nombre == "0":
            raise ValueError("La capa 0 no se borra")
        if nombre not in self.capas:
            return
        usadas = [e.id for e in self.entidades.values() if e.capa == nombre]
        if usadas:
            raise CapaEnUso(
                f"La capa «{nombre}» tiene {len(usadas)} entidad(es). "
                "Muévelas o bórralas primero."
            )
        capa = self.capas[nombre]
        self.historial.anotar(("capa-", nombre, capa.a_dict()))
        del self.capas[nombre]
        if self.capa_activa == nombre:
            self.capa_activa = "0"
        self.sucio = True

    def capa_de(self, entidad: Entidad) -> Capa:
        return self.capas.get(entidad.capa) or self.capas["0"]

    # --- resolución de propiedades  ·  feature 49 -------------------------
    def color_efectivo(self, e: Entidad) -> str:
        return e.color or self.capa_de(e).color

    def grosor_efectivo(self, e: Entidad) -> int:
        if e.grosor is None or e.grosor == config.GROSOR_POR_CAPA:
            return self.capa_de(e).grosor
        if e.grosor == config.GROSOR_OMISION:
            return 25
        return e.grosor

    def tipo_linea_efectivo(self, e: Entidad) -> str:
        return e.tipo_linea or self.capa_de(e).tipo_linea

    # =====================================================================
    # Bloques
    # =====================================================================
    def bloque_agregar(self, bloque: Bloque) -> Bloque:
        self.bloques[bloque.nombre] = bloque
        self.sucio = True
        return bloque

    # =====================================================================
    # Geometría del conjunto
    # =====================================================================
    def caja_de(self, e: Entidad):
        """Caja de una entidad, resolviendo la inserción contra su bloque.

        La inserción se resuelve **con su giro, su escala y el punto base del
        bloque, y hacia adentro** (los bloques anidados con los suyos). Hasta
        la 0.19.4 se tomaba la caja del contenido sin girar y los sub-bloques
        sólo por su punto de inserción: en el plano WPMNDLZA100 de Mike
        (9-sep-2026) una silla dibujada a 1.6 km de su punto base, insertada
        girada 89° para caer junto a la mesa, daba una extensión de dos
        kilómetros; Extents se iba tan lejos que no se podía volver. AutoCAD
        no la contaba porque gira de verdad. Ahora aquí también.
        """
        if e.tipo == "insercion":
            return self._caja_insercion(e, 0)
        return e.caja()

    def _caja_bloque(self, nombre: str, profundidad: int):
        """La caja del contenido de un bloque, en sus coordenadas. En caché."""
        cache = self.__dict__.setdefault("_cajas_bloque", {})
        if nombre in cache:
            return cache[nombre]
        bl = self.bloques.get(nombre)
        salida = None
        if bl is not None and profundidad < 8:
            cajas = []
            for x in bl.entidades:
                c = self._caja_insercion(x, profundidad + 1) if x.tipo == "insercion" else x.caja()
                if c:
                    cajas.append(c)
            if cajas:
                salida = (min(c[0] for c in cajas), min(c[1] for c in cajas),
                          max(c[2] for c in cajas), max(c[3] for c in cajas))
        cache[nombre] = salida
        return salida

    def _caja_insercion(self, e: Entidad, profundidad: int):
        import math as _m
        bl = self.bloques.get(e.bloque)
        local = self._caja_bloque(e.bloque, profundidad) if bl is not None else None
        if local is None:
            return e.caja()
        sx, sy = e.escala[0], e.escala[1]
        r = _m.radians(e.rotacion or 0.0)
        cos, sen = _m.cos(r), _m.sin(r)
        ox = e.p[0] - bl.base[0] * sx
        oy = e.p[1] - bl.base[1] * sy
        xs, ys = [], []
        for lx, ly in ((local[0], local[1]), (local[2], local[1]), (local[2], local[3]), (local[0], local[3])):
            x, y = lx * sx, ly * sy
            xs.append(ox + x * cos - y * sen)
            ys.append(oy + x * sen + y * cos)
        return min(xs), min(ys), max(xs), max(ys)

    # `sucio` es una propiedad y no un campo a propósito: cada mutación del
    # documento lo pone en True, y ése es el momento de tirar las cachés que
    # dependen de la geometría. Así no hay que acordarse en veinte sitios.
    @property
    def sucio(self) -> bool:
        # Un documento de la caché de apertura (pickle) puede venir de antes de
        # que `sucio` fuera propiedad: traía el valor en el __dict__.
        d = self.__dict__
        return bool(d["_sucio"] if "_sucio" in d else d.get("sucio", False))

    @sucio.setter
    def sucio(self, valor: bool) -> None:
        self._sucio = bool(valor)
        cache = self.__dict__.get("_extension_cache")
        if cache:
            cache.clear()

    def mm_por_unidad(self) -> float:
        """Cuántos milímetros vale una unidad del dibujo (1, 10 o 1000)."""
        from . import unidades as mod_unidades
        return mod_unidades.MM_POR_NOMBRE.get(self.unidades, 1.0)

    def extension(self, espacio: str = ""):
        """(x0, y0, x1, y1) de todo lo visible, o None si el espacio está vacío."""
        cache = self.__dict__.setdefault("_extension_cache", {})
        if espacio in cache:
            return cache[espacio]
        # Las cajas de cada entidad se guardan por id: calcularlas es lo caro
        # (recorrer cada vértice), y sólo cambian las de lo que se tocó.
        guardadas = self.__dict__.setdefault("_cajas_cache", {})
        cajas = []
        for e in self.visibles(espacio):
            c = guardadas.get(e.id)
            if c is None:
                c = self.caja_de(e)
                guardadas[e.id] = c if c else ()
            if c:
                cajas.append(c)
        salida = None if not cajas else (
            min(c[0] for c in cajas), min(c[1] for c in cajas),
            max(c[2] for c in cajas), max(c[3] for c in cajas))
        cache[espacio] = salida
        return salida

    # =====================================================================
    # Deshacer / rehacer
    # =====================================================================
    def _aplicar(self, op: tuple, invertir: bool) -> None:
        clase = op[0]
        # Deshacer y rehacer tocan las listas directamente, así que la caché se
        # invalida aquí a mano. Las operaciones de capa cambian el color y el
        # grosor heredados de todo el dibujo: ahí se olvida entero.
        if str(clase).startswith("capa"):
            self.olvidar()
        elif len(op) > 1:
            self.olvidar([op[1]])
        if clase == "ent+":
            _, id_, datos, i = op
            if invertir:
                if id_ in self.entidades:
                    del self.entidades[id_]
                    self.orden.remove(id_)
            else:
                self.entidades[id_] = ent_mod.de_dict(datos)
                self.orden.insert(min(i, len(self.orden)), id_)
        elif clase == "ent-":
            _, id_, datos, i = op
            if invertir:
                self.entidades[id_] = ent_mod.de_dict(datos)
                self.orden.insert(min(i, len(self.orden)), id_)
            else:
                if id_ in self.entidades:
                    del self.entidades[id_]
                    self.orden.remove(id_)
        elif clase == "ent~":
            _, id_, antes, despues = op
            self.entidades[id_] = ent_mod.de_dict(antes if invertir else despues)
        elif clase == "capa+":
            _, nombre, datos = op
            if invertir:
                self.capas.pop(nombre, None)
            else:
                self.capas[nombre] = Capa.de_dict(datos)
        elif clase == "capa-":
            _, nombre, datos = op
            if invertir:
                self.capas[nombre] = Capa.de_dict(datos)
            else:
                self.capas.pop(nombre, None)
        elif clase == "capa~":
            _, nombre, antes, despues = op
            datos = antes if invertir else despues
            viejo = despues if invertir else antes
            self.capas.pop(viejo["nombre"], None)
            self.capas.pop(nombre, None)
            capa = Capa.de_dict(datos)
            self.capas[capa.nombre] = capa
            for e in self.entidades.values():
                if e.capa == viejo["nombre"]:
                    e.capa = capa.nombre
        else:
            raise ValueError(f"Operación desconocida en el historial: {clase}")

    @staticmethod
    def _ids_de(tr) -> list[str]:
        """Qué entidades toca una transacción. Con esto el lienzo se repinta
        por parche y no entero: un Ctrl+Z en un plano grande no debería costar
        lo mismo que abrirlo. Las operaciones de capa no traen id de entidad y
        se resuelven aparte, recargando."""
        ids = []
        for op in tr.ops:
            if op and isinstance(op, tuple) and str(op[0]).startswith("ent") and len(op) > 1:
                ids.append(op[1])
        return ids

    def deshacer(self) -> str | None:
        if not self.historial.puede_deshacer:
            return None
        tr = self.historial.hechas.pop()
        for op in reversed(tr.ops):
            self._aplicar(op, invertir=True)
        self.historial.deshechas.append(tr)
        self.sucio = True
        self.ultimos_tocados = self._ids_de(tr)
        self.ultimo_toco_capas = any(
            str(op[0]).startswith("capa") for op in tr.ops if op)
        return tr.nombre

    def rehacer(self) -> str | None:
        if not self.historial.puede_rehacer:
            return None
        tr = self.historial.deshechas.pop()
        for op in tr.ops:
            self._aplicar(op, invertir=False)
        self.historial.hechas.append(tr)
        self.sucio = True
        self.ultimos_tocados = self._ids_de(tr)
        self.ultimo_toco_capas = any(
            str(op[0]).startswith("capa") for op in tr.ops if op)
        return tr.nombre

    # =====================================================================
    # Serialización
    # =====================================================================
    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "cliente": self.cliente,
            "unidad": self.unidad,
            "capa_activa": self.capa_activa,
            "capas": [c.a_dict() for c in self.capas.values()],
            "bloques": [b.a_dict() for b in self.bloques.values()],
            "entidades": [self.entidades[i].a_dict() for i in self.orden],
            "estilos_texto": self.estilos_texto,
            "estilos_cota": self.estilos_cota,
            "layouts": self.layouts,
            "origen_t101x": self.origen_t101x,
            "xrefs": self.xrefs,
            "origen_dxf": self.origen_dxf,
            "origen_dwg": self.origen_dwg,
            "factor_unidades": self.factor_unidades,
            "insunits_origen": self.insunits_origen,
            "unidades": self.unidades,
        }

    @staticmethod
    def de_dict(d: dict) -> "Documento":
        doc = Documento(con_plantilla=False)
        doc.historial.silencio = True
        try:
            doc.nombre = d.get("nombre", "Sin título")
            doc.cliente = d.get("cliente", "")
            doc.unidad = d.get("unidad", config.UNIDAD)
            doc.capas = {}
            for c in d.get("capas", []):
                capa = Capa.de_dict(c)
                doc.capas[capa.nombre] = capa
            if "0" not in doc.capas:
                doc.capas["0"] = Capa("0")
            for b in d.get("bloques", []):
                bl = Bloque.de_dict(b)
                doc.bloques[bl.nombre] = bl
            for e in d.get("entidades", []):
                ent = ent_mod.de_dict(e)
                doc.entidades[ent.id] = ent
                doc.orden.append(ent.id)
            doc.estilos_texto = d.get("estilos_texto") or {"T101": dict(ESTILO_TEXTO_T101)}
            doc.estilos_cota = d.get("estilos_cota") or {"T101": dict(ESTILO_COTA_T101)}
            doc.capa_activa = d.get("capa_activa", "0")
            if doc.capa_activa not in doc.capas:
                doc.capa_activa = "0"
            doc.layouts = d.get("layouts") or []
            doc.origen_t101x = d.get("origen_t101x")
            doc.xrefs = d.get("xrefs") or {}
            doc.origen_dxf = d.get("origen_dxf")
            doc.origen_dwg = d.get("origen_dwg")
            doc.factor_unidades = float(d.get("factor_unidades", 1.0) or 1.0)
            doc.insunits_origen = d.get("insunits_origen")
            doc.unidades = d.get("unidades") if d.get("unidades") in ("mm", "cm", "m") else "mm"
            ent_mod.sembrar_contador(doc.entidades.values())
        finally:
            doc.historial.silencio = False
        doc.sucio = False
        return doc

    def copia(self) -> "Documento":
        return Documento.de_dict(copy.deepcopy(self.a_dict()))
