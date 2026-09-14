# shape101

CAD 2D de Taller 101, y una de las siete apps de suite101. Lee y escribe DXF y
DWG, dibuja, acota, arma hojas con pie de plano, imprime, y trae cocinas de
Taller 101 por `.t101x` para devolver un paquete a SUPERVISOR.

Un cascarón de **Electron** que levanta un motor de **FastAPI con Python 3.11
embebido** en `127.0.0.1`, y le carga la interfaz desde ese mismo servidor. El
documento vive **en el servidor**, no en el navegador: un plano de obra son
decenas de miles de entidades y mandarlo entero en cada clic no aguantaría.

```
core/       documento, entidades, capas, historial, geometría exacta, cotas,
            papel, importación de .t101x y de PDF, preferencias, dwg, unidades
dwgjs/      los dos motores de DWG y el guión que los llama
export/     dxf.py (DXF y DWG) · pdf.py (PDF y PNG)
ui/         base · vista · osnap · entrada · seleccion · comandos · dibujar ·
            editar · cotas · bloques · papel · suite · barra · app
pruebas/    t001 a t015, más el arranque del navegador (navegador.py)
server.py   el backend
verificar.py  15 pruebas, 341 comprobaciones
claude/     el handoff del chat que reconstruyó la app, y el semáforo
```

El manual —qué hace cada comando, qué quedó corto y por qué— está en
[`LEEME.md`](LEEME.md).

## De dónde salió este repositorio

shape101 se compiló y publicó durante meses **desde chats, sin repositorio**. El
código sólo vivía dentro del instalador publicado; el 10-sep-2026 se
reconstruyó abriendo `shape101-0.20.1-setup.exe`, que es un NSIS con
`resources\app\` sin asar —Python, JS, CSS, fuentes y licencias en claro—. Lo
único que no viajaba dentro eran las pruebas, que se volvieron a escribir.

El árbol que está aquí es el de `shape101-fuente-X.0.2.zip`, que Mike dejó en
Drive. Su huella, para que se pueda comprobar que es el mismo:

```
sha256  fbfcfbac17d40869f5af9cfcc28ca10299480440b1fc98ccc123c8e4d1e8980c
bytes   6 566 519
```

Se usa **sha256** y no md5 porque es lo que usa el resto de la suite —
`descargas/nest101.json`, las releases y los `UNIR-X.bat` que juntan los pedazos
del instalador—, y dos huellas distintas para lo mismo se acaban contradiciendo.

## Lo que no está aquí y cómo se repone

| Qué falta | Cuánto pesa | Cómo vuelve |
|---|---|---|
| `runtime/python/` | ~140 MB (lo dice el handoff) | Se saca de un instalador ya publicado: `7z x shape101-0.20.1-setup.exe -oX` y se copia `X/resources/python/` a `runtime/python/`. Es más rápido y más fiel que armarlo con pip, porque es exactamente el intérprete con el que el taller ya trabaja. |
| `node_modules/` (la raíz) | no medido | `npm install`. Son Electron y electron-builder: sólo hacen falta para armar el instalador. |
| `dist/` | el instalador, ~120 MB | Lo deja `npx electron-builder --win nsis`. |

**`dwgjs/node_modules/` sí está versionado, a propósito.** Son los dos motores
de DWG —LibreDWG compilado a WebAssembly y acad-ts—. `npm install` no garantiza
la misma versión, y con otra versión shape101 deja de abrir planos que hoy abre.

Después de reponer cualquiera de los tres, se comprueba la huella de lo que se
repuso antes de armar nada:

```bash
sha256sum shape101-0.20.1-setup.exe     # contra la que publica descargas
find runtime/python -type f | wc -l    # y que el conteo cuadre con el origen
```

## Correr en desarrollo

```bash
npm install
npm start                        # Electron levanta el backend solo
python server.py --port 8760     # o sólo el backend, en el navegador
python verificar.py              # las 15 pruebas, 341 comprobaciones, ~50 s
```

Las pruebas de interfaz arrancan el programa de verdad con Playwright; si no
hay Playwright, o no hay Node para las de DWG, **se saltan diciéndolo** en vez
de fallar. Ninguna escribe en la carpeta del usuario: `verificar.py` apunta
`HOME` a un temporal antes de importar nada.

## Armar el instalador

```bash
npm install
apt-get install wine wine32      # hace falta el de 32 bits, ver abajo
npx electron-builder --win nsis  # deja dist/shape101-X.0.2-setup.exe
```

Cuatro cosas que costaron un intento cada una:

1. **Wine, y de 32 bits.** No es para firmar: NSIS fabrica el desinstalador
   corriendo el instalador una vez, y el instalador es x86. Con sólo wine de 64
   bits falla con `failed to load ntdll.dll`. Son `dpkg --add-architecture
   i386` y `wine32`.
2. **`signAndEditExecutable: false`.** Sin eso electron-builder llama a
   `rcedit` y pide wine antes de empezar. El costo: el `.exe` conserva el icono
   de Electron; el de shape101 sí sale en la ventana, la barra de tareas y los
   accesos directos, que es donde se ve.
3. **`asar: false`.** `electron/main.js` arranca `server.py` como archivo de
   disco junto a `electron/`. Dentro de un asar no hay archivo que arrancar.
4. **`extraResources` copia `dwgjs/node_modules` a mano.** electron-builder saca
   cualquier `node_modules` de los globs de `files`, sin avisar. La primera
   entrega salió con buena cara —118 MB, instalador válido— y **sin los dos
   motores de DWG**.

**La versión se declara en un solo lugar**, `core/version.py`. `package.json`
dice `0.20.1` porque electron-builder exige semver; ése no es el número que ve
el taller.

## Lo que está abierto

El estado completo, con las mediciones y las decisiones que quedan, está en
[`claude/shape101-handoff.md`](claude/shape101-handoff.md). Lo más grande:

- **Fluidez (objetivo 1).** Está medido dónde se va el tiempo y hay tres
  caminos planteados; falta que Mike corra `PERF` y `DIAG` en su máquina con su
  plano de verdad para decidir cuál.
- **El puente con suite101.** shape101 todavía no habla con la base unificada
  (Cloudflare Durable Objects / OrgDB): la feature 74 deja el paquete para
  SUPERVISOR en una carpeta y ahí se queda.

Cómo opera un chat en este repositorio: [`OPERAR.md`](OPERAR.md).
