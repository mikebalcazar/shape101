"""t058 · Ningún alias de comando está repetido; UN es de UNIDADES.

`UN` estaba en UNIDADES y en UNIR a la vez. Con dos dueños gana el último que
se registra (ui/comandos.js), sin avisar: el comando que abre depende del orden
en que cargan los archivos. Mike decidió el 3-nov-2026 que UN es de UNIDADES
(como UNITS en AutoCAD); UNIR se queda con J y JOIN.

Al buscar los repetidos salieron siete más: el PARCHE de la fase D1 se llamaba
RED (alias de REDONDEAR, que le ganaba) y seis de antes, que Mike pidió
resolver como AutoCAD: EX extender, H rayado, EXT extruir, MEDIR medir, CP
copiar (abría COTAPIEZA) y BLOQUE el comando BLOQUE (abría PRISMA).

Se revisa en el programa de verdad, con todos los comandos registrados, que
ningún nombre ni alias tenga dos dueños, y qué comando corre cada uno.
"""

from __future__ import annotations

from pruebas import comun, navegador

DESCRIPCION = "ningún alias de comando repetido; UN es de UNIDADES y UNIR es J/JOIN"


def correr(r: comun.Reporte) -> None:
    if not navegador.hay_navegador():
        r.cierto(True, "(sin Playwright en esta máquina: la prueba se salta)")
        return
    with navegador.programa() as (pagina, base):
        navegador.cerrar_inicio(pagina)
        repetidos = pagina.evaluate("""() => {
            const dueños = new Map();
            for (const c of Comandos.lista) {
                for (const a of [c.nombre, ...(c.alias || [])]) {
                    const k = String(a).toUpperCase();
                    if (!dueños.has(k)) dueños.set(k, new Set());
                    dueños.get(k).add(c.nombre);
                }
            }
            return [...dueños].filter(([, s]) => s.size > 1).map(([k, s]) => k + ': ' + [...s].join(', '));
        }""")
        r.igual(repetidos, [], "ningún nombre ni alias de comando tiene dos dueños")
        nombre = pagina.evaluate("() => { const c = Comandos.lista.find((x) => (x.alias || []).includes('JOIN')); return c && c.nombre; }")
        r.igual(nombre, "UNIR", "JOIN (y J) sigue siendo UNIR")
        # Lo que corre de verdad cada alias que tenía dos dueños (Mike, 3-nov-2026:
        # como en AutoCAD). Se interceptan los comandos para no ejecutarlos.
        corre = pagina.evaluate("""async () => {
            const out = {};
            for (const k of ['UN', 'EX', 'MEDIR', 'H', 'CP', 'EXT', 'BLOQUE', 'RED', 'PARCHE']) {
                let quien = null;
                const guardados = new Map();
                for (const c of Comandos.lista) { guardados.set(c, c.correr); c.correr = () => { quien = c.nombre; }; }
                try { await Comandos.correr(k); } catch (e) {}
                for (const [c, f] of guardados) c.correr = f;
                out[k] = quien;
            }
            return out;
        }""")
        r.igual(corre, {"UN": "UNIDADES", "EX": "EXTENDER", "MEDIR": "MEDIR", "H": "RAYADO", "CP": "COPIAR",
                        "EXT": "EXTRUIR", "BLOQUE": "BLOQUE", "RED": "REDONDEAR", "PARCHE": "PARCHE"},
                "cada alias corre el comando de AutoCAD (CP copia y BLOQUE es BLOQUE, ya no PRISMA)")
        r.igual(pagina.errores, [], "y no hubo un solo error de JavaScript")
