"""El motor detrás de una API local, como en draw101  ·  P4 y P6.

Sirve la página de la vista 3D (poc/vista/) y node_modules/ (three.js), y
contesta JSON:

  GET  /api/modelo            la malla teselada por cara + las aristas
  POST /api/cargar   {ops}    carga un historial y regenera
  POST /api/empujar  {cara, mm}   añade la operación, regenera y devuelve el modelo
  GET  /api/gltf              el sólido como glTF (P6)

Una geometría **por cara** —no una malla única— es lo que permite seleccionar
una cara en Three.js con un raycast y saber su nombre. Corre en un hilo para
que la prueba lo arranque y lo pare sola.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build123d import export_gltf

from poc import historial

RAIZ = pathlib.Path(__file__).resolve().parent.parent


class Motor:
    def __init__(self):
        self.ops: list[dict] = []
        self.reg: historial.Regenerado | None = None
        self.ms_ultima = 0.0

    def cargar(self, ops):
        self.ops = list(ops)
        t = time.perf_counter()
        self.reg = historial.regenerar(self.ops)
        self.ms_ultima = (time.perf_counter() - t) * 1000

    incremental = True      # como la app: sólo se ejecuta la operación nueva

    def empujar(self, cara: str, mm: float):
        op = {"op": "empujar_cara", "cara": cara, "mm": mm}
        if self.incremental and self.reg is not None and self.reg.estado is not None:
            t = time.perf_counter()
            historial.extender(self.reg, op)
            self.ops = list(self.reg.estado.ops)
            self.ms_ultima = (time.perf_counter() - t) * 1000
        else:
            self.ops.append(op)
            self.cargar(self.ops)

    def cargar_forma(self, forma, nombres_caras: dict):
        """Una forma cualquiera con sus caras ya nombradas (sin historial)."""
        nom = historial.nombres.Nombrador()
        nom.caras = dict(nombres_caras)
        self.reg = historial.Regenerado(forma, nom, [])
        self.ops = []
        self.ms_ultima = 0.0

    _cache_malla: dict = {}
    reteseladas = 0

    def malla(self, tolerancia=0.5, angular=0.3) -> dict:
        """Una cara que no cambió (misma superficie, misma área, mismo centro)
        no se vuelve a teselar: es lo que haría la app, y lo que la medición
        de P4 quiere saber es cuánto cuesta lo que SÍ cambió."""
        from poc import nombres as _n
        t = time.perf_counter()
        caras = []
        self.reteseladas = 0
        nueva_cache = {}
        for nombre, f in self.reg.nombrador.caras.items():
            c = f.center()
            clave = (nombre, tuple(round(x, 6) if isinstance(x, float) else x for x in _n.superficie(f)),
                     round(f.area, 4), round(c.X, 4), round(c.Y, 4), round(c.Z, 4))
            malla = self._cache_malla.get(clave)
            if malla is None:
                vs, tris = f.tessellate(tolerancia, angular)
                malla = {"nombre": nombre, "v": [k for v in vs for k in (v.X, v.Y, v.Z)], "i": [k for t3 in tris for k in t3]}
                self.reteseladas += 1
            nueva_cache[clave] = malla
            caras.append(malla)
        self._cache_malla = nueva_cache
        aristas = []
        for e in self.reg.solido.edges():
            n = 2 if e.geom_type.name == "LINE" else 24
            aristas.append([[p.X, p.Y, p.Z] for p in (e.position_at(k / n) for k in range(n + 1))])
        return {"caras": caras, "aristas": aristas, "ms_regenerar": round(self.ms_ultima, 1), "reteseladas": self.reteseladas,
                "ms_teselar": round((time.perf_counter() - t) * 1000, 1),
                "n_caras": len(caras), "n_triangulos": sum(len(c["i"]) // 3 for c in caras)}

    def gltf(self) -> bytes:
        ruta = pathlib.Path(tempfile.mkdtemp()) / "modelo.glb"
        export_gltf(self.reg.solido, str(ruta), binary=True, linear_deflection=0.5, angular_deflection=0.3)
        return ruta.read_bytes()


def _manejador(motor: Motor):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(RAIZ), **k)

        def log_message(self, *a):
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == "/api/modelo":
                return self._json(motor.malla())
            if self.path == "/api/gltf":
                datos = motor.gltf()
                self.send_response(200)
                self.send_header("Content-Type", "model/gltf-binary")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                return self.wfile.write(datos)
            if self.path == "/":
                self.path = "/poc/vista/index.html"
            return super().do_GET()

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            datos = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/api/cargar":
                    motor.cargar(datos["ops"])
                elif self.path == "/api/empujar":
                    motor.empujar(datos["cara"], float(datos["mm"]))
                else:
                    return self._json({"error": "no existe"}, 404)
            except Exception as e:      # el error se devuelve, no se esconde
                return self._json({"error": str(e)}, 400)
            return self._json(motor.malla())
    return H


class Servidor:
    def __init__(self, motor: Motor, puerto=0):
        self.motor = motor
        self.httpd = ThreadingHTTPServer(("127.0.0.1", puerto), _manejador(motor))
        self.puerto = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.puerto}"
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.hilo.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    from poc import p3_historial
    m = Motor()
    m.cargar(p3_historial.documento())
    with Servidor(m, 8790) as s:
        print("motor en", s.url)
        threading.Event().wait()
