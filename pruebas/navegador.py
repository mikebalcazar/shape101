"""Levantar el programa de verdad y manejarlo con un navegador.

Las pruebas de interfaz no simulan el programa: **lo arrancan**. Un servidor
Python en un puerto libre, un Chromium de verdad cargando la misma página que
ve el taller, y las funciones del propio programa llamadas desde dentro de la
página. Una prueba de interfaz que reimplementa la interfaz sólo comprueba que
la reimplementación coincide consigo misma.

El idioma se fija en español a mano: el programa lo saca del navegador, y el
Chromium de un armador suele estar en inglés — una prueba que compara textos
pasaría en la máquina de Mike y fallaría en el servidor por algo que no es un
error del programa.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def hay_navegador() -> bool:
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


def _puerto_libre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@contextlib.contextmanager
def programa(idioma: str = "es-MX"):
    """Arranca el motor y abre la interfaz. Devuelve `(pagina, base)`."""
    from playwright.sync_api import sync_playwright

    puerto = _puerto_libre()
    motor = subprocess.Popen(
        [sys.executable, str(RAIZ / "server.py"), str(puerto)],
        cwd=str(RAIZ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"})
    base = f"http://127.0.0.1:{puerto}"
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(base + "/api/salud", timeout=1)
                break
            except Exception:
                if motor.poll() is not None:
                    raise RuntimeError("el motor no arrancó: "
                                       + (motor.stdout.read() or b"").decode()[-800:])
                time.sleep(0.25)
        else:
            raise RuntimeError("el motor no contestó a /api/salud")

        with sync_playwright() as pw:
            navegador = pw.chromium.launch()
            contexto = navegador.new_context(viewport={"width": 1280, "height": 800},
                                             locale=idioma)
            pagina = contexto.new_page()
            pagina.errores = []          # se llena sola; la mira cada prueba
            pagina.on("pageerror", lambda e: pagina.errores.append(str(e)))
            pagina.on("console", lambda m: (pagina.errores.append(m.text)
                                            if m.type == "error" else None))
            pagina.goto(base + "/", wait_until="networkidle")
            pagina.wait_for_selector("#lienzo", timeout=15000)
            pagina.wait_for_timeout(800)     # que termine de arrancar la interfaz
            try:
                yield pagina, base
            finally:
                navegador.close()
    finally:
        motor.terminate()
        try:
            motor.wait(timeout=5)
        except subprocess.TimeoutExpired:
            motor.kill()


def cerrar_inicio(pagina) -> None:
    """La pantalla de inicio sale al abrir; se quita para trabajar.

    La × de cerrar sólo está cuando hay un dibujo detrás al que volver. Recién
    arrancado no lo hay —es lo correcto: cerrar la pantalla de inicio dejaría a
    la vista una ventana vacía— así que se entra por «Dibujo nuevo».
    """
    if not pagina.locator("#inicio").is_visible():
        return
    if pagina.locator("#iCerrar").is_visible():
        pagina.click("#iCerrar")
    else:
        pagina.click("#iNuevo")
    pagina.wait_for_selector("#inicio", state="hidden", timeout=10000)
    pagina.wait_for_timeout(300)


def comando(pagina, texto: str, confirmar: str = "Enter") -> None:
    """Escribe en la línea de comando y remata. `confirmar` puede ser el
    espacio, que es como se dibuja en AutoCAD: la izquierda en la barra y la
    derecha en el ratón."""
    pagina.click("#cmd")
    pagina.fill("#cmd", "")
    pagina.type("#cmd", texto, delay=10)
    pagina.keyboard.press(confirmar if confirmar != " " else "Space")
    pagina.wait_for_timeout(250)


def estado(base: str) -> dict:
    """Lo que dice el motor. La prueba comprueba contra **el servidor**, no
    contra lo que el lienzo cree tener pintado: el documento vive allá."""
    import json
    with urllib.request.urlopen(base + "/api/estado", timeout=5) as f:
        return json.loads(f.read().decode("utf-8"))


def trazos(base: str) -> list[dict]:
    import json
    with urllib.request.urlopen(base + "/api/trazos", timeout=15) as f:
        return json.loads(f.read().decode("utf-8"))["trazos"]
