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
  POST /api/t101d                 {ruta} → qué trae ese dibujo de draw101, ya en mm
  POST /api/operacion/editar      {i, op} → reemplaza, regenera y devuelve el modelo
  POST /api/operacion/borrar      {i}     → quita, regenera y devuelve el modelo
  POST /api/regenerar             regenera y devuelve el modelo
  GET  /api/aristas               los nombres de las aristas del sólido vigente
  GET  /                          la pantalla (app/ui/), y /ui/* sus archivos

Un error del motor (una operación desconocida, un archivo que no existe)
contesta 400 con el nombre del error y el motor sigue vivo. Nada lo tumba.
"""
from __future__ import annotations

import json
import mimetypes
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UI = pathlib.Path(__file__).resolve().parent.parent / "ui"
RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]

from build123d import export_step, export_stl

from app.motor import VERSION, malla, t101d
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

    def editar(self, i: int, op: dict):
        doc = self._exigir_documento()
        antes = doc.operaciones[i]
        doc.editar(i, op)
        try:
            return self.regenerar()
        except Exception:
            doc.editar(i, antes)                     # se vuelve a lo que sí regeneraba
            self.regenerar()
            raise

    def borrar(self, i: int):
        doc = self._exigir_documento()
        antes = doc.operaciones[i]
        doc.borrar(i)
        try:
            return self.regenerar()
        except Exception:
            doc.operaciones.insert(i, antes)
            self.regenerar()
            raise

    def aristas(self) -> dict:
        if self.reg is None or self.reg.solido is None:
            self.regenerar()
        if self.reg.solido is None:
            return {"aristas": []}
        return {"aristas": sorted(self.reg.nombrador.aristas(self.reg.solido))}

    def modelo(self) -> dict:
        if self.reg is None or self.reg.solido is None:
            self.regenerar()
        if self.reg.solido is None:
            return {"caras": [], "aristas": [], "n_caras": 0, "n_triangulos": 0, "reteseladas": 0,
                    "ms_regenerar": round(self.ms_regenerar, 1), "ms_teselar": 0.0}
        m, self._cache_malla = malla.malla_de(self.reg, self._cache_malla, ms_regenerar=self.ms_regenerar)
        bb = self.reg.solido.bounding_box()
        m["caja"] = [round(bb.size.X, 2), round(bb.size.Y, 2), round(bb.size.Z, 2)]
        m["volumen_mm3"] = round(self.reg.solido.volume, 1)
        m["operaciones"] = len(self.doc.operaciones)
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
        def log_message(self, formato, *args):
            pass                                            # lo de abajo ya deja rastro con el tiempo

        def _rastro(self, inicio: float, codigo: int):
            print(f"[motor] {self.command} {self.path} → {codigo} en {(time.perf_counter() - inicio) * 1000:.0f} ms", flush=True)

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self._rastro(getattr(self, "_t0", time.perf_counter()), codigo)
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _cuerpo(self) -> dict:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _archivo(self, ruta: pathlib.Path):
            if not ruta.is_file():
                return self._json({"error": f"no existe {self.path}"}, 404)
            datos = ruta.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(ruta))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            self._t0 = time.perf_counter()
            try:
                if self.path == "/api/salud":
                    return self._json({"ok": True, "version": VERSION})
                if self.path == "/api/documento":
                    return self._json(motor._exigir_documento().a_dict())
                if self.path == "/api/modelo":
                    return self._json(motor.modelo())
                if self.path == "/api/aristas":
                    return self._json(motor.aristas())
                # la pantalla y sus archivos (sólo lectura, sólo dentro de app/ui/)
                ruta = self.path.split("?", 1)[0]
                if ruta == "/":
                    return self._archivo(UI / "index.html")
                if ruta.startswith("/ui/"):
                    destino = (UI / ruta[4:]).resolve()
                    if UI.resolve() in destino.parents:
                        return self._archivo(destino)
                if ruta.startswith("/node_modules/") and (RAIZ_REPO / "node_modules").is_dir():   # sólo en desarrollo
                    destino = (RAIZ_REPO / ruta[1:]).resolve()
                    if (RAIZ_REPO / "node_modules").resolve() in destino.parents:
                        return self._archivo(destino)
                return self._json({"error": f"no existe {self.path}"}, 404)
            except Exception as e:                       # el error se contesta, el motor sigue
                return self._json({"error": f"{type(e).__name__}: {e}"}, 400)

        def do_POST(self):
            self._t0 = time.perf_counter()
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
                if self.path == "/api/t101d":
                    return self._json(t101d.leer(datos["ruta"]))
                if self.path == "/api/exportar":
                    return self._json(motor.exportar(datos["formato"], datos["ruta"]))
                if self.path == "/api/operacion/editar":
                    motor.editar(int(datos["i"]), datos["op"])
                    return self._json(motor.modelo())
                if self.path == "/api/operacion/borrar":
                    motor.borrar(int(datos["i"]))
                    return self._json(motor.modelo())
                if self.path == "/api/regenerar":
                    motor.regenerar()
                    return self._json(motor.modelo())
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
    # `python -m app.motor.servidor [puerto]`: lo arranca el cascarón de Electron
    # con un puerto libre, o alguien a mano para abrir la pantalla en un navegador.
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    with Servidor(puerto) as s:
        print("motor de shape101 en", s.url, flush=True)
        threading.Event().wait()
