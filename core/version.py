"""La versión de shape101  ·  un solo lugar.

Hasta el 31-ago-2026 el número vivía escrito a mano en `build/armar_paquete.py`
y nadie lo subía: ocho instaladores distintos salieron llamándose todos
`DIBUJADOR-0.9.0-setup.exe`. Desde dentro de la app no había manera de saber
cuál estaba corriendo. Eso se acabó aquí:

  · el número se declara **una vez**, en este archivo;
  · `build/armar_paquete.py` lo lee de aquí para el `.nsi` y para el nombre
    del `.exe`;
  · la app lo enseña en el pie y el comando `VERSION` cuenta qué cambió;
  · el armador se niega a repetir versión si el código cambió (ver
    `build/entregas.json`).

Numeración: `mayor.menor.parche`.
  · **parche** — se arregló algo, nada nuevo que aprender.
  · **menor** — hay función nueva o cambió cómo se comporta algo.
  · **mayor** — 1.0.0 el día que el taller dibuje un plano completo aquí sin
    volver a AutoCAD.
"""

from __future__ import annotations

VERSION = "0.21.1"
FECHA = "2026-09-24"

# Qué trae cada entrega, en el idioma del taller y no en el del código.
# La más nueva arriba. Lo que se lista aquí es lo que el comando VERSION
# enseña en la consola.
BITACORA: list[dict] = [
    {
        "version": "0.21.1",
        "fecha": "2026-09-24",
        "cambios": [
            "Dibujar en la Perspectiva ya cae donde apuntas. Antes el programa leía el "
            "punto con la cámara de la ventana que estuviera activa, no con la de la "
            "ventana donde tenías el ratón: apuntando al centro de la Perspectiva con la "
            "Superior activa, el punto se iba 558 mm de donde señalaste. Ahora manda la "
            "ventana donde está el ratón, como en Rhino.",
            "Y el trazo en curso se ve en su sitio en las cuatro ventanas. La línea de "
            "hule no se acordaba de sobre qué plano se estaba trazando, así que cada "
            "ventana la pintaba con el suyo y lo trazado sobre el suelo se veía parado "
            "en la Frontal y en la Lateral — «como si fuera vista frontal».",
            "Empezada la línea, una ventana de otro plano ya no se la lleva: una línea no "
            "puede tener un extremo en el suelo y el otro en la pared. El hule se queda "
            "quieto mientras el cursor ande por ahí.",
        ],
    },
    {
        "version": "0.21.0",
        "fecha": "2026-09-24",
        "cambios": [
            "Ya se puede traer un dibujo de draw101. El comando IMPORTAR —o el botón "
            "«Importar…» de arriba— mete el dibujo 2D adentro de la pieza que tengas "
            "abierta, sin borrar lo que ya llevas. Lo que entra es dibujo de verdad: se "
            "señala y se levanta con EXTRUIR como cualquier contorno tuyo.",
            "Cae siempre acostado en el suelo. Un dibujo de draw101 es plano y no sabe de "
            "ventanas; ponerlo según dónde estuvieras parado acierta casi siempre y la vez "
            "que falla deja la pieza de canto sin que se entienda por qué.",
            "Las capas que traiga el dibujo y aquí no existan se crean solas. Las que ya "
            "tienes NO se tocan: traer un dibujo no puede repintarte tus propias capas.",
            "Abrir también acepta los dibujos de draw101, además del DXF y el DWG. Y "
            "abrir uno no te lo convierte en el archivo donde guardas: el dibujo 2D sigue "
            "siendo de draw101, y lo que levantes aquí se guarda aparte.",
            "ARREGLADO: el programa guardaba en .101s pero su propio diálogo de Abrir "
            "sólo ofrecía .t101d, así que las piezas que guardabas no aparecían cuando "
            "las querías volver a abrir. Y Guardar te volvía a pedir la ruta cada vez. "
            "El doble clic de Windows tampoco abría una pieza propia.",
            "ARREGLADO, y éste era el peligroso: traer otro dibujo encima de una pieza ya "
            "levantada la borraba, sin avisar. Los nombres internos de lo que entraba "
            "volvían a empezar desde uno y pisaban los que ya estaban ocupados.",
        ],
    },
    {
        "version": "0.20.1",
        "fecha": "2026-09-20",
        "cambios": [
            "La rejilla de la Perspectiva ya no se ve como tres planos espaciados. Se "
            "desvanecía a tres pasos, y las líneas quedaban cortadas en el borde de cada "
            "paso; esos cortes, vistos casi de canto cerca del horizonte, se leían como "
            "tres orillas. Ahora se apaga de una sola pieza: el tono baja hasta cero y ya, "
            "sin ningún corte en ningún lado.",
        ],
    },
    {
        "version": "0.20.0",
        "fecha": "2026-09-20",
        "cambios": [
            "La rejilla es una referencia de verdad: infinita. No se acaba en una orilla ni "
            "se queda descentrada —era un cuadro fijo de mil milímetros alrededor del cero—. "
            "Ahora se pinta lo que cabe en cada ventana, y el paso crece o se achica solo "
            "con el zoom, así que sirve igual para una pieza de 20 mm que para una nave.",
            "La Frontal y la Lateral tienen rejilla. No la tenían porque se pintaba siempre "
            "sobre el suelo, y el suelo desde la Frontal se ve de canto: era una raya. Cada "
            "ventana pinta ahora el plano en el que se dibuja.",
            "Se prende y se apaga por ventana, con el cuadrito del título, y en la "
            "Perspectiva por plano —XY, XZ, YZ—, con los tres cuadritos de su título. El "
            "botón REJILLA de abajo sigue mandando sobre todas, y apagarlo no borra lo que "
            "cada ventana tenía elegido.",
            "El botón REJILLA ahora apaga de verdad. Cambiaba la preferencia y la pantalla "
            "se quedaba igual, porque la rejilla se pinta dentro de algo que va en caché y "
            "nadie avisaba de que había cambiado.",
            "Más clara, y más clara todavía cuando hay varios planos encimados en la "
            "Perspectiva. Y ahí se desvanece hacia el horizonte en vez de apelmazarse: una "
            "rejilla en perspectiva junta las líneas hasta volverlas una mancha gris.",
            "Al abrir, las cuatro ventanas miran al cero. Las tres que no eran la Superior "
            "nacían con el origen en su esquina de arriba a la izquierda, y eso no era sólo "
            "feo: una pieza levantada después caía fuera de la Perspectiva, no se le podía "
            "picar una cara, y JALAR y CRECER se quedaban sin cara que mover.",
            "Extents encuadra las cuatro ventanas, no sólo la activa, y toma en cuenta las "
            "piezas y no sólo los trazos del dibujo: una pieza cuyo contorno se borró "
            "después de levantarla ya no se queda fuera de la cuenta.",
        ],
    },
    {
        "version": "0.19.0",
        "fecha": "2026-09-20",
        "cambios": [
            "Cuatro maneras nuevas de hacer una pieza, además de extruir. REVOLVER la tornea: "
            "señalas el contorno y la línea que hace de eje, y el contorno gira. BARRER la "
            "lleva por un camino: señalas el contorno y el camino. LOFT pasa una piel por "
            "varios contornos, en el orden en que los señalaste. CRECER levanta material "
            "nuevo con el perfil de la cara señalada —la cara se queda donde está; no la "
            "estira, le nace un sólido encima—.",
            "Los cuatro están en la barra y en la rueda del 3D, y Extruir no se movió de su "
            "sitio.",
            "El perfil y el camino de un barrido pueden estar en ventanas distintas: el "
            "perfil dibujado en la Frontal y el camino en la Superior. La pieza cae a "
            "caballo de las dos, que es como se dibuja un tubo de verdad.",
            "Quién es el contorno y quién el eje o el camino lo reparte el programa solo, "
            "por lo que cada cosa es: lo cerrado es el contorno, lo abierto es el eje o el "
            "camino. No hay que señalarlos en ningún orden.",
            "Si el contorno son líneas sueltas, el aviso lo dice y manda a juntarlas con "
            "UNIR, en vez de adivinar mal en silencio.",
            "Dos secciones dibujadas en la misma ventana necesitan una separación para el "
            "LOFT: dos contornos a la misma altura no encierran volumen. El programa lo "
            "dice así en vez de soltar el error del motor.",
            "Cada operación de la pieza tiene ahora su propio nombre interno, y ya no su "
            "número de renglón. Eso es lo que permite decir «este loft usa estos tres "
            "contornos» y lo que evita que meter un paso a la mitad del historial le "
            "cambie el nombre a caras que nadie tocó. Los archivos de antes se abren igual.",
            "Un boceto ya sabe sobre qué plano vive: el de su ventana, uno subido, una cara "
            "de la pieza, o uno libre. De una cara alabeada se puede sacar el plano "
            "promedio, y el programa dice cuánto se está mintiendo al proponerlo.",
        ],
    },
    {
        "version": "0.18.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Ya se eligen a mano las aristas que se van a redondear: Ctrl+clic sobre el "
            "círculo de en medio de una arista la elige, y se pinta en amarillo. Volver a "
            "picarla la quita.",
            "REDONDEAR usa las elegidas. Si no elegiste ninguna sigue tomando las "
            "verticales, como antes, así que nada de lo que ya hacías cambia.",
            "Ctrl y no un clic pelón porque el clic pelón ya significa «jalar esta "
            "arista», que es el gesto que más se usa: no se le quita el sitio.",
            "Ojo con la ventana: en la Superior una arista vertical se dibuja justo encima "
            "de su esquina, y ahí gana la esquina. Para elegir esas aristas, gira la vista "
            "o usa la Frontal o la Lateral.",
        ],
    },
    {
        "version": "0.17.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Cuando una operación parte una cara en dos —una muesca que entra por un "
            "costado, una ranura que cruza la pieza—, cada trozo se queda con su propio "
            "nombre: «lado[0]» y «lado[0]~2». Antes los dos trozos se peleaban el mismo.",
            "Y el nombre se queda en el mismo trozo aunque cambie la medida de la pieza. "
            "Antes, al estirar el tablero, el nombre saltaba al otro trozo sin avisar: una "
            "cara jalada se iba al otro lado de la pieza y el programa no decía nada. "
            "Comprobado con anchos de 450, 600, 900 y 2000.",
            "Jalar un trozo ya no deja al otro sin nombre. Antes se perdía, y con él se "
            "perdían los nombres de sus aristas y sus vértices, así que ya no se podía "
            "trabajar sobre ese trozo.",
            "Una ranura que parte la pieza en dos sólidos ya no pierde ni un nombre.",
        ],
    },
    {
        "version": "0.16.0",
        "fecha": "2026-09-19",
        "cambios": [
            "El contorno de una pieza ya tiene cotas que se teclean. El paso del historial "
            "se lee «Rectángulo 600 × 400» y trae Ancho, Fondo y la esquina donde empieza: "
            "cambiar el ancho a 900 es teclear 900, no arrastrar cuatro puntos.",
            "Estirar una medida no se lleva lo que hiciste después, y el barreno sigue "
            "redondo: en madera no hay barrenos ovalados.",
            "Sirve con cualquier contorno, no sólo rectángulos: una L se estira entera.",
            "La pieza señalada enseña sus tres medidas encima —ancho, fondo y espesor—. "
            "Se dibujan en píxeles, así que se leen igual con cualquier zoom. COTAPIEZA "
            "las apaga y las enciende.",
            "Y esas cotas se pican: le das clic al número, tecleas la medida y la pieza se "
            "rehace. Sin abrir el panel y sin comandos.",
            "El panel del historial ya no se salta una recarga cuando hay otra en vuelo. "
            "Antes, señalar una pieza y cambiarle un número en seguida podía dejarlo "
            "enseñando los pasos de antes.",
        ],
    },
    {
        "version": "0.15.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Las piezas traen su historial a la vista: al señalar una cara, el panel de la "
            "derecha dice con qué se hizo la pieza —contorno, extrusión, barrenos, redondeos— "
            "en palabras y no en código.",
            "Y sus números se tocan. Un barreno se agranda cambiando su diámetro en la "
            "cajita: no hay que volver a trazar el círculo ni repetir la resta.",
            "Lo que se hizo después sobrevive al cambio. Si redondeaste unas aristas encima "
            "de un barreno, siguen redondeadas cuando el barreno cambia de tamaño, y siguen "
            "redondeadas si borras el barreno del historial.",
            "Cada paso se puede quitar con su ×, menos el contorno y la extrusión: sin esos "
            "dos no hay pieza.",
            "Si un cambio deja la pieza imposible, se niega y la pieza queda como estaba. "
            "Tocar un número no puede romper nada.",
            "Dos comandos nuevos: BARRENO —se pica el centro y se da el diámetro— y "
            "REDONDEAR, que redondea las aristas verticales de la pieza señalada.",
        ],
    },
    {
        "version": "0.14.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Cada punto y cada arista de una pieza se mueven solos. Los tiradores ya no "
            "salen del contorno sino del sólido: la esquina de arriba y la de abajo son dos "
            "puntos distintos, y mover una ya no mueve la otra.",
            "Arrastrar el medio de una arista la corre entera, sin doblarla.",
            "El arrastre va en el plano de la ventana donde estás: en la Superior sobre XY, "
            "en la Frontal sobre XZ, en la Lateral sobre YZ.",
            "Una pieza puede dejar de ser un prisma: si una cara se alabea, se pone la "
            "superficie que pasa por sus cuatro puntos, sin inflarse.",
            "Lo que se hizo después —un barreno, una cara jalada— se sigue volviendo a "
            "aplicar solo: la pieza se guarda como cómo se hizo, no como geometría.",
            "Si un movimiento deja una pieza imposible, el programa lo dice y no cambia nada.",
            "Ctrl+Z ya redibuja al instante. Antes había que dar otro comando para ver el "
            "resultado de deshacer.",
        ],
    },
    {
        "version": "0.13.0",
        "fecha": "2026-09-19",
        "cambios": [
            "Las piezas traen tiradores: un cuadrito en cada esquina —abajo, a media altura y "
            "arriba— y un círculo en el medio de cada arista. Se arrastran y la pieza se rehace "
            "desde el contorno nuevo, sin perder lo que hayas hecho después.",
            "Arrastrar el medio de una arista corre la arista entera: se mueve, no se dobla.",
            "Con el ortho encendido, el tirador se va por un solo eje.",
            "Al abrir un archivo con piezas, las piezas ya se ven. Antes había que teclear 3D "
            "para que aparecieran, y un dibujo guardado se veía vacío de piezas.",
            "Deshacer una extrusión ya borra la pieza de la pantalla.",
            "Los grips del medio de una línea se ven en su sitio en las cuatro ventanas. "
            "Seguían proyectándose en planta, como la selección antes de la 0.12.0.",
            "El instalador es de shape101: icono propio —una pieza en isometría— y sus "
            "pantallas. Hasta ahora llevaba el icono de draw101.",
        ],
    },
    {
        "version": "0.12.1",
        "fecha": "2026-09-19",
        "cambios": [
            "Pan, zoom y órbita en una ventana que no es la activa ya no cambian de ventana "
            "activa ni devuelven las cuatro al centro. Movías una y se movía otra: el "
            "repintado de a mitad del gesto lo secuestraba.",
            "Shift + clic central en una ventana que no es la activa mueve esa, la de abajo "
            "del cursor, que es donde están las manos.",
        ],
    },
    {
        "version": "0.12.0",
        "fecha": "2026-09-19",
        "cambios": [
            "La selección se ve bien en las cuatro ventanas, cada una desde su ángulo y en el "
            "plano de cada línea. En 0.11.0 se proyectaba siempre en planta y salía mal.",
            "Pan, zoom y órbita se ven en tiempo real en la ventana bajo el cursor.",
            "Las tres ventanas ortogonales están clavadas en su vista: ORBITAR, ISO y las demás "
            "giran siempre la Perspectiva, esté activa o no.",
            "La perspectiva ya no se estira al alejar: su fuerza va en píxeles, no en "
            "milímetros, y es la misma a cualquier zoom.",
            "La rueda 3D sale con Shift + clic derecho sostenido (antes era Alt).",
        ],
    },
    {
        "version": "0.11.0",
        "fecha": "2026-09-18",
        "cambios": [
            "Cada ventana dibuja sobre su plano: la Superior sobre el suelo, la Frontal sobre "
            "XZ y la Lateral sobre YZ. Cada línea recuerda en qué plano vive y se ve en las "
            "cuatro ventanas desde su ángulo, con su selección y su hule.",
            "Extruir empuja en la dirección del plano: un contorno de la Frontal se levanta "
            "hacia quien mira; uno de la Lateral, hacia el lado. STEP y STL salen ya rotados.",
            "La ventana activa se elige con clic y se queda para los comandos. Pan, zoom y "
            "órbita van a la ventana bajo el cursor sin cambiarla: es lo que quita el brinco "
            "de la Perspectiva y el hule mal pintado de la 0.10.0.",
            "Orbitar sólo existe en la Perspectiva, con el botón central. Shift + central hace "
            "pan ahí. En las ortogonales el central es pan.",
        ],
    },
    {
        "version": "0.10.0",
        "fecha": "2026-09-18",
        "cambios": [
            "La selección, el hule y los fantasmas se ven en las cuatro ventanas, cada una "
            "desde su ángulo. En 0.9.0 sólo se pintaban con la cámara de la activa y salían "
            "desfasados en las demás.",
            "La ventana Perspectiva tiene perspectiva de verdad; las otras tres siguen "
            "ortogonales, que es donde se mide.",
            "Orbitar gira alrededor de lo que está bajo el cursor al empezar a arrastrar. En la "
            "Perspectiva, el botón central orbita y Alt + central hace pan; en las otras tres el "
            "central es pan y Alt + central orbita.",
            "La ventana se activa con solo pasar el mouse: zoom, pan y órbita van donde está el "
            "cursor.",
            "Extruir es interactivo: das EXTRUIR con el contorno seleccionado, arrastras y el "
            "fantasma crece con la cota; clic confirma, Enter teclea el valor, Escape cancela.",
        ],
    },
    {
        "version": "0.9.0",
        "fecha": "2026-09-18",
        "cambios": [
            "Cuatro ventanas, como Rhino: superior, perspectiva, frontal y lateral, cada una "
            "con su cámara. Clic en una la activa; doble clic en su título la maximiza y otro "
            "doble clic la devuelve. Todo —dibujar, zoom, pan, orbitar— trabaja sobre la "
            "ventana activa, que se ve con el borde marcado.",
            "Al abrir, la ventana superior conserva lo que estabas mirando y las otras tres se "
            "encuadran solas a lo que hay.",
            "Todavía se dibuja sobre el suelo (XY) en las cuatro: en la frontal y la lateral "
            "el plano se ve de canto. Dibujar sobre el plano de cada ventana es el paso "
            "siguiente. La perspectiva de la cuarta ventana es aún isométrica.",
        ],
    },
    {
        "version": "0.8.2",
        "fecha": "2026-09-18",
        "cambios": [
            "Los dibujos nuevos arrancan en milímetros con centésimas, como se decidió el "
            "primer día. Hasta ahora arrancaban en centímetros, heredados de draw101.",
            "Si un dibujo está en centímetros o metros, el motor lo sabe: el volumen sale "
            "bien y el STEP y el STL a tamaño real. Antes una pieza dibujada en cm se "
            "exportaba diez veces más chica, y ese error se ve ya cortado.",
        ],
    },
    {
        "version": "0.8.1",
        "fecha": "2026-09-18",
        "cambios": [
            "El motor de sólidos se carga al abrir el programa, en segundo plano, en vez de "
            "la primera vez que extruyes. En 0.8.0 esa primera extrusión tardaba medio "
            "minuto: eran 350 MB de bibliotecas leyéndose por primera vez.",
            "Al extruir, la consola dice cuánto tardó el motor. Si algo vuelve a tardar, "
            "sabremos dónde.",
        ],
    },
    {
        "version": "0.8.0",
        "fecha": "2026-09-18",
        "cambios": [
            "Ya no hay un plano 2D aparte: el dibujo vive sobre el suelo del 3D y el visor "
            "nuevo pinta siempre, también en planta. Dos pintores para el mismo espacio era lo "
            "que hacía lento girar. Las hojas de impresión siguen como estaban.",
            "Orbitar es Alt + botón central del ratón, arrastrando. ORBITAR sigue existiendo "
            "para quien no tenga botón central.",
            "La rejilla se ve también girada, en perspectiva, con los ejes marcados para "
            "saber dónde está el cero. Los textos vuelven a verse girados, de frente a quien "
            "mira.",
        ],
    },
    {
        "version": "0.7.0",
        "fecha": "2026-09-18",
        "cambios": [
            "Con la vista girada pinta un visor nuevo, pensado en 3D: las líneas del dibujo y "
            "las piezas en un mismo espacio, sin los atajos de planta que hacían que las "
            "líneas se quedaran en 2D y que girar fuera lento. En planta todo sigue igual.",
            "Orbitar ya no se pelea con el pan: mientras giras, el ratón es de la cámara.",
            "El zoom con la rueda girado ya no se descentra: lo que está bajo el cursor se "
            "queda bajo el cursor, desde cualquier ángulo.",
            "Después de jalar una cara, la pieza se redibuja de inmediato.",
            "Girado se ve el plano de trabajo, apenas insinuado, para saber dónde está el "
            "suelo. Textos y cotas todavía no se pintan girados; en planta sí.",
        ],
    },
    {
        "version": "0.6.1",
        "fecha": "2026-09-17",
        "cambios": [
            "La pieza ya nace pegada al dibujo. En 0.6.0 las líneas del plano se seguían "
            "pintando desde arriba aunque la cámara girara, así que la pieza giraba sola y "
            "se veía despegada.",
            "Orbitar se ve en tiempo real y ya no brinca: la cámara pedía repintar por un "
            "nombre que no existía, y el cuadro llegaba tarde.",
            "Un error al pintar ya no deja el programa muerto: se anota, se pinta lo que se "
            "pudo y sigue vivo. Es lo que pasó en 0.6.0 al hacer zoom con la vista girada.",
            "Con la vista girada no se pinta la rejilla, que ahí no significa nada.",
        ],
    },
    {
        "version": "0.6.0",
        "fecha": "2026-09-16",
        "cambios": [
            "Un solo espacio. El 3D ya no es un visor pegado encima del dibujo: las piezas "
            "se pintan en el mismo lienzo que las líneas, con la misma cámara, y la pieza se "
            "para sobre el contorno del que salió. La vista de planta es un ángulo de cámara, "
            "no un modo: se dibuja igual que siempre.",
            "ORBITAR gira la vista arrastrando, alrededor de lo que estás mirando. PLANTA, "
            "FRENTE, DERECHA e ISO son las vistas fijas. El comando 3D alterna planta e "
            "isométrica. Todo en la barra y en la rueda 3D (Alt + clic derecho sostenido).",
            "Al jalar una cara ahora ves en tiempo real a dónde va: la cara punteada en su "
            "sitio nuevo, las líneas que la unen al viejo y la medida en milímetros siguiendo "
            "al cursor. Al soltar, la pieza se rehace. Si la cara se ve exactamente de canto, "
            "el programa lo dice en vez de inventar un número.",
            "El sugeridor de comandos es cinco veces más chico: cinco filas, letra chica, "
            "pegado a la caja.",
        ],
    },
    {
        "version": "0.5.0",
        "fecha": "2026-09-16",
        "cambios": [
            "Sugeridor de comandos: al teclear sale la lista de los que empiezan así, con sus "
            "atajos y para qué sirven. Las flechas eligen y Enter corre. Con la caja vacía las "
            "flechas siguen siendo el historial, como siempre.",
            "El 3D ya no está escondido en la consola: tiene su bloque en la barra de "
            "herramientas —Extruir, Ver 3D, Jalar, STEP, STL— y su propia rueda con "
            "**Alt + clic derecho sostenido**. La rueda de siempre no cambió ni un ángulo.",
            "JALAR mueve la cara señalada una medida exacta. Arrastrar da la sensación; "
            "teclear da el milímetro, y en un taller hacen falta los dos.",
            "STEP y STL sacan la pieza desde la barra o la rueda, sin teclear.",
        ],
    },
    {
        "version": "0.4.1",
        "fecha": "2026-09-16",
        "cambios": [
            "EXTRUIR ya pregunta el espesor como el resto del programa, con la cajita de "
            "siempre: acepta coma o punto y recuerda lo último que tecleaste. En 0.4.0 el "
            "comando se quedaba muerto sin preguntar nada.",
        ],
    },
    {
        "version": "0.4.0",
        "fecha": "2026-09-15",
        "cambios": [
            "Empieza el 3D. Dibuja un contorno cerrado como siempre, selecciónalo y teclea "
            "EXTRUIR: se levanta y se vuelve una pieza sólida de verdad, con su espesor.",
            "La vista pasa a 3D sola. Arrastrando en el vacío se gira la pieza y la rueda "
            "acerca. Un clic señala una cara —se pone amarilla— y arrastrarla la jala: la "
            "pieza se rehace, no se estira. La medida se toma sobre la dirección a la que la "
            "cara apunta, así que jalar se siente igual mires desde donde mires.",
            "Los vértices del contorno salen como puntos azules. Al mover uno, la pieza "
            "entera se reconstruye y conserva lo que hayas hecho después: un barreno sigue "
            "siendo redondo y una cara jalada sigue jalada.",
            "La pieza se guarda dentro del .101s como cómo se hizo, no como una malla, y sale "
            "en STEP para abrirla en otro CAD o en STL para imprimirla.",
            "Escape vuelve al dibujo; el comando 3D regresa. Esta es la primera versión del "
            "gesto: todavía no hay ejes de arrastre, ni ajuste a rejilla, ni deshacer dentro "
            "del 3D.",
            "El instalador pesa bastante más: el motor de sólidos (OpenCascade) son unos "
            "200 MB. Es el precio de que las piezas sean exactas y se puedan exportar.",
            "Seguridad del botón «Instalar ODA»: el instalador del convertidor sólo se "
            "baja de opendesign.com por https; una liga ajena del puntero se ignora, y si "
            "el puntero declara la huella sha256 se comprueba antes de correr msiexec. "
            "Prueba t023 (28 comprobaciones).",
        ],
    },
    {
        "version": "0.3.0",
        "fecha": "2026-09-14",
        "cambios": [
            "shape101 vuelve a nacer, ahora desde la fuente de draw101 0.20.4. Trae todo lo "
            "que draw101 sabe hacer en 2D; el modelado 3D empieza en la siguiente entrega.",
            "Sus archivos son .101s y sus preferencias, bloques y autoguardado viven en su "
            "propia carpeta: draw101 y shape101 son dos programas distintos que comparten un "
            "abuelo. Ninguno le pisa el trabajo al otro.",
            "La numeración arranca en 0.3.0 porque las versiones 0.1.0 y 0.2.0 de shape101 ya se "
            "publicaron con otro contenido, y un número repetido con contenido distinto es "
            "justo lo que no se debe hacer.",
        ],
    },
]


def bitacora(desde: str | None = None) -> list[dict]:
    """La bitácora, opcionalmente recortada a partir de una versión."""
    if desde is None:
        return BITACORA
    salida = []
    for e in BITACORA:
        salida.append(e)
        if e["version"] == desde:
            break
    return salida


def como_tupla(v: str = VERSION) -> tuple[int, int, int]:
    """`"0.10.0"` → `(0, 10, 0)`. Para comparar sin sorpresas alfabéticas:
    ordenado como texto, 0.9.0 sale *después* de 0.10.0."""
    partes = (v.split("-")[0].split(".") + ["0", "0", "0"])[:3]
    return tuple(int(p) if p.isdigit() else 0 for p in partes)  # type: ignore[return-value]
