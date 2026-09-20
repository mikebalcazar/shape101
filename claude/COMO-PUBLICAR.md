# Cómo se compila y se publica shape101

*Todo lo que hace falta saber para sacar una versión, y todas las trampas que
ya nos costaron una vuelta. Si vas a publicar, lee esto primero.*

**shape101 es un producto independiente.** No depende de draw101 para nada:
ni para armarse, ni para correr, ni para actualizarse. Comparten un antepasado
y ahí se acaba el parentesco. Si encuentras una mención a draw101 en el código
o en un flujo, es deuda: bórrala.

---

## La receta, en tres pasos

1. **El código, en `main`.** Los cambios se empujan a `main` como siempre.
2. **La versión, en dos sitios que deben decir lo mismo:**
   - `core/version.py` → `VERSION = "X.Y.Z"` y una entrada arriba en `BITACORA`
   - `package.json` → `"version"`, `"_versionApp"` y `"artifactName"`
   Si no coinciden, el armado se niega en el segundo paso y no gasta un armado.
3. **Crear la rama `claude/publicar-X.Y.Z`** apuntando al commit que quieres
   publicar. Eso dispara `armar-y-publicar.yml` y ya no hay que hacer nada más.

Unos 20 minutos después, `descargas/shape101.json` dice la versión nueva y el
instalador se puede bajar. Esa es la única señal que cuenta: **nunca des por
publicada una versión sin leer ese archivo.**

---

## Qué hace el armado, paso a paso

Corre en `windows-latest` porque el producto es para Windows.

1. **Parches pendientes** (`claude/APLICAR.txt`) — casi siempre vacío.
2. **Versión y tag coinciden** — la comprobación barata que evita las caras.
3. **Python empotrado** — se baja la **última release de shape101** y se le saca
   su Python de dentro. Ver abajo, que tiene truco.
4. **El kernel de sólidos** — `build123d` dentro de ese Python, y una prueba de
   que el kernel y la app conviven (una caja de 6 caras).
5. **Dependencias de Electron** y **motores DWG presentes**.
6. **Pruebas** — `python verificar.py`, las 28 pruebas. Si una falla, se detiene
   aquí y no se publica nada. Esto es lo que nos ha salvado más veces.
7. **Armar el instalador** — `electron-builder --win nsis`, ~250 MB.
8. **Preparar la carga** — se parte en pedazos y se calcula la huella sha256.
9. **Artefacto del run** y **poda**: sólo se guardan los 3 instaladores más
   recientes.
10. **Cargar a `descargas`** — una rama `claude/carga-shape101-X.Y.Z` que dispara
    allá el flujo que crea la release.
11. **Esperar la release y comprobarla** — se baja el instalador publicado y se
    compara su huella con la del armado. Sólo entonces se toca el manifiesto.
12. **El cuaderno**, pase lo que pase. Ver «cuando algo falla».

---

## El Python empotrado: de dónde sale y por qué tiene truco

El instalador lleva dentro un Python de Windows con todo puesto: `ezdxf`,
`fastapi`, `numpy`, `pillow`, `reportlab` y el kernel `build123d`. Armar eso
desde cero en cada corrida sería lentísimo, así que **cada armado lo hereda del
instalador anterior de shape101** y sólo le pone encima lo que falte.

**Cuál es ese instalador no se escribe a mano.** El flujo lo saca del
manifiesto de `descargas`:

```yaml
MANIFIESTO: https://raw.githubusercontent.com/mikebalcazar/descargas/main/shape101.json
```

y de ahí lee la URL del `.exe` publicado ahora mismo. Se hizo así en la 0.18.0
después de que el armado de la 0.17.0 muriera en un minuto: la URL estaba
escrita a mano apuntando a la 0.13.0, y la poda automática —que deja las 3
releases más nuevas— se había llevado esa release. **Dos cosas nuestras que
funcionan bien, juntas se rompían.** Ahora la poda y el armado no se pueden
contradecir, porque los dos miran el mismo archivo.

Dos cosas más que hay que saber:

**1. Está en dos capas.** El NSIS de electron-builder guarda toda la app dentro
de `$PLUGINSDIR/app-64.7z` y sólo deja el icono suelto. Hay que abrir el `.exe`
y después el `.7z` de dentro. Medido el 19-sep bajando el instalador y mirando:

```
$PLUGINSDIR/app-64.7z   248 MB   ← aquí vive resources/python
resources/icon.ico       53 KB   ← lo único suelto
```

**2. REGLA QUE NO SE ROMPE: la release que anuncia el manifiesto nunca se
borra.** Es el cimiento del siguiente armado. El 19-sep se limpiaron releases
viejas y con ellas se fue el archivo del que salía el Python; el armado murió
en 19 segundos durante horas sin que nadie entendiera por qué. La poda
automática deja las 3 más nuevas y el manifiesto anuncia la más nueva de todas,
así que hoy la regla se cumple sola — pero si alguien borra releases a mano,
que mire antes qué dice `descargas/shape101.json`.

---

## Secretos (los pone Mike, una vez)

| secreto | para qué | sin él |
| --- | --- | --- |
| `TOKEN_SHAPE101` | escribir en shape101 (recados, cuaderno) | los recados no reportan nada |
| `TOKEN_DESCARGAS` | publicar en `descargas` | arma y prueba, pero no publica |

Los tokens caducan. Si un armado llega hasta el final y dice *«Falta el secreto
TOKEN_DESCARGAS»*, es que expiró: se renueva en Settings → Developer settings →
Personal access tokens, con acceso sólo a `descargas` y permiso Contents: RW.

---

## El canal de vuelta: dónde mirar cuando algo falla

El chat no alcanza el log de Actions. Por eso todo deja rastro en el propio
repositorio:

| dónde | qué dice |
| --- | --- |
| `claude/ultimo-recado.md` en `main` | qué hizo el último recado que salió bien |
| rama `claude/recado-fallo` | dónde se rompió un recado |
| rama `claude/ultimo-armado` | lo que imprimió **cada paso** del armado, salga bien o mal |

**Orden para diagnosticar**, de lo barato a lo caro:

1. ¿`descargas/shape101.json` dice la versión nueva? Si sí, ya está publicada.
2. ¿`claude/ultimo-recado.md` es del recado que disparaste? Si no, el recado no
   corrió o falló: mira `claude/recado-fallo`.
3. ¿El cuaderno de `claude/ultimo-armado` es de tu versión? Ahí está el motivo
   exacto, con lo que imprimió cada paso.
4. Si **nada** corrió y no hay ni fallo escrito, no es el código: es la cuenta.
   Mira la pestaña Actions del repo y la página de facturación. Ya nos ha
   pasado por 2FA obligatorio y por cuota de minutos agotada.

**Agujero conocido:** un recado que muere *antes* de clonar no tiene dónde
escribir. Si el reporte no aparece en absoluto, sospecha del token.

---

## Trampas que ya costaron una vuelta

- **Mover una rama al commit donde ya está no dispara nada.** Git no ve cambio,
  GitHub no manda evento. Para volver a disparar hay que hacer un commit de
  verdad primero.
- **Las comprobaciones miran código, no palabras.** Buscar `window.prompt` como
  texto encuentra el comentario que explica por qué no se usa. Busca la llamada,
  con paréntesis.
- **Los archivos de `ui/` traen CRLF.** Cada inserción respeta el final de línea
  del archivo o git marca el archivo entero como cambiado.
- **Hay dos Pythons en el armado**: el empotrado (va al instalador) y el del
  corredor (corre las pruebas). Lo que las pruebas importen tiene que estar en
  el segundo.
- **Windows cuenta doble** en los minutos de Actions. Con el repositorio público
  son gratis; si vuelve a privado, cada armado cuesta el doble de lo que dura.
- **No dispares un armado sin comprobar antes todo lo comprobable sin Windows**:
  `node --check` en el JS tocado, `ast.parse` en el Python, y las cuentas que se
  puedan hacer con `node` o `python` a secas.

---

## Numeración

`mayor.menor.parche`:

- **parche** — se arregló algo, nada nuevo que aprender.
- **menor** — hay función nueva o cambió cómo se comporta algo.
- **mayor** — 1.0.0 el día que el taller dibuje y modele una pieza completa aquí
  sin volver a otro programa.

Un número no se repite nunca con contenido distinto. Si una versión se armó mal
y no llegó a publicarse, se puede reusar; si llegó a `descargas`, no.
