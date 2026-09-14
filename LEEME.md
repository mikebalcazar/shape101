# shape101 — versión 0.12.1

CAD 2D de Taller 101. App aparte, con la identidad de Taller 101 y los colores
del logotipo invertidos: fondo blanco, «101» azul.

**Las 80 funcionalidades del plan están hechas.** Se puede abrir un plano ajeno,
dibujarlo, editarlo, acotarlo, armar la hoja e imprimirla, traer una cocina de
Taller 101 y devolver el paquete a SUPERVISOR.

**Abre DWG sin instalar nada aparte.** Los motores viajan dentro. Si además
está el ODA File Converter en la máquina, se usa ése, que es más fiel.

Lo que falta es lo que no se puede hacer desde aquí: correrlo en Windows de
verdad y comprobar que un DXF nuestro abre bien en AutoCAD y en Rhino. Eso lo
prueba el taller.

## Lo que hay que saber de la 0.11.0

- **La pantalla de inicio** sale al abrir, con los planos recientes. `Ctrl+I`
  la vuelve a llamar.
- **Pestañas**: varios dibujos abiertos a la vez. `Ctrl+N` abre uno, `Ctrl+Tab`
  pasa al siguiente, `Ctrl+W` cierra. Cada pestaña tiene su propio deshacer.
- **Las referencias a objetos** —extremo, medio, centro, cuadrante,
  intersección, perpendicular, nodo y cercano— se encienden y apagan en un
  cuadro: comando `MODOSREF`, o clic derecho en el botón `REF` del pie. También
  funcionan **al jalar un extremo con el ratón**, que es lo que faltaba.
- **Las cotas** nacen con texto de 30 mm en el dibujo. Se cambia en
  `ESTILOCOTA`. Ojo con las dos columnas: la altura va en **milímetros de
  papel** y se multiplica por la escala de la cota. Así, al meter el dibujo en
  una hoja, el texto sigue midiendo lo mismo impreso.
- **La capa de trabajo se cambia con doble clic**, no con uno. Un clic sólo
  enseña sus propiedades.
- **Hojas** en A0–A4, carta, tabloide o a la medida, y el pie de plano, todo en
  el mismo cuadro: comando `PLANO`.
- **El rectángulo acepta medidas**: primera esquina, `M`, ancho, alto.
- **Ctrl+P imprime en papel**; `IMPRIMIR` sigue sacando el PDF.

## Abrir un DWG desde el Explorador

Clic derecho en un `.dwg` o un `.dxf` → **Abrir con** → shape101.

El instalador **no** se queda con los DWG: si en esa máquina los abre AutoCAD,
los sigue abriendo AutoCAD. shape101 sólo se agrega a la lista. Para cambiarlo,
«Abrir siempre con», o Configuración → Aplicaciones → Aplicaciones
predeterminadas.

## Seleccionar

- Un clic toma lo más cercano. Si hay **varias cosas encimadas**, sale un menú
  para elegir; al pasar por cada renglón se enciende esa entidad en el dibujo.
  Se apaga con la preferencia `menu_seleccion`.
- **Ctrl+clic** suma a la selección (⌘ en Mac). Shift no: **Shift+arrastrar es
  mover la vista**, junto con el botón central y el derecho.
- Ventana de izquierda a derecha: sólo lo que queda entero dentro. De derecha a
  izquierda: todo lo que toque.

## La versión

El número está a la derecha del pie de la ventana. Escribiendo **`VERSION`** en
la línea de comando sale qué trae esa entrega. Cuando reportes algo, ese número
es lo primero: hasta la 0.9.0 salieron ocho instaladores distintos con el mismo
nombre y no había manera de saber cuál era cuál. Ya no puede pasar — el armador
se niega a repetir número si el código cambió.

---

## Cómo se instala

En la carpeta `instalador\` están los pedazos del instalador y `UNIR.bat`.

1. Doble clic en **`UNIR.bat`** — junta los pedazos, comprueba el tamaño y deja
   `shape101-0.12.1-setup.exe` (120 MB).
2. Doble clic en el `.exe`. Instala en `C:\Program Files\Taller 101\shape101`,
   deja acceso directo en el escritorio y en el menú, y asocia los `.t101d`.

**Windows va a avisar que no reconoce el editor.** El instalador no está firmado
—quitarlo pide un certificado EV de firma de código— así que en la pantalla azul
de SmartScreen hay que dar «Más información» → «Ejecutar de todas formas». Es lo
mismo que pasa con el instalador de Taller 101.

**No hace falta instalar Python ni nada más**: el instalador trae dentro su
propio Python 3.11 con ezdxf, FastAPI, uvicorn, numpy, pillow, reportlab y
PyMuPDF. Ocupa 422 MB instalado.

Desinstala desde «Agregar o quitar programas». **Los dibujos no se tocan**: viven
en `%USERPROFILE%\Taller 101\shape101` y siguen ahí.

## Cómo se arranca sin instalar

Doble clic en **`shape101.bat`**.

Usa el Python que ya trae **Taller 101** instalado: ahí dentro están ezdxf,
FastAPI, uvicorn, numpy, pillow y reportlab, que es exactamente lo que
shape101 necesita. No hay nada que instalar y nada que se pise con Taller 101.

Si algo no arranca, **`Diagnostico.bat`** dice qué falta y dónde.

Se abre el navegador con el programa. La ventana negra que queda detrás es el
motor: cerrarla cierra el programa.

*(Sirve para probar el código sin instalar, y para trabajar sobre él.)*

---

## Las 80, y cómo quedaron

### F0 · Cimientos
`2` abrir DXF · `4` guardar DXF R2013 · `5` formato propio `.t101d` ·
`9` autoguardado con recuperación · `10` deshacer/rehacer · `45` capas ·
`46` catálogo Taller 101 (**un dibujo nuevo nace con dos capas**) · `47` tipos de línea · `48` grosores ·
`49` color por capa/objeto

### F1 · Navegar y dar puntos
`11` zoom rueda/ventana/extensión/previo y pan · `12` rejilla y snap ·
`13` referencias a objetos (8 modos) · `14` ortho · `15` entrada dinámica ·
`16` coordenadas por teclado · `17` línea de comando (**el espacio confirma,
como en AutoCAD**) · barra de herramientas anclable a los cuatro lados o
flotante, con los iconos repartiéndose solos (`BARRA`)

### F2 · Dibujar
`18` línea · `19` polilínea · `20` rectángulo · `21` círculo · `22` arco por
tres puntos · `23` elipse · `24` spline · `25` punto · `26` rayado ·
`27` texto · `28` texto de párrafo

### F3 · Editar
`31` selección por ventana y cruce · `32` mover · `33` copiar · `34` rotar ·
`35` escalar · `36` espejo · `37` desfase · `38` recortar y extender ·
`39` empalme y chaflán · `40` arreglo rectangular y polar · `41` estirar ·
`42` grips · `43` panel de propiedades · `44` igualar propiedades · **`UNIR`** (varias líneas y arcos en una polilínea)

### F4 · Bloques y referencias
`29` crear e insertar bloques · `30` biblioteca del taller ·
`7` PDF vectorial de fondo · `8` imagen de referencia

### F5 · Cotas
`50` lineal · `51` alineada · `52` continua y línea base · `53` angular ·
`54` radio y diámetro · `55` directriz · `56` estilo configurable ·
`57` estilo Taller 101 · `58` asociativa · `59` escala automática

### F6 · Papel e impresión
`60` layouts · `61` ventanas con escala fija · `62` formatos A4–A0 con pie de
plano · `63` pie autollenado · `64` PDF · `65` impresora · `66` PNG ·
`67` lote de hojas en un PDF · `68` vista previa

### F7 · DWG
`1` abrir DWG · `3` guardar DWG — sin instalar nada, con tres motores en cascada

### F8 · Puente con la suite
`6` importar `.t101x` · `69` vistas 2D acotadas · `70` cada mueble como bloque ·
`71` capas separadas · `72` regenerar sin perder anotaciones · `73` hoja por
mueble · `74` paquete para SUPERVISOR

### F9 · Extras
`75` medir · `76` tabla de cantidades · `77` referencia externa ·
`78` comparar versiones · `79` tema claro/oscuro · `80` atajos propios

---

## Dónde se quedó corto, dicho claro

Ninguna de estas es un bug: son decisiones, y conviene saberlas antes de
toparse con ellas.

| # | Qué hace | Qué no |
|---|---|---|
| `1` | Abre DWG de R2000 a R2018 sin instalar nada | El DWG es formato cerrado: estos motores lo leen por ingeniería inversa. **No se ha probado con un plano real de los que te mandan** |
| `3` | Guarda DWG sin instalar nada | Lo escribe acad-ts, no AutoCAD. **Para entregar, el DXF es lo seguro** |
| `26` | Se raya eligiendo el contorno cerrado | No se pica dentro para que adivine el contorno. Detectar islas en un plano medio dibujado falla más de lo que acierta |
| `38` | Recorta y extiende líneas y arcos | Polilíneas todavía no: hay que explotarlas |
| `65` | Sale el PDF y se abre para imprimir | No hay diálogo de impresora propio. El del visor de PDF hace lo mismo y lo conoce todo el mundo |
| `73` | Una hoja por mueble, acotada | El despiece pieza por pieza lo calcula **Taller 101** y lo exporta en DXF. Dos motores de despiece que se contradicen sería peor que uno |
| `74` | Deja PDF, DXF y `manifiesto.json` en una carpeta | No llama a SUPERVISOR: SUPERVISOR todavía no tiene puerta de entrada. El día que la tenga, cambia quién lee la carpeta, no lo que hay dentro |
| `1` | Lo que no modelamos —cotas, splines ajenas— **se ve** y se conserva | No se puede editar ni se le hace osnap: es dibujo de apoyo, sacado del archivo. Los números de una cota ajena salen en la unidad del archivo, no en la nuestra: es su cota, no la reescribimos |
| `8` | La imagen de referencia se ve y se calca | No viaja al DXF: una ruta absoluta dentro del plano de otro es una referencia rota |
| — | El icono sale en la ventana, la barra de tareas y los accesos directos | El `.exe` en sí conserva el icono de Electron: cambiarlo pide `rcedit`, que es un binario de Windows, y el instalador se compila desde Linux |

---

## DWG: cómo se lee sin depender de nadie

El DWG es formato cerrado de Autodesk. No hay librería de Python que lo lea, y
la salida de siempre —pedirle al usuario que instale el **ODA File Converter**—
convierte «el programa lee DWG» en «el programa lee DWG si antes te bajas otra
cosa». Para un taller que recibe planos en DWG, eso es no leerlos.

Ahora hay tres motores y se prueban en cascada:

| | Cubre | Va dentro |
|---|---|---|
| **ODA File Converter** | todo, y es el más fiel | no — su licencia no deja redistribuirlo. Si está instalado, se usa |
| **LibreDWG** (GNU, a WebAssembly) | R13 a R2018 **menos R2007** | sí |
| **acad-ts** (puerto de ACadSharp, MIT) | R2007, y además **escribe** DWG | sí |

R2007 es la razón de tener dos motores empotrados y no uno: es el formato más
retorcido de la familia, LibreDWG tropieza ahí, y acad-ts no. El programa cambia
de uno a otro solo y dice en el informe con cuál abrió.

Los dos motores empotrados son JavaScript. **No se empaqueta un Node aparte**:
Electron ya trae uno, y con `ELECTRON_RUN_AS_NODE=1` se comporta como un Node
pelón. Un intérprete de más, cero.

Los tres caminos desembocan en un DXF que lee el lector de siempre. No hay un
segundo importador que mantener.

### Tres cosas que sólo enseñó un plano de verdad

El primer DWG ajeno que entró —`I5103.dwg`, un export de Revit— destapó tres
fallos que las pruebas fabricadas no podían destapar. Vale la pena saberlas
porque las tres son del tipo que **no truena**:

**Las capas venían todas apagadas.** LibreDWG escribe el color de capa en
negativo en su DXF, y en DXF un color negativo quiere decir «capa apagada». El
plano abría con las 31 capas apagadas: en blanco, como si lo hubiéramos perdido.
Ahora el encendido lo pone acad-ts, que lo lee bien, y la geometría la sigue
poniendo LibreDWG, que la lee mejor.

**El plano venía en metros.** `$INSUNITS = 6`. Tratado como milímetros, un
mueble de 0.6 en vez de 600 y una cota que dice «1» donde va «1000». No se ve
raro en pantalla —el dibujo es idéntico, sólo cambian los números— y sale a la
luz cortando una pieza. Ahora se convierte al abrir y se avisa (`core/unidades.py`),
con freno: si el encabezado no cuadra con el tamaño del dibujo, no se le hace
caso. `ezdxf.new()` pone metros por omisión aunque el dibujo esté en milímetros,
así que ese freno no es teórico.

**Los rayados y las cotas del arquitecto no se veían.** Los 77 rayados del
archivo traían el contorno por aristas —líneas, arcos, splines— y no por
vértices, que es lo único que el lector entendía. Y las 49 cotas se conservaban
tal cual, correctamente, pero **invisibles**. Ahora los rayados entran nativos, y
lo que se conserva sin modelar guarda además cómo se dibuja, sacado del propio
archivo. Un plano ajeno al que le faltan las cotas parece un plano al que le
faltan las cotas, y eso es justo lo que no queremos que parezca.

**Al guardar en DWG hay una advertencia y es en serio:** el DXF que produce
shape101 es el archivo que está auditado entidad por entidad; el DWG sale de
traducirlo, y esa traducción no la hizo Autodesk. Para entregar, DXF. El DWG
está para cuando del otro lado lo piden así.

Tipografías: Raleway y Sansation (OFL) para el texto; **Fira Sans** (OFL, `assets/fonts/OFL-FiraSans.txt`) sólo para los dígitos y signos de medida, como subconjunto de 5 KB.

Las licencias —LibreDWG es GPL-3 y eso importa el día que shape101 salga del
taller— están en `dwgjs/LICENCIAS.md`.

---

## Lo que se aprendió editando un plano ajeno

Mike, con el primer DWG abierto: *«cuando quiero borrar un elemento, no se
borra»*.

**No era el borrado.** Era que no se podía **seleccionar**. Una entidad que el
programa no modela no tenía geometría con la que engancharla al ratón, así que
picarla no seleccionaba nada, y sin selección no hay nada que borrar. Desde que
lo ajeno se dibuja, se veía perfectamente… y no respondía al clic. **Ver algo
que no responde es peor que no verlo**, porque no parece una limitación, parece
que el programa está roto.

Ahora una entidad ajena aporta geometría de selección sacada de su propio
dibujo, marcada `aprox`. **El osnap la ignora a propósito**: el punto medio de
una raya teselada de una cota ajena no es el punto medio de nada, y en un plano
que va a la CNC ese pelo es una pieza mal cortada. Seleccionar no necesita
exactitud; medir sí. Es la misma línea que separa `core/dibujo.py` de
`core/geometria.py` desde el primer día.

### El espacio confirma

Como en AutoCAD: se dibuja con la izquierda en la barra espaciadora y la
derecha en el ratón, sin cruzar el teclado a buscar el Enter. La excepción es
cuando se pide **texto libre** —un rótulo, el nombre de una capa o un bloque—:
ahí el espacio es un espacio, porque «MESA DE TRABAJO» tiene que poder
escribirse.

El costo, dicho para que no sorprenda: los comandos que aceptan argumentos en la
misma línea (`ZOOM 2`) ya no se rematan con espacio, porque el espacio los
dispara antes. Para ésos, Enter.

### La barra se mueve, y **se reparte de verdad**

Arranca **flotante**, en fila. Se arrastra del asa y se ancla a la izquierda, la
derecha, arriba o abajo; si se suelta en medio, se queda flotando. Doble clic en
el asa la devuelve al último anclaje. También por comando: `BARRA arriba`.

**Los iconos se reparten solos**: si no caben en una fila, se hacen dos; anclada
a un lado, si no caben a lo alto, se hacen dos columnas. **Nunca sale una barra
de desplazamiento** — un icono al que hay que hacerle scroll es un icono que no
está, y ése fue exactamente el fallo del primer intento.

Lo que lo hacía fallar merece quedar escrito, porque es contraintuitivo: los
grupos de iconos eran cajas, así que `flex-wrap` repartía **grupos**, y un grupo
de catorce iconos no cabe en ninguna parte. La barra crecía y se le ponía scroll
en vez de partirse. La cura es una línea: `#herramientas .grupo{display:contents}`
— el grupo deja de ser caja, los botones pasan a ser hijos directos de la barra,
y el reparto es botón por botón. La separación entre grupos la hace un elemento
propio (`.corte`) que también entra en el reparto.

Sigue sin haber una sola cuenta de píxeles en JavaScript: el navegador reparte
y lo rehace solo al cambiar el tamaño de la ventana. Contar píxeles para partir
filas es de las cosas que se rompen con el primer icono que se agregue.

Dónde quedó se guarda en las **preferencias del usuario**, no en el documento:
dónde te gusta la barra no cambia porque abras otro dibujo. Misma regla que la
rejilla y las referencias.

---

## Por qué un comando tarda 40 milisegundos y no tres segundos

Mike, con un plano de 1 837 entidades: *«Los comandos tardan mucho… Incluso
para borrar se tarda mucho. Unos 3-5 segundos.»*

**El borrado tardaba 16 milisegundos.** Lo que tardaba era lo de después:
cada acción volvía a pedir `/api/trazos`, que tesela el documento completo y lo
manda por la red. En ese plano son 9 500 trazos y **6 MB de JSON** — más de un
segundo en la máquina de pruebas, tres a cinco en una de taller — para
enterarse de que se borró una línea.

La cuenta que lo arregla es evidente una vez vista: **el navegador ya tiene el
dibujo pintado.** Lo único que necesita saber es qué entidades cambiaron y cómo
quedaron. Eso son unos kilobytes, y **no crece con el tamaño del plano**, que es
la parte que de verdad importa porque los planos de obra sólo se hacen más
grandes.

Ahora cada endpoint que modifica algo devuelve un **parche** —`quitar`, `trazos`,
`geometria`— y el cliente lo aplica sobre lo que ya tiene. Si por lo que sea no
viene parche, recarga entero: lento, pero correcto. Entre pintar rápido y pintar
bien, gana pintar bien.

| en un plano de 1 850 entidades | antes | ahora |
|---|---|---|
| borrar | 1 100 ms | **42 ms** |
| dibujar una línea | 1 100 ms | **46 ms** |
| deshacer | 1 100 ms | **51 ms** |
| apagar una capa | 1 100 ms | **37 ms** |

### La caché, y el agujero que dejó al descubierto

Teselar es lo caro, y casi siempre se vuelve a hacer sobre entidades que no
cambiaron. Ahora se guarda por entidad, y se olvida en cuanto algo la toca.
**La regla es olvidar de más, nunca de menos:** una caché que se queda con un
trazo viejo enseña un dibujo que no es el del archivo, y eso se descubre
midiendo una pieza ya cortada.

Que esto sea posible se debe a una decisión vieja: todo cambio pasa por los
métodos de `Documento`. Si las herramientas tocaran las listas directamente, no
habría dónde poner la invalidación.

Y aun así se coló un error el mismo día: **una cota no depende sólo de sí misma
y de su capa, sino de su estilo.** Cambiar un estilo cambia las doscientas cotas
del plano sin tocar ninguna. Las pruebas `t008` y `t009` lo cazaron en la primera
corrida. La cura fue no cachear las cotas: son pocas, y quitarlas de la caché
elimina de golpe toda una familia de errores silenciosos.

---

## Las capas de un dibujo nuevo, y dónde nacen las cotas

**Un dibujo nuevo trae dos capas: `0` y `COTAS`.** No trece. Trece capas vacías
son trece renglones que hay que leer para encontrar la única que se está usando.
El catálogo de Taller 101 sigue completo —muros, cuerpo, frentes, cubierta,
herrajes, texto, ejes, oculto, rayado, rótulo, auxiliar— pero cada capa **se
crea cuando una herramienta la pide**, no antes. Las capas se ganan al usarse.

`COTAS` es azul Taller 101 (`#0080C1`), grosor 0.18.

### Toda cota nace en COTAS

Da igual en qué capa se esté trabajando: **una cota siempre se traza en
`COTAS`**. Si después se quiere mover, se mueve; pero no nace fuera.

La razón es de taller, no de programa: la capa de cotas se apaga entera para ver
el dibujo limpio, o se imprime aparte. Eso deja de funcionar en cuanto una cota
se queda regada en la capa de muros. Moverla después es un clic; **encontrar** la
que se quedó fuera, no.

La regla se impone **en el motor** (`core/cotas.py`, `encapar`), no en la
interfaz. Así vale igual para la cota que dibuja alguien, la que llega importada
de Taller 101 y la que entre por la API el día que haya una. Una regla que hay
que acordarse de aplicar en tres sitios no es una regla.

Si la capa no existe —un DWG ajeno, por ejemplo— se crea del catálogo, en azul.

---

## UNIR, y el Enter que cierra

**Enter (o espacio) en vacío termina el comando.** Se trazan tres líneas, se
remata con Enter y se acabó. Antes no hacía nada y la herramienta se quedaba
abierta encadenando desde el último punto.

Termina *el pedido de punto*, no la herramienta: por eso una polilínea se cierra
y **se crea con lo que lleva** en vez de perderse. Cada herramienta ya sabía qué
hacer cuando se le acaban los puntos; lo que faltaba era decírselo.

Funciona con el foco en el lienzo, que es donde está siempre: sin eso, el Enter
que cierra una línea no llegaba a ninguna parte.

### `UNIR` (`J`) — el JOIN de AutoCAD

Une líneas, arcos y polilíneas que **se tocan** en una sola polilínea. En un
taller se usa todo el tiempo: un contorno que llega de un plano ajeno viene
hecho de veinte líneas sueltas, y para rayarlo, desfasarlo o mandarlo a la CNC
hace falta que sea *una* cosa.

Tres cosas que carga el diseño:

**Los arcos no se pierden.** Un arco entra como `bulge` en el vértice donde
empieza, que es como el DXF guarda un arco dentro de una polilínea. Aplanarlo a
una recta sería más fácil de programar y convertiría una puerta redondeada en
una cuadrada. Y **el bulge cambia de signo** cuando la cadena recorre el arco al
revés: sin esa línea el arco sale curvado hacia el otro lado — un error que no
truena, no se ve raro, y aparece cuando la pieza llega al taller. La prueba lo
comprueba en los ocho casos de sentido y orden.

**Los extremos tienen que tocarse de verdad.** La tolerancia es 0.05 mm, no «lo
que se vea cerca». Unir dos líneas separadas medio milímetro mueve el dibujo sin
avisar, y este programa existe para planos que se cortan.

**Lo que no se une, no se toca.** Una pieza suelta se queda como estaba, con su
id, y el mensaje dice cuántas quedaron fuera y por qué. Un UNIR que sólo acierta
con la mitad no obliga a deshacer para recuperar la otra.

Un Ctrl+Z devuelve **todas** las piezas: la unión es una sola transacción.

*(La polilínea ya existía desde F2: `POLILINEA` / `PL`, o el icono `⌇`.)*

---

## Las decisiones que cargan el resto

**DXF ASCII R2013 nativo, DWG por ODA.** Lo abren AutoCAD 2013+, Rhino,
BricsCAD, LibreCAD, QCAD, Illustrator, Inkscape y Fusion, y soporta MTEXT,
HATCH, DIMENSION, bloques, layouts y viewports.

**El `.t101d` es el trabajo; el DXF es la entrega.** El DXF no guarda el
historial de deshacer, ni la liga de una cota con la pieza que mide, ni de qué
`.t101x` vino el dibujo.

**Nada se pierde en silencio.** Lo que el modelo entiende entra como entidad
editable; lo que no —splines ajenas, objetos propietarios— se deja donde está:
al exportar se parte del archivo original. Devolverle a un arquitecto su plano
sin cotas es el error que este diseño existe para no cometer.

**El deshacer va en los cimientos.** Cada operación anota su inversa, agrupada
en transacciones con nombre, para que un Ctrl+Z deshaga *una acción del
usuario* — un rectángulo entero, un arreglo de cuarenta copias.

**El osnap trabaja sobre geometría exacta, no sobre lo que se pinta.** El punto
medio de un arco teselado no es el punto medio del arco, y en un plano que va a
la CNC esa diferencia es una pieza mal cortada.

**El selector de punto existe antes que las herramientas.** Cada herramienta de
dibujo y de edición se reduce a «pídeme un punto, y otro»: por eso son cortas y
por eso todas se comportan igual.

**Una cota guarda lo que mide, no las rayas.** Cambiar el estilo cambia las
doscientas cotas del plano; mover la pieza mueve su cota.

**La hoja se pinta con los mismos trazos que van al PDF.** Si la pantalla y la
impresora se dibujaran por caminos distintos, la única forma de enterarse sería
imprimiendo.

**Lo blanco se imprime negro.** El papel es blanco: mandarle una capa blanca tal
cual imprime una hoja vacía. Los plotters de verdad hacen esta misma traducción.

**Las preferencias son del usuario; la biblioteca de bloques, del taller.**
Rejilla, ortho y referencias viven en `~/Taller 101/shape101/preferencias.json`;
los bloques en `~/Taller 101/shape101/bloques`. Misma lección que los
materiales de Taller 101: el estándar es del taller, no del proyecto.

---

## Cómo está armado

| | |
|---|---|
| **Motor** | Python 3.11 — ezdxf, reportlab, pillow, pypdfium2, numpy |
| **DWG** | LibreDWG (WebAssembly) y acad-ts, corridos con el Node de Electron |
| **Backend** | FastAPI + uvicorn en 127.0.0.1 |
| **Interfaz** | HTML/CSS/JS con canvas 2D, sin empaquetador |
| **Envoltura** | Electron (para el instalador) |

El documento vive **en el servidor**, no en el navegador: un plano de obra son
decenas de miles de entidades y mandarlo entero en cada clic no aguantaría.

```
core/     documento, entidades, capas, historial, geometría exacta, cotas,
          papel, importación de .t101x y de PDF, preferencias, dwg, unidades,
          unir
dwgjs/    los dos motores de DWG y el guión que los llama
export/   dxf.py (DXF y DWG) · pdf.py (PDF y PNG)
ui/       base · vista · osnap · entrada · seleccion · comandos ·
          dibujar · editar · cotas · bloques · papel · suite · barra · app
pruebas/  t001 a t011 + capturas
```

---

## Verificación

```
python verificar.py
```

| Prueba | Qué cubre |
|---|---|
| `t001_dxf` | ida y vuelta de las entidades nativas; una spline y una cota ajenas salen intactas después de editar el archivo |
| `t002_historial` | deshacer, rehacer, transacciones, orden de dibujo, tope |
| `t003_capas` | plantilla, nombres inválidos, grosores que AutoCAD rechaza, herencia, bloqueo |
| `t004_proyecto` | `.t101d`, guardado atómico, autoguardado, recuperación |
| `t005_interfaz` | el programa manejado con un navegador real |
| `t006_entrada` | las ocho referencias contra geometría de respuesta conocida, ortho, snap, las cuatro formas de dar un punto |
| `t007_dibujo` | dibujar y editar con el ratón, comprobando la geometría exacta |
| `t008_cotas` | medida, asociatividad, y que salgan como DIMENSION |
| `t009_papel` | escala real en el papel, recorte de la ventana, pie de plano, PDF |
| `t010_suite` | bloques, PDF de fondo, importación de Taller 101, regenerar, paquete |
| `t011_flujo` | el día completo: cocina → dibujo → anotación → actualización → hoja → PDF → DXF → guardar y reabrir |
| `t015_unir` | UNIR: contornos sueltos, arcos en los dos sentidos y en los dos órdenes, lo que no se toca no se une, y que Enter cierre el comando |
| `t014_rapidez` | que una acción en un plano grande cueste lo que cambió y **no** lo que mide el plano, y que lo pintado coincida con lo que hay en el servidor |
| `t013_ajeno` | editar un plano de fuera: que lo que no modelamos **se pueda picar y borrar**, que el espacio confirme como Enter, y que la barra se ancle a los cuatro lados repartiendo los iconos |
| `t012_dwg` | DWG de R2000 a R2018: se fabrican con un motor y se leen con el otro, y la geometría se compara contra números escritos a mano. Además: que las capas abran encendidas, y que las unidades se conviertan —y que no se conviertan cuando el encabezado miente— |

Las capturas de `pruebas/capturas/` salen de estas pruebas: son el programa de
verdad, no maquetas.

---

## Lo que hay que probar en el taller

1. **Que arranque en Windows.** Es el hueco de siempre: aquí no hay Windows.
2. **Abrir un plano de verdad** de los que te mandan, y ver qué preserva y qué
   entiende. El pie de la ventana lo dice siempre.
3. **Que el DXF abra bien en AutoCAD y en Rhino.** Se audita con ezdxf, que es
   lo que detecta el archivo mal formado, pero no sustituye abrirlo allá.
4. **Más DWG de verdad**, de los que te mandan. Ya pasó uno (`I5103.dwg`, de
   Revit, en metros) y destapó tres fallos. El siguiente destapará otros: es la
   única prueba que sirve.
5. **Una cocina real de Taller 101** por `T101X`, y luego `ACT` después de
   cambiarle algo allá.
