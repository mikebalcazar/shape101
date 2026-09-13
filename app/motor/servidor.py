"""La API local del motor  ·  el mismo patrón que draw101: el documento vive
en el servidor, no en el navegador. Contesta JSON en 127.0.0.1 y sólo ahí.

  GET  /api/salud                 {"ok": true, "version": ...}
  GET  /api/documento             el documento como JSON
  POST /api/documento/nuevo       {nombre, material, espesor_mm}
  POST /api/documento/abrir       {ruta}
  POST /api/documento/guardar     {ruta}
  POST /api/operacion             {op} → agrega, regenera y devuelve el modelo
  GET  /api/modelo                una malla por cara con su nombre, más las aristas
  POST /api/exportar              {formato: step|stl|gltf, ruta}

Un error del motor (una operación desconocida, un archivo que no existe)
contesta 400 con el nombre del error y el motor sigue vivo. Nada lo tumba.
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from build123d import export_step, export_stl

from app.motor import VERSION, malla
from app.motor.documento import Documento


class Motor:
    """El estado que la API expone: un documento y la caché de su malla."""

    def __init__(self):
        self.doc: Documento | None = None
        self.reg = None
        self.ms_regenerar = 0.0
        self._cache_malla: dict = {}

    def _exigir_documento(self) -> Documento:
        if self.doc is None:
            raise ValueError("no hay documento abierto: primero /api/documento/nuevo o /api/documento/abrir")
        return self.doc

    def nuevo(self, datos: dict):
        self.doc = Documento.nuevo(datos["nombre"], datos.get("material", ""), float(datos.get("espesor_mm", 0)))
        self.reg, self._cache_malla = None, {}

    def abrir(self, ruta):
        self.doc = Documento.abrir(ruta)
        self.reg, self._cache_malla = None, {}
        self.regenerar()

    def guardar(self, ruta):
        return str(self._exigir_documento().guardar(ruta))

    def regenerar(self):
        doc = self._exigir_documento()
        t = time.perf_counter()
        self.reg = doc.regenerar()
        self.ms_regenerar = (time.perf_counter() - t) * 1000
        return self.reg

    def operacion(self, op: dict):
        doc = self._exigir_documento()
        doc.agregar(op)
        try:
            return self.regenerar()
        except Exception:
            doc.borrar(len(doc.operaciones) - 1)     # una operación que no regenera no se queda en el historial
            raise

    def modelo(self) -> dict:
        if self.reg is None or self.reg.solido is None:
            self.regenerar()
        if self.reg.solido is None:
            return {"caras": [], "aristas": [], "n_caras": 0, "n_triangulos": 0, "reteseladas": 0,
                    "ms_regenerar": round(self.ms_regenerar, 1), "ms_teselar": 0.0}
        m, self._cache_malla = malla.malla_de(self.reg, self._cache_malla, ms_regenerar=self.ms_regenerar)
        return m

    def exportar(self, formato: str, ruta) -> dict:
        if self.reg is None or self.reg.solido is None:
            self.regenerar()
        if self.reg.solido is None:
            raise ValueError("no hay sólido que exportar: el historial no produce nada todavía")
        ruta = pathlib.Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        formato = str(formato).lower()
        if formato == "step":
            export_step(self.reg.solido, str(ruta))
        elif formato == "stl":
            export_stl(self.reg.solido, str(ruta))
        elif formato == "gltf":
            malla.gltf_de(self.reg.solido, ruta, binario=ruta.suffix.lower() != ".gltf")
        else:
            raise ValueError(f"no conozco el formato «{formato}»: step, stl o gltf")
        return {"ruta": str(ruta), "bytes": ruta.stat().st_size}


def _manejador(motor: Motor):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _cuerpo(self) -> dict:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            try:
                if self.path == "/api/salud":
                    return self._json({"ok": True, "version": VERSION})
                if self.path == "/api/documento":
                    return self._json(motor._exigir_documento().a_dict())
                if self.path == "/api/modelo":
                    return self._json(motor.modelo())
                return self._json({"error": f"no existe {self.path}"}, 404)
            except Exception as e:                       # el error se contesta, el motor sigue
                return self._json({"error": f"{type(e).__name__}: {e}"}, 400)

        def do_POST(self):
            try:
                datos = self._cuerpo()
                if self.path == "/api/documento/nuevo":
                    motor.nuevo(datos)
                    return self._json(motor.doc.a_dict())
                if self.path == "/api/documento/abrir":
                    motor.abrir(datos["ruta"])
                    return self._json(motor.doc.a_dict())
                if self.path == "/api/documento/guardar":
                    return self._json({"ruta": motor.guardar(datos["ruta"])})
                if self.path == "/api/operacion":
                    motor.operacion(datos["op"])
                    return self._json(motor.modelo())
                if self.path == "/api/exportar":
                    return self._json(motor.exportar(datos["formato"], datos["ruta"]))
                return self._json({"error": f"no existe {self.path}"}, 404)
            except Exception as e:
                return self._json({"error": f"{type(e).__name__}: {e}"}, 400)
    return H


class Servidor:
    """`with Servidor() as s: ... s.url ...`  Un hilo, sólo 127.0.0.1."""

    def __init__(self, puerto: int = 0, motor: Motor | None = None):
        self.motor = motor or Motor()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", puerto), _manejador(self.motor))
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
    with Servidor(8791) as s:
        print("motor de shape101 en", s.url)
        threading.Event().wait()
