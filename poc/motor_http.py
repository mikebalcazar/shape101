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
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


from app.motor import historial, malla as malla_mod, nombres

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
        nom = nombres.Nombrador()
        nom.caras = dict(nombres_caras)
        self.reg = historial.Regenerado(forma, nom, [])
        self.ops = []
        self.ms_ultima = 0.0

    _cache_malla: dict = {}
    reteseladas = 0

    def malla(self, tolerancia=0.5, angular=0.3) -> dict:
        "Una cara que no cambió no se vuelve a teselar (app/motor/malla.py)."
        m, self._cache_malla = malla_mod.malla_de(self.reg, self._cache_malla, tolerancia, angular, self.ms_ultima)
        self.reteseladas = m["reteseladas"]
        return m

    def gltf(self) -> bytes:
        return malla_mod.gltf_de(self.reg.solido)

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
