# Las pruebas de shape101

```
python verificar.py              todas
python verificar.py t008 t015    sólo ésas
```

Quince pruebas, **341 comprobaciones**, unos 50 segundos. Sale una línea por
prueba y, si algo falla, el renglón dice qué se esperaba y qué salió.

| Prueba | Qué cubre |
|---|---|
| `t001_dxf` | ida y vuelta de las entidades nativas; una spline y una cota ajenas salen intactas después de editar el archivo |
| `t002_historial` | deshacer, rehacer, transacciones con nombre, orden de dibujo y tope |
| `t003_capas` | plantilla de dos capas, nombres que AutoCAD rechaza, grosores fuera de tabla, herencia y bloqueo |
| `t004_proyecto` | `.t101d`, guardado atómico, autoguardado aparte y recuperación |
| `t005_interfaz` | el programa manejado con un navegador real: arranque sin errores, línea de comando, el espacio que confirma, la barra anclada a los cuatro lados |
| `t006_entrada` | las ocho referencias contra geometría de respuesta conocida, ortho y las cuatro formas de dar un punto |
| `t007_dibujo` | dibujar y editar **con el ratón**, comprobando la geometría exacta que quedó en el motor |
| `t008_cotas` | medida, asociatividad al estirar y al trasladar, la capa COTAS y que salgan como DIMENSION |
| `t009_papel` | escala real en el papel, recorte de la ventana, pie de plano, PDF y PNG |
| `t010_suite` | `.t101x`: bloques, capas separadas, acotado, regenerar sin perder anotaciones, paquete para SUPERVISOR |
| `t011_flujo` | el día completo: cocina → dibujo → anotación → actualización → hoja → PDF → DXF → guardar y reabrir |
| `t012_dwg` | DWG con los dos motores empotrados, capas encendidas y unidades (incluido el encabezado que miente) |
| `t013_ajeno` | un plano de fuera: se pica y se borra, y al osnap se le ignora a propósito |
| `t014_rapidez` | que una acción cueste lo que cambió y no lo que mide el plano, y que lo pintado sea lo que hay en el servidor |
| `t015_unir` | UNIR: contornos sueltos, arcos en los dos sentidos y en los dos órdenes, y lo que no se toca no se une |

## Cómo están escritas

**Cada comprobación dice qué debería pasar, en el idioma del taller.** No hay
`assertEqual(a, b)`: hay «el bulge del vértice curvo vuelve igual (un arco no se
aplana)». Cuando una falla, el renglón se lee solo y no hace falta abrir el
archivo para saber qué se rompió.

**Ninguna prueba escribe en la carpeta del usuario.** `verificar.py` apunta
`HOME` a una carpeta temporal antes de importar nada: preferencias,
autoguardado y caché van ahí. Por eso dan el mismo resultado en la máquina de
Mike y en el armador.

**Las de interfaz arrancan el programa de verdad.** Un servidor en un puerto
libre, un Chromium con Playwright y las funciones del propio programa llamadas
desde dentro de la página (`pruebas/navegador.py`). Una prueba de interfaz que
reimplementa la interfaz sólo comprueba que la copia se parece a sí misma. Si
en la máquina no hay Playwright, esas cuatro se saltan diciéndolo, en vez de
fallar por algo que no es del programa. Lo mismo hace `t012` si no hay Node.

**Se compara contra números escritos a mano**, no contra lo que devuelva el
programa: un rectángulo de 1 000 × 600, un círculo de radio 200, un 3-4-5 que
mide 500. Una prueba que pregunta el resultado y luego lo da por bueno no
protege de nada.

**El control también se comprueba.** Cuando una prueba dice «aquí NO tiene que
pasar nada» —el osnap que ignora lo ajeno— se comprueba al lado que en el caso
normal **sí** pasa. Si no, la prueba pasaría el día que el osnap deje de
enganchar del todo.

## Lo que estas pruebas ya cazaron

- **La cota que se iba de lado al estirar** (`t008`). Al estirar una pieza
  acotada por un extremo, la línea de cota se movía siguiendo un traslado que
  nunca ocurrió. Sólo se apuntaban los desplazamientos de los puntos que
  cambiaban, así que un estirado quedaba con un solo desplazamiento en la lista
  y la prueba de «todos iguales» se cumplía sola. Arreglado en `core/cotas.py`.
- **Que `encapar` no vive donde dice vivir.** La regla «toda cota nace en
  COTAS» está escrita en el motor, pero hoy la aplica quien crea la entidad
  (`server.py`), no `Documento.agregar`. Vale para todo lo que entra por la API
  y por la interfaz; una cota creada llamando al documento directamente se
  quedaría en la capa activa. No se cambió porque mover la regla a `agregar`
  tocaría también la lectura de archivos ajenos, y eso es una decisión, no un
  arreglo.
