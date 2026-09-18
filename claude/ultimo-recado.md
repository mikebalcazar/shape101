# Último recado · FALLÓ

- corrido: 2026-09-18T16:47:05+00:00

```
ui/seleccion.js (selección por cámara y por plano): parchado
ui/vista.js (la llave mira las cuatro): parchado
ui/vista.js (sin foto con cuatro ventanas): parchado
ui/vista.js (perspectiva en píxeles): parchado
ui/ventanas.js (foco en píxeles): parchado
ui/camara.js (girar va a la Perspectiva): parchado
ui/radial.js (rueda 3D con Shift): parchado
versión 0.11.0 → 0.12.0

ERROR: RuntimeError: falló node: /tmp/recado28/shape101/ui/vista.js:728
  return `${todas}#`${v.x}|${v.y}|${v.escala}|${v.rx || 0}|${v.rz || 0}|${lienzo.width}|${lienzo.height}|` +
                    ^

SyntaxError: Unexpected identifier '$'
    at wrapSafe (node:internal/modules/cjs/loader:1713:18)
    at checkSyntax (node:internal/main/check_syntax:78:3)

Node.js v22.23.2
```
