"""P6 · Presentación: glTF del sólido teselado, abierto en un visor web.

El motor exporta glTF binario (.glb) con build123d; la misma página de P4 lo
carga con GLTFLoader de three.js, como lo haría peek101 en el navegador del
cliente. Sí/no y MB del archivo.
"""
from __future__ import annotations

from poc import comun, motor_http, p3_historial, p4_vista_3d

DESCRIPCION = "glTF del sólido → GLTFLoader de three.js (como peek101)"


def correr(r: comun.Reporte):
    from playwright.sync_api import sync_playwright
    motor = motor_http.Motor()
    motor.cargar(p3_historial.documento())
    t = {}
    with comun.cronometro(t, "gltf"):
        datos = motor.gltf()
    r.exige(datos[:4] == b"glTF", "el motor produce un glTF binario válido (cabecera glTF)")
    r.numero("P6 glTF del tablero (11 caras): tamaño", round(len(datos) / 1024, 1), "KB")
    r.numero("P6 exportar glTF", round(t["gltf"]), "ms")
    forma, nombres = p4_vista_3d._mueble_500_caras()
    motor.cargar_forma(forma, nombres)
    datos500 = motor.gltf()
    r.numero("P6 glTF del mueble de 504 caras: tamaño", round(len(datos500) / 1024, 1), "KB")
    motor.cargar(p3_historial.documento())
    with motor_http.Servidor(motor) as srv, sync_playwright() as pw:
        nav, pag, errores = p4_vista_3d._abrir(pw, srv.url)
        try:
            res = pag.evaluate("window.shape101.gltf()")
            r.cierto(res["mallas"] >= 1, "three.js cargó el glTF y hay al menos una malla en escena", str(res))
            r.cierto(res["triangulos"] > 100, "la malla cargada tiene triángulos", str(res))
            r.numero("P6 cargar el glTF en three.js (GLTFLoader)", round(res["ms"]), "ms")
            r.numero("P6 el glTF abre en un visor web", "sí", "", umbral="sí/no", cumple=True)
            r.igual(errores, [], "sin errores de JavaScript al cargar el glTF")
        finally:
            nav.close()
