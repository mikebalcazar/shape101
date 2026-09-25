/* Vista y lienzo  ·  features 11 y 12 (la parte de la rejilla que se ve).
 *
 * Aquí vive la transformación mm ↔ píxel, el pintado del dibujo, la rejilla
 * adaptativa y toda la navegación: rueda, encuadre, zoom por ventana, zoom
 * previo y pan.
 *
 * El zoom previo guarda una pila de vistas. Es de las cosas que en AutoCAD uno
 * usa sin pensar y que se extraña de inmediato cuando no está: acercarse a un
 * detalle y volver de un golpe a donde estabas.
 */

const lienzo = $("#lienzo");
const ctx = lienzo.getContext("2d");
/* El de encima: mira, selección y goma. Ver el bloque «El pintado». */
const encima = $("#encima");
const ctxE = encima.getContext("2d");

const historialVista = [];
const MAX_VISTAS = 40;

function ajustarLienzo() {
  // Se mide la **caja**, no el lienzo: el lienzo va absoluto dentro de ella
  // (ver styles.css) y por eso la caja nunca crece por culpa del lienzo.
  const caja = lienzo.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(caja.width * dpr));
  const h = Math.max(1, Math.round(caja.height * dpr));
  for (const [cv, c] of [[lienzo, ctx], [encima, ctxE]]) {
    // Sólo si cambió: asignar `width` borra el lienzo aunque sea el mismo
    // número, y eso es un parpadeo por cada aviso de tamaño.
    if (cv.width !== w) cv.width = w;
    if (cv.height !== h) cv.height = h;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  invalidarPlano();
  pintar();
}

/* La caja del lienzo avisa cuando cambia de tamaño, sea por la ventana, por
 * el panel que se ensancha, por la barra que se ancla arriba o por cambiar de
 * monitor. El `resize` de la ventana sólo cubre el primero de esos casos. */
if (typeof ResizeObserver !== "undefined") {
  new ResizeObserver(() => ajustarLienzo()).observe(lienzo.parentElement);
}

// La Y se voltea: en CAD crece hacia arriba, en el lienzo hacia abajo.
// Con la cámara en cero —la vista superior— se hace **la misma cuenta de
// siempre**, línea por línea. Eso no es una optimización: es lo que garantiza
// que el 2D que ya funciona no cambie ni en el último decimal. Si cambiara, el
// osnap dejaría de pegar donde debe y nadie sabría por qué.
const aPX = (x, y, z) => {
  const v = estado.vista;
  if (!v.rx && !v.rz) return [(x - v.x) * v.escala + (v.ox || 0), (v.y - y) * v.escala + (v.oy || 0)];
  const cz = Math.cos(v.rz), sz = Math.sin(v.rz);
  const ux = x * cz - y * sz;
  const uy = x * sz + y * cz;
  const cx = Math.cos(v.rx), sx = Math.sin(v.rx);
  const vy = uy * cx - (z || 0) * sx;
  let px = (ux - v.x) * v.escala + (v.ox || 0), py = (v.y - vy) * v.escala + (v.oy || 0);
  if (v.persp) {
    // Perspectiva: lo cercano al ojo se aleja del centro de la ventana y lo
    // lejano se acerca. Sólo la ventana Perspectiva la lleva; las otras tres
    // son ortogonales, que es donde se mide.
    const prof = uy * sx + (z || 0) * cx;
    const cxs = (v.ox || 0) + v.w / 2, cys = (v.oy || 0) + v.h / 2;
    // El foco va en píxeles: así la perspectiva es igual de conservadora a
    // cualquier zoom. En milímetros se estiraba al alejarse.
    const k = 1 / Math.max(0.1, 1 - prof * v.escala / (v.foco || 1400));
    px = cxs + (px - cxs) * k;
    py = cys + (py - cys) * k;
  }
  return [px, py];
};
// Al revés se cae **sobre el plano de trabajo** (z = 0): es donde vive el
// dibujo, así que el punto que sueltas es el que estabas viendo.
const aMM = (px, py) => {
  const v = estado.vista;
  if (!v.rx && !v.rz) return [(px - (v.ox || 0)) / v.escala + v.x, v.y - (py - (v.oy || 0)) / v.escala];
  let ux = (px - (v.ox || 0)) / v.escala + v.x;
  let vy = v.y - (py - (v.oy || 0)) / v.escala;
  const cx = Math.cos(v.rx);
  if (v.persp && Math.abs(cx) > 1e-9) {
    // Deshacer la perspectiva sobre el suelo (z = 0): ahí la profundidad es
    // lineal en la Y de la cámara, y la ecuación se resuelve exacta.
    const cxs = (v.ox || 0) + v.w / 2, cys = (v.oy || 0) + v.h / 2;
    const t = (Math.sin(v.rx) / cx) * v.escala / (v.foco || 1400);
    const A = v.y * v.escala + (v.oy || 0) - cys, d = py - cys;
    vy = (A - d) / (v.escala - d * t);
    const k = 1 / Math.max(0.1, 1 - t * vy);
    ux = v.x + ((px - cxs) / k + cxs - (v.ox || 0)) / v.escala;
  }
  // En la Frontal y la Lateral lo que se devuelve son las coordenadas del
  // plano de la ventana —(x, z) o (y, z)—, que es donde se dibuja ahí.
  if (v.plano === "XZ" || v.plano === "YZ") return [ux, vy];
  const uy = Math.abs(cx) < 1e-9 ? 0 : vy / cx;
  const cz = Math.cos(v.rz), sz = Math.sin(v.rz);
  return [ux * cz + uy * sz, -ux * sz + uy * cz];
};

function recordarVista() {
  historialVista.push({ ...estado.vista });
  if (historialVista.length > MAX_VISTAS) historialVista.shift();
}

function vistaPrevia() {
  const v = historialVista.pop();
  if (!v) return avisar("No hay vista anterior.", false, 2000);
  ponerVista(v);
  pintar();
}

/** El tamaño útil de la ventana activa: su ancho y su alto sin la franja del
 *  título. Con una sola vista es el lienzo entero. */
function tamanoActivo() {
  const v = estado.vista;
  const titulo = v.w && typeof Ventanas !== "undefined" ? Ventanas.TITULO : 0;
  return { ancho: v.w || lienzo.clientWidth || 800, alto: (v.h || lienzo.clientHeight || 600) - titulo, titulo };
}

/** Cambiar la cámara **dentro** del objeto, nunca encima: la ventana activa ES
 *  ese objeto, y reemplazarlo la desconecta de su cámara. */
function ponerVista(v) {
  Object.assign(estado.vista, { x: v.x, y: v.y, escala: v.escala, rx: v.rx || 0, rz: v.rz || 0 });
}

function encuadrar(recordar = true) {
  const caja = estado.resumen && estado.resumen.extension;
  const { ancho, alto, titulo } = tamanoActivo();
  if (recordar) recordarVista();
  // Con las cuatro ventanas, Extents encuadra **las cuatro**: es lo que la
  // palabra significa cuando hay cuatro cámaras mirando la misma pieza, y es
  // la única manera de recuperar una ventana que se quedó viendo al vacío.
  // Cada una desde su ángulo: la caja en planta no dice dónde caen las cosas
  // vistas de frente.
  if (typeof Ventanas !== "undefined" && estado.vista && estado.vista.w) {
    const puntos = puntosDelDibujo();
    if (puntos.length) { Ventanas.encuadrarTodas(puntos); return pintar(); }
    Ventanas.centrarEnOrigen();
    return pintar();
  }
  if (!caja) {
    ponerVista({ x: -ancho / 4, y: alto / 4 + titulo, escala: 1 });
    return pintar();
  }
  const [x0, y0, x1, y1] = caja;
  const escala = Math.min(
    (ancho * 0.92) / Math.max(x1 - x0, 1e-6),
    (alto * 0.92) / Math.max(y1 - y0, 1e-6)
  );
  estado.vista.escala = Math.min(escala, 200);
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + (alto / 2 + titulo) / estado.vista.escala;
  pintar();
}

function encuadrarCaja(x0, y0, x1, y1) {
  if (Math.abs(x1 - x0) < 1e-9 || Math.abs(y1 - y0) < 1e-9) return;
  recordarVista();
  const { ancho, alto, titulo } = tamanoActivo();
  estado.vista.escala = Math.min(500, Math.min(
    ancho / Math.abs(x1 - x0), alto / Math.abs(y1 - y0)));
  estado.vista.x = (x0 + x1) / 2 - ancho / 2 / estado.vista.escala;
  estado.vista.y = (y0 + y1) / 2 + (alto / 2 + titulo) / estado.vista.escala;
  pintar();
}

function zoomEn(px, py, factor) {
  // En el espacio de la cámara, no en el del plano: vista.x y vista.y viven
  // ahí. En planta son lo mismo; girado, mezclar los dos descentra el zoom
  // media pantalla en cada tic de la rueda.
  const v = estado.vista;
  const ox = v.ox || 0, oy = v.oy || 0;                // la ventana empieza donde empieza
  const ux = (px - ox) / v.escala + v.x, vy = v.y - (py - oy) / v.escala;
  v.escala = Math.min(500, Math.max(0.002, v.escala * factor));
  v.x = ux - (px - ox) / v.escala;                     // el punto bajo el cursor
  v.y = vy + (py - oy) / v.escala;                     // se queda quieto
  Regen.gesto();
  pintar();
}

/* --- Rejilla  ·  feature 12 -------------------------------------------- */
function pasoRejilla() {
  // Se parte del paso que pidió el usuario y se multiplica o divide por 2 y 5
  // hasta que la celda quede entre 8 y 80 píxeles. Sin esto, alejarse en un
  // plano de obra pinta cien mil líneas y la app se arrodilla.
  // El paso de las preferencias está en mm; en un dibujo en metros son 0.01.
  let paso = ((estado.prefs && estado.prefs.rejilla_paso) || 10) / mmPorUnidad();
  let guarda = 0;
  while (paso * estado.vista.escala < 8 && guarda++ < 40) paso *= (String(paso)[0] === "2" ? 2.5 : 2);
  guarda = 0;
  while (paso * estado.vista.escala > 80 && guarda++ < 40) paso /= (String(paso)[0] === "2" ? 2 : 2.5);
  return paso;
}

function pintarRejilla(c = ctx) {
  if (!estado.prefs || !estado.prefs.rejilla) return;
  const anchoPX = lienzo.clientWidth, altoPX = lienzo.clientHeight;
  const paso = pasoRejilla();
  // Los colores salen del tema en caché: leerlos del CSS en cada cuadro es
  // obligar al navegador a recalcular estilos sesenta veces por segundo para
  // enterarse de tres valores que no cambian.
  const T = tema();
  const [mx0, my1] = aMM(0, 0);
  const [mx1, my0] = aMM(anchoPX, altoPX);

  c.lineWidth = 1;
  for (const [mult, color] of [[1, T.rejilla], [10, T.rejilla2]]) {
    const p = paso * mult;
    if (p * estado.vista.escala < 6) continue;
    c.strokeStyle = color;
    c.beginPath();
    for (let x = Math.ceil(mx0 / p) * p; x <= mx1; x += p) {
      const [px] = aPX(x, 0);
      c.moveTo(Math.round(px) + 0.5, 0); c.lineTo(Math.round(px) + 0.5, altoPX);
    }
    for (let y = Math.ceil(my0 / p) * p; y <= my1; y += p) {
      const [, py] = aPX(0, y);
      c.moveTo(0, Math.round(py) + 0.5); c.lineTo(anchoPX, Math.round(py) + 0.5);
    }
    c.stroke();
  }

  c.strokeStyle = T.linea3;
  c.beginPath();
  const [ox, oy] = aPX(0, 0);
  c.moveTo(0, Math.round(oy) + 0.5); c.lineTo(anchoPX, Math.round(oy) + 0.5);
  c.moveTo(Math.round(ox) + 0.5, 0); c.lineTo(Math.round(ox) + 0.5, altoPX);
  c.stroke();
}

/* Un plano ajeno viene lleno de entidades blancas (en AutoCAD el fondo es
 * negro) o negras (si venía de papel). Pintarlas tal cual las hace invisibles
 * en la mitad de los temas. AutoCAD hace justo esto: el blanco y el negro se
 * voltean según el fondo; los demás colores no se tocan. */
function colorVisible(hex, oscuro) {
  if (!hex || hex.length !== 7) return hex;
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  const gris = Math.max(r, g, b) - Math.min(r, g, b) < 24;
  if (!gris) return hex;
  if (!oscuro && Math.min(r, g, b) > 225) return "#1a1f27";
  if (oscuro && Math.max(r, g, b) < 40) return "#e6e8ec";
  return hex;
}

/* ===================================================================== */
/* El pintado                                                            */
/* ===================================================================== */
/* Reescrito por lo que reportó Mike: *«sigue siendo muy lento cuando un
 * archivo grande se abre; AutoCAD y Rhino responden bien igual»*.
 *
 * La versión anterior hacía, **por cada trazo y en cada cuadro**: descifrar su
 * color de un texto hexadecimal, asignar `strokeStyle` (que obliga al navegador
 * a interpretar ese texto otra vez), construir el arreglo del punteado,
 * `beginPath()`, un arreglo nuevo por cada vértice, y `stroke()`. Con 120 000
 * trazos eso son 120 000 `stroke()` por cuadro: **86 ms**, o sea 12 cuadros por
 * segundo en una máquina rápida y bastante menos en una de taller. Y como el
 * movimiento del ratón pintaba directo, los cuadros se encolaban: eso es lo que
 * se siente como que el programa «se traba».
 *
 * Lo que se hace ahora es lo que hace cualquier motor de CAD:
 *
 *  1. **Un cuadro por cuadro.** `pintar()` no pinta: apunta que hay que
 *     pintar y lo hace en el siguiente `requestAnimationFrame`. Diez avisos
 *     seguidos cuestan uno.
 *  2. **Se descarta lo que no se ve.** Cada trazo guarda su caja; si cae fuera
 *     de la pantalla no se toca. Acercarse a un detalle deja de costar lo que
 *     mide el plano entero — que es justo lo que uno hace todo el día.
 *  3. **Lo que no se distingue se pinta como punto.** Una entidad que a este
 *     zoom mide menos de un píxel no se puede dibujar mejor que como una
 *     mancha, y recorrer sus cien vértices para eso es tirar el trabajo: se
 *     resuelve con dos órdenes en vez de cien. Lo que **no** se hace es
 *     saltársela, que fue el primer intento y estaba mal — en un plano de obra
 *     visto entero, esa nube de cosas diminutas **es** el plano; quitarla deja
 *     la pantalla medio vacía y el usuario cree que se perdió el dibujo. Y
 *     dentro de una polilínea, los vértices que caen en el mismo píxel se
 *     saltan, que eso sí no se nota.
 *  4. **Se pinta por lotes.** En vez de un `stroke()` por trazo, se juntan los
 *     que comparten color, grosor y punteado y se hace **uno por grupo**. De
 *     120 000 llamadas se pasa a unas pocas docenas.
 *  5. **El dibujo se guarda pintado.** Mientras la vista no se mueva, el plano
 *     no se vuelve a dibujar: se copia la imagen ya hecha y encima van la mira,
 *     la selección y la goma, que es lo único que cambia al mover el ratón.
 *     Ésta es la que quita el tirón de verdad — antes, pasear el cursor por
 *     encima de un plano grande lo redibujaba **entero, sesenta veces por
 *     segundo**, para mover una cruz de dos rayas.
 *
 * Lo que cuesta el punto 4: dentro de un cuadro, el orden de dibujo pasa a ser
 * por estilo y no por orden de creación. En un dibujo de líneas —que es lo que
 * es un plano— no se nota, porque nada tapa a nada. Si algún día hay rellenos
 * opacos habrá que agruparlos aparte respetando su orden.
 */

/* Los colores del tema se leían con `getComputedStyle` en cada cuadro. Se leen
 * una vez y se vuelven a leer sólo si cambia el tema. */
let _tema = null;
function tema() {
  const cual = document.documentElement.dataset.tema || "claro";
  if (_tema && _tema.cual === cual) return _tema;
  const css = getComputedStyle(document.documentElement);
  const v = (n) => css.getPropertyValue(n).trim();
  _tema = { cual, oscuro: cual === "oscuro", lienzo: v("--lienzo"),
            rejilla: v("--rejilla"), rejilla2: v("--rejilla2"), linea3: v("--linea3"),
            acc2: v("--acc2"), panel: v("--panel"), canto: v("--canto"),
            // Lo que pintan las capas de encima en cada cuadro. Leerlas con
            // getComputedStyle en cada cuadro obliga al navegador a recalcular
            // el estilo de toda la ventana justo después de que se movió la
            // cajita dinámica y cambió el texto de coordenadas: un reflow por
            // movimiento del ratón. Se leen una vez por tema.
            txt3: v("--txt3"), txt: v("--txt") || "#1A1F27", ok: v("--ok"), warn: v("--warn"), texto3: v("--texto3") || "#9aa3ad" };
  return _tema;
}

/* `colorVisible` descifra un hexadecimal a mano. Hacerlo por trazo y por cuadro
 * es medio millón de veces por segundo para un puñado de colores distintos. */
const _colores = new Map();
function colorDeTrazo(hex, oscuro) {
  const llave = oscuro ? "o" + hex : "c" + hex;
  let c = _colores.get(llave);
  if (c === undefined) {
    c = colorVisible(hex, oscuro);
    _colores.set(llave, c);
  }
  return c;
}

/* --- Bloques pesados: una definición, muchas inserciones ------------------
 *
 * El A8-501 de Mike (6-sep): cientos de palmeras de 50 000 vértices. Explotar
 * cada una a sus trazos daba 559 MB de JSON y el navegador ni lo leía. Ahora
 * el motor manda, por cada inserción de un bloque pesado, **un trazo** con su
 * punto, escala, giro y caja (`clase: "insercion"`, ver core/dibujo.py), y la
 * definición del bloque se pide aparte, **una vez**, cuando hace falta pintarla.
 *
 * Cada definición se guarda como `Path2D` por lote de color (uno por color),
 * en coordenadas del bloque, y se pinta con la matriz de la inserción: el
 * navegador transforma, no JavaScript. Y con tres niveles de detalle: una
 * palmera de 20 píxeles no necesita sus 50 000 vértices — se pinta con la
 * versión adelgazada, que es lo que hace cualquier CAD con lista de
 * despliegue. Mientras la definición no ha llegado, se pinta su caja punteada.
 */
const Bloques = (() => {
  const defs = new Map();          // nombre → {trazos, caja, lotes:[{color, grosor, paths:[Path2D×3]}], textos}
  const pidiendo = new Map();      // nombre → Promise
  const cola = [];                 // nombres por pedir, en orden
  let enVuelo = 0;
  const A_LA_VEZ = 3;
  const NIVELES = [0, 1 / 300, 1 / 60];   // tolerancia de adelgazado, como fracción de la diagonal

  function adelgazar(pts, tol) {
    if (pts.length < 3 || tol <= 0) return pts;
    const out = [pts[0]];
    let ux = pts[0][0], uy = pts[0][1];
    const t2 = tol * tol;
    for (let i = 1; i < pts.length - 1; i++) {
      const dx = pts[i][0] - ux, dy = pts[i][1] - uy;
      if (dx * dx + dy * dy >= t2) { out.push(pts[i]); ux = pts[i][0]; uy = pts[i][1]; }
    }
    out.push(pts[pts.length - 1]);
    return out;
  }

  function armar(def) {
    const c = def.caja;
    const diag = Math.hypot(c[2] - c[0], c[3] - c[1]) || 1;
    const lotes = new Map();
    def.textos = [];
    for (const t of def.trazos) {
      if (t.clase === "texto") { def.textos.push(t); continue; }
      if (!t.puntos || t.puntos.length < 2) continue;
      const llave = (t.color || "") + "|" + (t.grosor || 0);
      let lote = lotes.get(llave);
      if (!lote) {
        lote = { color: t.color || null, grosor: t.grosor || 0, paths: NIVELES.map(() => new Path2D()), n: NIVELES.map(() => 0) };
        lotes.set(llave, lote);
      }
      NIVELES.forEach((f, k) => {
        const tol = diag * f;
        if (k > 0) {
          // Un trazo entero más chico que la tolerancia no aporta nada a este
          // nivel: fuera. Es lo que de verdad adelgaza una palmera de 8 000
          // trazos de tres vértices.
          let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
          for (const q of t.puntos) { if (q[0] < x0) x0 = q[0]; if (q[0] > x1) x1 = q[0]; if (q[1] < y0) y0 = q[1]; if (q[1] > y1) y1 = q[1]; }
          if (x1 - x0 < tol && y1 - y0 < tol) return;
        }
        const pts = adelgazar(t.puntos, tol);
        const P = lote.paths[k];
        P.moveTo(pts[0][0], pts[0][1]);
        for (let i = 1; i < pts.length; i++) P.lineTo(pts[i][0], pts[i][1]);
        lote.n[k] += pts.length;
      });
    }
    def.lotes = [...lotes.values()];
    def.trazos = null;               // ya está en los Path2D: no hace falta dos veces
    return def;
  }

  function siguiente() {
    while (enVuelo < A_LA_VEZ && cola.length) {
      const nombre = cola.shift();
      enVuelo++;
      const prom = api("/api/bloques/definicion?nombre=" + encodeURIComponent(nombre))
        .then((d) => { defs.set(nombre, armar(d)); })
        .catch(() => { defs.set(nombre, { lotes: [], textos: [], caja: [0, 0, 0, 0], fallo: true }); })
        .finally(() => { enVuelo--; pidiendo.delete(nombre); invalidarPlano(); window.pintar ? window.pintar() : pintar(); siguiente(); });
      pidiendo.set(nombre, prom);
    }
  }

  /** La definición, o null si todavía no llegó (y se pide). */
  function definicion(nombre) {
    const d = defs.get(nombre);
    if (d) return d;
    if (!pidiendo.has(nombre) && !cola.includes(nombre)) { cola.push(nombre); siguiente(); }
    return null;
  }

  /** Nivel de detalle según el tamaño en pantalla de la inserción. */
  function nivel(tamPX) { return tamPX > 500 ? 0 : tamPX > 80 ? 1 : 2; }

  /** Pintar una inserción pesada en el contexto dado (ya en píxeles CSS). */
  function pintarInstancia(c, t, esc, vx, vy, colorInsercion, borrador) {
    const def = definicion(t.bloque);
    const bb = t.caja;
    const tamPX = Math.max(bb[2] - bb[0], bb[3] - bb[1]) * esc;
    if (!def) {
      // Todavía no llegó: la caja punteada, para que se vea que ahí va algo.
      c.save();
      c.setLineDash([4, 3]);
      c.lineWidth = 1;
      c.strokeStyle = colorInsercion;
      c.globalAlpha = 0.6;
      c.strokeRect((bb[0] - vx) * esc, (vy - bb[3]) * esc, (bb[2] - bb[0]) * esc, (bb[3] - bb[1]) * esc);
      c.restore();
      return;
    }
    if (!def.lotes.length) return;
    if (tamPX <= SPRITE_HASTA_PX && !borrador) {
      // Chica en pantalla: se pinta una vez a una imagen del tamaño justo y de
      // ahí se copia. La imagen se conserva mientras el zoom quede en el mismo
      // escalón; al panear no se rehace nada.
      pintarSprite(c, t, def, esc, vx, vy, colorInsercion);
      return;
    }
    const k = nivel(tamPX);
    const r = (t.rotacion || 0) * Math.PI / 180;
    const cos = Math.cos(r), sen = Math.sin(r);
    const sx = t.escala[0], sy = t.escala[1];
    c.save();
    // local (lx, ly) → pantalla: X = (p.x - vx)·esc + esc·(lx·sx·cos − ly·sy·sen)
    //                              Y = (vy − p.y)·esc − esc·(lx·sx·sen + ly·sy·cos)
    c.transform(esc * sx * cos, -esc * sx * sen, -esc * sy * sen, -esc * sy * cos,
                (t.p[0] - vx) * esc, (vy - t.p[1]) * esc);
    const escMedia = esc * (Math.abs(sx) + Math.abs(sy)) / 2 || 1;
    c.setLineDash([]);
    for (const lote of def.lotes) {
      c.strokeStyle = lote.color ? colorDeTrazo(lote.color, tema().oscuro && estado.modo !== "papel") : colorInsercion;
      // El grosor va en mm de papel, como el resto: se deshace la escala.
      c.lineWidth = (borrador ? 1 : Math.max(1, lote.grosor * 3.78 * 0.35)) / escMedia;
      c.stroke(lote.paths[k]);
    }
    c.restore();
    // Los textos del bloque, si se leen.
    if (def.textos.length && !borrador) {
      const f = (Math.abs(sx) + Math.abs(sy)) / 2;
      for (const tx of def.textos) {
        const alturaPX = (tx.altura || 2.5) * f * esc;
        if (alturaPX < 4) continue;
        const lx = tx.p[0] * sx, ly = tx.p[1] * sy;
        const wx = t.p[0] + lx * cos - ly * sen, wy = t.p[1] + lx * sen + ly * cos;
        c.save();
        c.fillStyle = tx.color ? colorDeTrazo(tx.color, tema().oscuro) : colorInsercion;
        c.translate((wx - vx) * esc, (vy - wy) * esc);
        const rot = (tx.rotacion || 0) + (t.rotacion || 0);
        if (rot) c.rotate(-rot * Math.PI / 180);
        c.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
        c.textAlign = tx.alineacion === "CENTRO" ? "center" : tx.alineacion === "DER" ? "right" : "left";
        c.fillText(String(tx.texto), 0, 0);
        c.restore();
      }
    }
  }

  const SPRITE_HASTA_PX = 160;

  /* La imagen de una definición a un tamaño dado. Se guarda por escalón de
   * escala (×1.25 entre escalones), giro y espejo, dentro de la definición. */
  function pintarSprite(c, t, def, esc, vx, vy, colorInsercion) {
    const sx = t.escala[0], sy = t.escala[1];
    const escalon = Math.round(Math.log(esc * (Math.abs(sx) + Math.abs(sy)) / 2) / Math.log(1.25));
    const escEfect = Math.pow(1.25, escalon);              // px por mm-local, redondeado al escalón
    const rot = Math.round((t.rotacion || 0) / 5) * 5;      // giros de 5 en 5 grados
    const llave = escalon + "|" + rot + "|" + (sx < 0 ? "x" : "") + (sy < 0 ? "y" : "") + "|" + colorInsercion;
    if (!def.sprites) def.sprites = new Map();
    let sp = def.sprites.get(llave);
    if (!sp) {
      // Caja del bloque girado, en píxeles del sprite.
      const bb = def.caja;
      const r = rot * Math.PI / 180, cos = Math.cos(r), sen = Math.sin(r);
      const esq = [[bb[0], bb[1]], [bb[2], bb[1]], [bb[2], bb[3]], [bb[0], bb[3]]].map(([x, y]) => {
        const lx = x * Math.sign(sx || 1), ly = y * Math.sign(sy || 1);
        return [(lx * cos - ly * sen) * escEfect, -(lx * sen + ly * cos) * escEfect];
      });
      const x0 = Math.min(...esq.map((q) => q[0])) - 2, x1 = Math.max(...esq.map((q) => q[0])) + 2;
      const y0 = Math.min(...esq.map((q) => q[1])) - 2, y1 = Math.max(...esq.map((q) => q[1])) + 2;
      const dpr = window.devicePixelRatio || 1;
      const cv = document.createElement("canvas");
      cv.width = Math.max(1, Math.ceil((x1 - x0) * dpr));
      cv.height = Math.max(1, Math.ceil((y1 - y0) * dpr));
      const cc = cv.getContext("2d");
      cc.setTransform(dpr, 0, 0, dpr, 0, 0);
      cc.translate(-x0, -y0);
      const sgx = Math.sign(sx || 1), sgy = Math.sign(sy || 1);
      cc.transform(escEfect * sgx * cos, -escEfect * sgx * sen, -escEfect * sgy * sen, -escEfect * sgy * cos, 0, 0);
      cc.lineCap = "round"; cc.lineJoin = "round";
      const k = nivel(Math.max(bb[2] - bb[0], bb[3] - bb[1]) * escEfect);
      for (const lote of def.lotes) {
        cc.strokeStyle = lote.color ? colorDeTrazo(lote.color, tema().oscuro && estado.modo !== "papel") : colorInsercion;
        cc.lineWidth = Math.max(1, lote.grosor * 3.78 * 0.35) / escEfect;
        cc.stroke(lote.paths[k]);
      }
      sp = { cv, x0, y0, w: x1 - x0, h: y1 - y0, escEfect };
      def.sprites.set(llave, sp);
      if (def.sprites.size > 6) def.sprites.delete(def.sprites.keys().next().value);
    }
    // Dónde cae el origen del bloque en pantalla, y de ahí la imagen. La
    // imagen se hizo a `escEfect`; se estira al zoom exacto de ahora.
    const f = esc * (Math.abs(sx) + Math.abs(sy)) / 2 / sp.escEfect;
    const ox = (t.p[0] - vx) * esc, oy = (vy - t.p[1]) * esc;
    c.drawImage(sp.cv, ox + sp.x0 * f, oy + sp.y0 * f, sp.w * f, sp.h * f);
  }

  function olvidar() { defs.clear(); pidiendo.clear(); cola.length = 0; }

  return { definicion, pintarInstancia, olvidar, nivel, adelgazar,
           get cargadas() { return defs.size; }, get pendientes() { return cola.length + enVuelo; } };
})();
window.Bloques = Bloques;

/** La caja del trazo en milímetros, calculada una vez y guardada en él.
 *
 *  Se guarda en el propio objeto y no en un índice aparte a propósito: los
 *  trazos se reemplazan por parches (ver `aplicarParche`), y un índice externo
 *  habría que invalidarlo a mano — que es exactamente el tipo de cosa que se
 *  olvida y deja media pantalla sin pintar. */
function cajaTrazo(t) {
  if (t._bb) return t._bb;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  if (t.clase === "insercion" && t.caja) {
    t._bb = t.caja;
    return t._bb;
  }
  if (t.clase === "texto") {
    const renglones = String(t.texto || "").split("\n");
    const ancho = t.ancho || 0.62 * (t.altura || 1) * Math.max(...renglones.map((r) => r.length), 1);
    const h = (t.altura || 1);
    // Los renglones de abajo cuelgan bajo la base del primero (texto de párrafo).
    const cuelga = 1.25 * h * (renglones.length - 1);
    // Con rotación se toma la caja del círculo que la envuelve: sobra un poco
    // y no se pierde nada, que es el lado por el que hay que equivocarse.
    const r = t.rotacion ? Math.hypot(ancho, h + cuelga) : 0;
    x0 = t.p[0] - r - ancho * 0.6; x1 = t.p[0] + ancho + r;
    y0 = t.p[1] - r - cuelga - h * 0.3; y1 = t.p[1] + h * 1.3 + r;
  } else if (t.clase === "imagen") {
    x0 = t.p[0]; y0 = t.p[1]; x1 = t.p[0] + t.ancho; y1 = t.p[1] + t.alto;
  } else if (t.clase === "relleno") {
    for (const pol of t.poligonos || []) {
      for (let i = 0; i < pol.length; i++) {
        const x = pol[i][0], y = pol[i][1];
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
    if (x0 === Infinity) { x0 = y0 = x1 = y1 = 0; }
  } else {
    const pts = t.puntos || [];
    for (let i = 0; i < pts.length; i++) {
      const x = pts[i][0], y = pts[i][1];
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
    if (!pts.length) { x0 = y0 = x1 = y1 = 0; }
  }
  t._bb = [x0, y0, x1, y1];
  return t._bb;
}

//: Menos de esto en pantalla y la entidad entera no da para más que una mancha.
const MINIMO_PX = 1.2;

/* --- REGEN: navegar sobre una foto, redibujar cuando se para el ratón ----
 *
 * Mike, 6-sep: *«sigue muy lento cuando el dibujo tiene muchas entidades y
 * estás con zoom alejado… AutoCAD no está dibujándolo todo el tiempo: hace
 * una imagen y la deja fija»*. Exacto. Hasta aquí cada movimiento del pan y
 * cada paso de la rueda **redibujaban el plano entero** —decenas de miles de
 * trazos— sesenta veces por segundo. En una máquina con la gráfica floja o con
 * la pantalla al 150 % eso se siente como arrastrar un mueble.
 *
 * Ahora, mientras dura el gesto (arrastrar con el botón central, girar la
 * rueda), el plano se pinta desde la **última foto** que se tomó de él: se
 * corre o se escala la imagen, que cuesta un milisegundo aunque haya un millón
 * de líneas. Se ve un poco borroso al acercarse, igual que en AutoCAD antes
 * del REGEN; y cuando el ratón se detiene un instante (`ESPERA_REGEN`) o se
 * suelta el botón, se redibuja fino. Es lo mismo que hace AutoCAD con su
 * lista de despliegue, y también lo que hace Google Maps con sus baldosas.
 *
 * Sólo entra si el plano es caro de pintar (`UMBRAL_MS`): en un plano chico
 * redibujar cuesta menos que la foto y se sigue pintando directo, nítido.
 *
 * El comando REGEN (alias RE, REGENALL) fuerza el redibujado y rehace el
 * índice, como en AutoCAD. */
const Regen = (() => {
  const UMBRAL_MS = 6;         // pintar más que esto → navegar sobre la foto
  const ESPERA_REGEN = 140;    // ms sin gesto → redibujar fino

  let foto = null;             // canvas fuera de pantalla con el último plano
  let fotoVista = null;        // {x, y, escala, w, h, dpr} con que se tomó
  let costo = 0;               // ms que costó el último pintado completo
  let enGesto = false;
  let temporizador = null;
  let contador = { fotos: 0, regens: 0 };

  function gesto() {
    enGesto = true;
    clearTimeout(temporizador);
    temporizador = setTimeout(terminarGesto, ESPERA_REGEN);
  }

  function terminarGesto() {
    clearTimeout(temporizador);
    temporizador = null;
    if (!enGesto) return;
    enGesto = false;
    if (!planoSirve()) { contador.regens++; pintar(); }
  }

  /** Guardar la foto del plano recién pintado (sólo si vale la pena). */
  function tomar(ms) {
    costo = ms;
    if (ms < UMBRAL_MS) { foto = null; fotoVista = null; return; }
    if (!foto) foto = document.createElement("canvas");
    if (foto.width !== lienzo.width || foto.height !== lienzo.height) {
      foto.width = lienzo.width; foto.height = lienzo.height;
    }
    const fc = foto.getContext("2d");
    fc.setTransform(1, 0, 0, 1, 0, 0);
    fc.clearRect(0, 0, foto.width, foto.height);
    fc.drawImage(lienzo, 0, 0);
    const v = estado.vista;
    fotoVista = { x: v.x, y: v.y, escala: v.escala, rx: v.rx, rz: v.rz,
                  w: lienzo.width, h: lienzo.height,
                  dpr: window.devicePixelRatio || 1, trazos: estado.trazos,
                  tema: tema().cual, modo: estado.modo, papel: estado.papel };
    contador.fotos++;
  }

  /** ¿Se puede navegar sobre la foto en vez de redibujar? */
  function sirve() {
    // Con cuatro ventanas la foto corrida ya no dice la verdad: mover una
    // ventana no mueve las otras. Se redibuja siempre.
    if (typeof Ventanas !== "undefined") return false;
    if (!enGesto || !foto || !fotoVista) return false;
    const f = fotoVista;
    // La foto se corre y se escala, pero **no se puede girar**: si la cámara
    // se movió, esta foto ya no dice la verdad y hay que redibujar. Sin esto,
    // orbitar durante un gesto estiraría el plano viejo y se vería deformado.
    if (f.rx !== estado.vista.rx || f.rz !== estado.vista.rz) return false;
    return f.trazos === estado.trazos && f.tema === tema().cual &&
           f.modo === estado.modo && f.papel === estado.papel &&
           f.w === lienzo.width && f.h === lienzo.height;
  }

  /** Pintar la foto corrida y escalada a la vista de ahora. */
  function pintarFoto(c) {
    const f = fotoVista, v = estado.vista;
    const k = v.escala / f.escala;
    // Dónde cae, en píxeles CSS de ahora, la esquina superior izquierda de la
    // foto: es el punto (f.x, f.y) en mm.
    const dx = (f.x - v.x) * v.escala;
    const dy = (v.y - f.y) * v.escala;
    const T = tema();
    c.save();
    c.fillStyle = estado.modo === "papel" ? T.lienzo : T.lienzo;
    c.fillRect(0, 0, lienzo.clientWidth, lienzo.clientHeight);
    // Suavizado siempre: al acercarse queda borroso (como el regen de AutoCAD)
    // en vez de pixelado en bloques, que Mike vio «chistoso».
    c.imageSmoothingEnabled = true;
    c.drawImage(foto, dx, dy, (f.w / f.dpr) * k, (f.h / f.dpr) * k);
    c.restore();
  }

  function olvidar() { foto = null; fotoVista = null; }

  /** REGEN de AutoCAD: redibujar todo y rehacer el índice. */
  function forzar() {
    olvidar();
    invalidarPlano();
    if (typeof Indice !== "undefined" && Indice.rehacer) Indice.rehacer();
    pintarYa();
    contador.regens++;
  }

  return { gesto, terminarGesto, tomar, sirve, pintarFoto, olvidar, forzar,
           get costo() { return costo; }, get enGesto() { return enGesto; },
           get contador() { return contador; }, UMBRAL_MS, ESPERA_REGEN };
})();

/* --- Cuándo hay que volver a dibujar el plano --------------------------- */
/* El plano vive en su propio lienzo y sólo se rehace cuando cambia algo que lo
 * afecta: el encuadre, el tamaño de la ventana, el tema o los propios trazos.
 *
 * La llave usa la **identidad del arreglo** de trazos, no su contenido:
 * `recargarTrazos` y `aplicarParche` siempre crean uno nuevo (ver app.js), así
 * que comparar la referencia es exacto y no cuesta nada. Si algún día alguien
 * empuja dentro del arreglo en vez de reemplazarlo, esto se quedaría con el
 * dibujo viejo — por eso queda dicho aquí y por eso `t019` lo comprueba. */
let _planoLlave = null;
let _planoTrazos = null;

function invalidarPlano() { _planoLlave = null; }

function llavePlano() {
  const v = estado.vista;
  // Las cuatro cámaras, no sólo la activa: navegar va en la ventana bajo el
  // cursor, y si su cámara cambia el plano tiene que redibujarse.
  const todas = typeof Ventanas !== "undefined"
    ? Ventanas.ventanas.map((q) => `${q.x}|${q.y}|${q.escala}|${q.rx}|${q.rz}|${q.ox}|${q.oy}|${q.w}|${q.h}`).join(";") : "";
  // La rejilla también: se pinta dentro del plano, que va en caché, así que si
  // no entra aquí apagarla no borra nada de la pantalla hasta que la vista se
  // mueva. Era justo lo que pasaba hasta la 0.19.0 con el botón REJILLA: la
  // preferencia cambiaba, el dibujo no. Con la llave puesta, el botón de
  // abajo, el comando REJILLA, F7 y los interruptores del título se arreglan
  // todos de una vez, y ninguno tiene que acordarse de invalidar nada.
  const pr = estado.prefs || {};
  const rv = pr.rejilla_ventanas || {}, rp = pr.rejilla_planos || {};
  const rej = `${pr.rejilla === false ? 0 : 1}${pr.rejilla_paso || 10}` +
    `${rv.Superior === false ? 0 : 1}${rv.Perspectiva === false ? 0 : 1}` +
    `${rv.Frontal === false ? 0 : 1}${rv.Lateral === false ? 0 : 1}` +
    `${rp.XY === false ? 0 : 1}${rp.XZ === false ? 0 : 1}${rp.YZ === false ? 0 : 1}`;
  return `${todas}#${v.x}|${v.y}|${v.escala}|${v.rx || 0}|${v.rz || 0}|${lienzo.width}|${lienzo.height}|` +
         `${tema().cual}|${estado.modo}|${estado.prefs && estado.prefs.borrador ? "b" : ""}|${rej}`;
}

/* En espacio papel el «plano» es la hoja, y ésa cambia sin que cambie la vista
 * —al tocar el pie, el formato o la escala—. `Papel.cargar` reemplaza el objeto
 * entero (ver ui/papel.js), así que vale la misma comparación por identidad. */
let _planoHoja = null;

const planoSirve = () =>
  _planoLlave === llavePlano() && _planoTrazos === estado.trazos &&
  _planoHoja === estado.papel;

let _pidiendoCuadro = false;

/* --- El parpadeo de «sí pasó»  ·  0.20.0 ----------------------------------
 *
 * Mike (9-sep-2026): «cuando entre un comando y se ejecute, no tengo ningún
 * feedback de que sí se ejecutó bien más que la caja de comandos de abajo.
 * Un mini mini mini flicker de casi nada para cuando el comando sí se ejecuta
 * bien; y cuando no, pues no pasa nada, así el feedback intuitivo es que el
 * programa no está haciendo nada».
 *
 * Un velo del color de marca al 6 % que aparece y se desvanece en 140 ms,
 * encima del lienzo. Va en un `div` con animación CSS y no pintado a mano:
 * no toca el plano ni la capa de encima, cuesta cero cuadros, y respeta
 * `prefers-reduced-motion` desde la hoja de estilos. Lo dispara `aplicarParche`
 * cuando la operación cambió algo de verdad (ver app.js). */
const Parpadeo = (() => {
  let veces = 0;
  function exito() {
    veces++;
    const p = (estado.prefs || {});
    if (p.parpadeo_comando === false) return;
    const el = document.getElementById("parpadeo");
    if (!el) return;
    el.classList.remove("si");
    void el.offsetWidth;                  // reinicia la animación si venía otra
    el.classList.add("si");
  }
  return { exito, get veces() { return veces; } };
})();
window.Parpadeo = Parpadeo;

// Para quien pinte en este mismo espacio —los cuerpos 3D— y para las
// pruebas. Son las dos únicas puertas entre milímetros y pantalla.
window.aPX = aPX;
window.aMM = aMM;
// Y el repintado, para la cámara, los cuerpos y el gesto del 3D. En 0.6.0
// pedían repintar por un nombre que no existía y el cuadro llegaba tarde.
window.pintar = pintar;
window.invalidarPlano = invalidarPlano;

/** Pide un repintado. No pinta: lo agenda para el próximo cuadro.
 *
 *  Ésta es la diferencia entre «va lento» y «se traba». El ratón manda eventos
 *  mucho más seguido de lo que la pantalla se refresca; pintando directo, los
 *  cuadros se encolan y el programa deja de responder aunque cada cuadro por
 *  separado sea razonable. */
function pintar() {
  if (_pidiendoCuadro) return;
  _pidiendoCuadro = true;
  requestAnimationFrame(() => { _pidiendoCuadro = false; pintarYa(); });
}

/** Dibuja el plano —rejilla, trazos y textos— en el contexto que se le dé.
 *
 *  Va aparte del resto porque es lo caro y lo que se guarda: se llama sólo
 *  cuando la vista cambió. Lo de encima —mira, selección, goma— se dibuja en
 *  cada cuadro, y es barato.
 */
/** Pinta las entidades del espacio activo.
 *
 * `fondo` en `false` las pinta **encima de lo que ya hay** —sin limpiar ni
 * pintar la rejilla—, que es como se dibuja sobre una hoja: primero la hoja,
 * luego lo que se puso sobre ella.
 */
/** Las cuatro esquinas de lo que hay dibujado, en el plano de trabajo. Es lo
 *  que se le da a las ventanas para que se encuadren solas. */
function puntosDelDibujo() {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const t of estado.trazos || []) for (const p of (t.puntos || [])) {
    if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
    if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
  }
  // Y las piezas: una pieza cuyo contorno se borró después de levantarla no
  // tiene trazos, y hasta la 0.19.0 encuadrar la dejaba fuera.
  const solidos = (typeof Cuerpos !== "undefined" && Cuerpos.esquinas) ? Cuerpos.esquinas() : [];
  if (!isFinite(x0)) return solidos;
  const planos = [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]];
  return solidos.length ? planos.concat(solidos) : planos;
}

function dibujarPlano(c, fondo = true) {
  const T = tema();
  // Sobre una hoja el fondo es **papel blanco**, aunque la app esté en tema
  // oscuro: si se tomara el tema, una capa blanca se pintaría blanca sobre
  // blanco y la nota que se acaba de escribir sería invisible. Es la misma
  // traducción que hace el plóter, y la que ya hacía el PDF.
  const oscuro = estado.modo === "papel" ? false : T.oscuro;
  // Girada, pinta el visor nuevo: un solo espacio, sin los atajos de planta.
  // En planta sigue todo lo de abajo, intacto, con sus cachés y sus pruebas.
  // El visor pinta siempre. Sólo el modo papel —las hojas, de donde sale el
  // PDF— se queda con el pintado viejo: es otro oficio y no tiene 3D.
  if (estado.modo !== "papel" && typeof Visor !== "undefined" && typeof Ventanas !== "undefined") {
    // Las cuatro ventanas, cada una con su cámara y recortada a su sitio. La
    // primera vez, la cámara de siempre pasa a ser la ventana superior y las
    // otras tres se encuadran a lo que hay.
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    Ventanas.repartir(w, h);
    Ventanas.adoptar(puntosDelDibujo());
    if (fondo) { c.clearRect(0, 0, w, h); c.fillStyle = T.lienzo; c.fillRect(0, 0, w, h); }
    Ventanas.pintarTodas(c, (cc, v) => Visor.pintarPlano(cc, {
      ancho: v.w, alto: v.h, fondo: false, lienzoColor: T.lienzo, oscuro,
      escala: v.escala, trazos: estado.trazos,
      borrador: !!(estado.prefs && estado.prefs.borrador), aPX,
      rx: v.rx || 0, rz: v.rz || 0,
      // La rejilla necesita saber dónde empieza y acaba **esta** ventana para
      // pintar sólo lo que cabe en ella. Hasta la 0.19.0 no se le pasaba nada
      // de esto y el interruptor REJILLA no hacía absolutamente nada: el visor
      // preguntaba por `ctx.rejilla` y nadie se lo mandaba.
      ox: v.ox, oy: v.oy, titulo: Ventanas.TITULO, persp: !!v.persp,
      rejilla: !!(estado.prefs && estado.prefs.rejilla),
      planos: Ventanas.planosRejilla(v),
      paso: (estado.prefs && estado.prefs.rejilla_paso) || 10,
      colorDe: (hex) => colorDeTrazo(hex, oscuro),
    }), oscuro);
    return;
  }
  const esc = estado.vista.escala;
  const vx = estado.vista.x, vy = estado.vista.y;
  const anchoPX = lienzo.clientWidth, altoPX = lienzo.clientHeight;

  if (fondo) {
    c.clearRect(0, 0, anchoPX, altoPX);
    c.fillStyle = T.lienzo;
    c.fillRect(0, 0, anchoPX, altoPX);
    if (!(estado.vista.rx || estado.vista.rz)) pintarRejilla(c);   // girada no significa nada
  }

  c.lineCap = "round";
  c.lineJoin = "round";

  // Lo que se ve, en milímetros, con un margen para que un trazo grueso que
  // asoma por el borde no desaparezca de golpe.
  // Con la cámara girada la ventana en milímetros no dice la verdad: lo que en
  // planta queda fuera puede estar en pantalla. Se pinta todo, y las líneas
  // pasan por aPX en vez del camino rápido, que sólo sabe de planta.
  const girada = !!(estado.vista.rx || estado.vista.rz);
  const margen = girada ? 1e12 : 20 / esc;
  const mx0 = vx - margen, mx1 = vx + anchoPX / esc + margen;
  const my1 = vy + margen, my0 = vy - altoPX / esc - margen;

  // Las imágenes de referencia van primero, debajo de todo: se calca encima.
  for (const t of estado.trazos) {
    if (t.clase === "imagen") pintarImagenRef(t, c);
  }

  /* Los lotes: llave de estilo → lista de trazos. Se arma cada vez que se
   * rehace el fondo porque lo que entra depende del encuadre; armarlo cuesta
   * un recorrido, y lo que ahorra son decenas de miles de llamadas al
   * lienzo. */
  const lotes = new Map();
  const textos = [];
  const instancias = [];           // inserciones de bloques pesados (ver Bloques)
  // Modo borrador (comando BORRADOR): la manera de LibreCAD y QCAD de aligerar
  // un plano pesado. Todo a 1 px, sin patrones de línea (las rayas son lo más
  // caro de trazar), y los textos como cajas. Se ve más tosco y va más suelto.
  const borrador = !!(estado.prefs && estado.prefs.borrador);

  // Los rellenos (rayado sólido) van debajo de las rayas, por su orden:
  // un sólido tapa lo que tenga debajo, pero no las líneas de encima.
  const rellenos = [];
  for (const t of estado.trazos) {
    if (t.clase === "ajena" || t.clase === "imagen") continue;

    const bb = cajaTrazo(t);
    if (bb[2] < mx0 || bb[0] > mx1 || bb[3] < my0 || bb[1] > my1) continue;

    if (t.clase === "relleno") { if (!borrador) rellenos.push(t); continue; }
    if (t.clase === "texto") {
      if (t.altura * esc >= 4) textos.push(t);   // más chico no se lee
      continue;
    }
    if (t.clase === "insercion") {
      // Diminuta: mancha como cualquier otra. Si no, se pinta con su definición.
      if ((bb[2] - bb[0]) * esc >= MINIMO_PX || (bb[3] - bb[1]) * esc >= MINIMO_PX) { instancias.push(t); continue; }
    }

    const grosor = borrador ? 1 : Math.max(1, t.grosor * 3.78 * 0.35);
    const patron = !borrador && (t.patron || []).length ? t.patron : null;
    const llave = t.color + "|" + grosor + "|" +
                  (patron ? patron.join(",") + "|" + (t.escala_tl || 1) : "");
    let lote = lotes.get(llave);
    if (!lote) {
      lote = { color: colorDeTrazo(t.color, oscuro), grosor, patron,
               escala_tl: t.escala_tl || 1, trazos: [], manchas: [], pixeles: null };
      lotes.set(llave, lote);
    }
    // Diminuta: se apunta como mancha, no como recorrido de vértices. Y dos
    // manchas que caen en el mismo píxel son una: alejado del todo, un plano
    // de obra tiene decenas de miles de cosas en unos cuantos miles de
    // píxeles, y pintar veinte veces el mismo punto es puro desperdicio.
    if (!girada && (bb[2] - bb[0]) * esc < MINIMO_PX && (bb[3] - bb[1]) * esc < MINIMO_PX) {
      const x = (((bb[0] + bb[2]) / 2 - vx) * esc) | 0;
      const y = ((vy - (bb[1] + bb[3]) / 2) * esc) | 0;
      const px = x * 65536 + y;
      if (!lote.pixeles) lote.pixeles = new Set();
      if (lote.pixeles.has(px)) continue;
      lote.pixeles.add(px);
      lote.manchas.push(x, y);
      continue;
    }
    lote.trazos.push(t);
  }

  for (const t of rellenos) {
    c.fillStyle = colorDeTrazo(t.color, oscuro);
    c.beginPath();
    for (const pol of t.poligonos) {
      for (let i = 0; i < pol.length; i++) {
        let px, py;
        if (girada) { const q = aPX(pol[i][0], pol[i][1], 0); px = q[0]; py = q[1]; }
        else { px = (pol[i][0] - vx) * esc; py = (vy - pol[i][1]) * esc; }
        i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
      }
      c.closePath();
    }
    c.fill("evenodd");
  }

  for (const lote of lotes.values()) {
    c.strokeStyle = lote.color;
    // El grosor del DXF está en mm de papel: se ve igual a cualquier zoom,
    // como en AutoCAD con LWDISPLAY encendido.
    c.lineWidth = lote.grosor;
    c.setLineDash(lote.patron
      ? lote.patron.map((v) => Math.max(1, Math.abs(v) * esc * lote.escala_tl))
      : []);
    // Las manchas: cuadritos de un píxel rellenados de una sola vez. Rellenar
    // rectángulos es lo más barato que sabe hacer un lienzo, mucho más que
    // trazar segmentos de 0.1 px con puntas redondas.
    if (lote.manchas.length) {
      const m = lote.manchas;
      c.fillStyle = lote.color;
      c.beginPath();
      for (let i = 0; i < m.length; i += 2) c.rect(m[i], m[i + 1], 1, 1);
      c.fill();
    }
    if (!lote.trazos.length) continue;
    c.beginPath();
    for (const t of lote.trazos) {
      const pts = t.puntos;
      if (!pts) continue;
      const n = pts.length;
      if (n < 2) continue;
      // La transformación va a mano y sin crear arreglos: `aPX` devuelve uno
      // nuevo por vértice, y a un millón de vértices por cuadro eso es trabajo
      // del recolector de basura, que es de lo que peor se recupera un
      // programa que tiene que ir a 60 cuadros.
      let px = (pts[0][0] - vx) * esc, py = (vy - pts[0][1]) * esc;
      c.moveTo(px, py);
      let ux = px, uy = py;
      for (let i = 1; i < n; i++) {
        px = (pts[i][0] - vx) * esc;
        py = (vy - pts[i][1]) * esc;
        // Vértices que caen en el mismo píxel: uno basta. El último siempre se
        // dibuja, o la figura quedaría abierta.
        if (i < n - 1 && Math.abs(px - ux) < 0.7 && Math.abs(py - uy) < 0.7) continue;
        c.lineTo(px, py);
        ux = px; uy = py;
      }
    }
    c.stroke();
  }
  c.setLineDash([]);

  for (const t of instancias) {
    Bloques.pintarInstancia(c, t, esc, vx, vy, colorDeTrazo(t.color, oscuro), borrador);
  }

  if (borrador) {
    // Cajas en vez de letras: el sitio del texto, sin el costo de las fuentes.
    c.strokeStyle = colorDeTrazo("#888888", oscuro);
    c.lineWidth = 1;
    c.beginPath();
    for (const t of textos) {
      const bb = cajaTrazo(t);
      c.rect((bb[0] - vx) * esc, (vy - bb[3]) * esc, (bb[2] - bb[0]) * esc, (bb[3] - bb[1]) * esc);
    }
    c.stroke();
    return;
  }
  for (const t of textos) {
    const alturaPX = t.altura * esc;
    c.fillStyle = colorDeTrazo(t.color, oscuro);
    const px = (t.p[0] - vx) * esc, py = (vy - t.p[1]) * esc;
    c.save();
    c.translate(px, py);
    if (t.rotacion) c.rotate(-t.rotacion * Math.PI / 180);
    c.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
    c.textAlign = t.alineacion === "CENTRO" ? "center"
      : t.alineacion === "DER" ? "right" : "left";
    const lineas = String(t.texto).split("\n");
    for (let i = 0; i < lineas.length; i++) {
      c.fillText(lineas[i], 0, i * alturaPX * 1.25);
    }
    c.restore();
  }

  // Los cuerpos 3D se pintan **aquí**, en el mismo lienzo y con la misma
  // cámara que las líneas. Ésa es la diferencia entre un visor pegado encima y
  // un espacio: la pieza se para sobre el contorno del que salió porque están
  // en el mismo sitio, no porque se hayan alineado a mano.
  if (typeof Cuerpos !== "undefined") Cuerpos.pintar(c, oscuro);
}

/** Pinta ahora mismo. Para cuando hace falta el resultado en el acto —una
 *  captura, una medición— y no se puede esperar al próximo cuadro. */
/* Cuadros lentos: se guardan los últimos con su desglose (plano, capa de
 * encima, referencia del ratón). Es lo que enseña PERF y DIAG cuando Mike
 * reporta «se puso lentísimo» y aquí no se reproduce. */
const Diag = { cuadros: [], activo: false, umbral: 40 };
function _anotarLento(desglose) {
  Diag.cuadros.push({ t: Date.now(), ...desglose });
  if (Diag.cuadros.length > 30) Diag.cuadros.shift();
  if (Diag.activo && typeof Comandos !== "undefined") {
    Comandos.eco(`cuadro lento: ${Object.entries(desglose).map(([k, v]) => `${k} ${typeof v === "number" ? v.toFixed(1) : v}`).join(" · ")}`, "malo");
  }
}

function pintarYa() {
  // Si un cuadro truena, se anota y el programa sigue vivo. En 0.6.0 un
  // error de dibujo se repetía en cada cuadro y dejó a Mike sin programa.
  try { _pintarYaCrudo(); }
  catch (e) { console.error("[vista] el cuadro tronó, el programa sigue:", e); }
}
function _pintarYaCrudo() {
  const anchoPX = lienzo.clientWidth, altoPX = lienzo.clientHeight;
  const tCuadro = performance.now();
  let tPlano = 0, tFoto = 0;

  // El plano, sólo si cambió algo suyo. Y en medio de un gesto de navegación
  // —pan o rueda— ni siquiera eso: se corre la foto (ver Regen).
  if (!planoSirve() && Regen.sirve()) {
    const t0 = performance.now();
    ctx.save();
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    Regen.pintarFoto(ctx);
    ctx.restore();
    tFoto = performance.now() - t0;
  } else if (!planoSirve()) {
    const t0 = performance.now();
    ctx.save();
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    if (estado.modo === "papel") {
      // La hoja tal como va a salir impresa —marco, pie de plano y lo que se
      // ve por las ventanas— y **encima, lo dibujado sobre la hoja**, con el
      // pintor de siempre: son entidades como cualquier otra, sólo que sus
      // milímetros son de papel. Así el osnap, la selección, los grips y el
      // repintado por parche funcionan igual aquí que en el modelo, sin una
      // segunda copia de todo eso.  ·  feature 68
      ctx.fillStyle = tema().lienzo;
      ctx.fillRect(0, 0, anchoPX, altoPX);
      Papel.pintarHoja(ctx);
      dibujarPlano(ctx, false);
    } else {
      dibujarPlano(ctx);
    }
    ctx.restore();
    _planoLlave = llavePlano();
    _planoTrazos = estado.trazos;
    _planoHoja = estado.papel;
    tPlano = performance.now() - t0;
    Regen.tomar(tPlano);
  }
  const tEncima0 = performance.now();

  // Y encima, lo que se mueve con el ratón. Esto es lo único que se rehace
  // sesenta veces por segundo, y no toca ni una línea del dibujo.
  ctxE.save();
  ctxE.clearRect(0, 0, encima.width, encima.height);
  // El ResizeObserver puede pedir un cuadro antes de que cargue seleccion.js.
  if (typeof Ventanas !== "undefined" && estado.modo !== "papel") {
    // La capa de encima también va ventana por ventana, con la cámara de cada
    // una: si se pintara una sola vez con la activa, la selección saldría
    // desfasada en las otras tres. Sólo la mira se queda en la activa.
    Ventanas.pintarTodas(ctxE, (cc) => {
      if (typeof Seleccion !== "undefined") Seleccion.pintarSeleccion(cc);
      pintarHule(cc);
      if (typeof Extrusion !== "undefined") Extrusion.pintar(cc);
      if (typeof TresD !== "undefined") TresD.pintarFantasma(cc);
      // Las cotas de la pieza señalada van antes que los tiradores: son un
      // letrero, y un letrero no debe taparle a la mano lo que va a agarrar.
      if (typeof CotasPieza !== "undefined") CotasPieza.pintar(cc);
      // Los tiradores van al final: son lo que se agarra, y lo que se agarra
      // se pinta encima de todo lo demás.
      if (typeof Tiradores !== "undefined") Tiradores.pintar(cc);
    }, tema().oscuro);
    pintarReferencia(ctxE);
    pintarMira(ctxE);
  } else {
    if (typeof Seleccion !== "undefined") Seleccion.pintarSeleccion(ctxE);
    if (window.VentanasHoja) VentanasHoja.pintarEncima(ctxE);
    pintarReferencia(ctxE);
    pintarMira(ctxE);
    pintarHule(ctxE);
  }
  ctxE.restore();

  const zoomTxt = Math.round(estado.vista.escala * 100) + "%";
  const fz = $("#f-zoom");
  if (fz.textContent !== zoomTxt) fz.textContent = zoomTxt;   // sin tocar el DOM si no cambió
  const total = performance.now() - tCuadro;
  if (total > Diag.umbral) {
    _anotarLento({ total, plano: tPlano, foto: tFoto, encima: performance.now() - tEncima0,
                   trazos: estado.trazos.length, sel: estado.sel ? estado.sel.size : 0,
                   captura: estado.captura ? 1 : 0, hule: estado.hule ? 1 : 0 });
  }
}

/* --- Imágenes de referencia  ·  feature 8 ------------------------------ */
/* El navegador no puede abrir un archivo del disco por su ruta, así que la
 * imagen se pide al motor, que sólo sirve las que el dibujo señala. Se guardan
 * en caché: sin eso, cada repintado pediría el archivo otra vez. */
const _cacheImagenes = new Map();

function pintarImagenRef(t, c = ctx) {
  let img = _cacheImagenes.get(t.id);
  if (!img) {
    img = new Image();
    // La imagen llega tarde, cuando el fondo ya está guardado sin ella: hay
    // que tirar el guardado o el PDF de calco no aparecería nunca.
    img.onload = () => { invalidarFondo(); pintar(); };
    img.onerror = () => { img.roto = true; };
    img.src = `/api/imagen_ref/${t.id}`;
    _cacheImagenes.set(t.id, img);
  }
  const [x0, y0] = aPX(t.p[0], t.p[1] + t.alto);
  const ancho = t.ancho * estado.vista.escala;
  const alto = t.alto * estado.vista.escala;
  c.save();
  if (img.complete && img.naturalWidth && !img.roto) {
    c.globalAlpha = t.opacidad === undefined ? 0.6 : t.opacidad;
    c.drawImage(img, x0, y0, ancho, alto);
  } else {
    // El archivo se movió o todavía no llega: se marca el hueco en vez de
    // dejar un vacío que parece que la imagen no existió nunca.
    c.strokeStyle = tema().warn;
    c.setLineDash([6, 4]);
    c.strokeRect(x0, y0, ancho, alto);
    c.setLineDash([]);
    if (img.roto && ancho > 80) {
      c.fillStyle = css.getPropertyValue("--warn").trim();
      c.font = "12px Cifras, Raleway, sans-serif";
      c.fillText("No se encuentra la imagen", x0 + 8, y0 + 20);
    }
  }
  c.restore();
}

/* --- Lo que se dibuja encima ------------------------------------------- */

// La goma: lo que la herramienta en curso quiere enseñar mientras el usuario
// mueve el cursor. Una herramienta devuelve una parte, o varias; así la
// polilínea puede pintar a la vez lo que ya lleva y el tramo que va colgando.
// El arco de a0 a a1 (grados, en el sentido del dibujo), en coordenadas del
// plano, recorrido cada 5° como mucho. Vale para el círculo entero (0 → 360).
function arcoPorElPlano(centro, r, a0, a1, P, c) {
  let barrido = ((a1 - a0) % 360 + 360) % 360;
  if (barrido === 0) barrido = 360;
  const n = Math.max(8, Math.ceil(barrido / 5));
  for (let i = 0; i <= n; i++) {
    const t = (a0 + barrido * i / n) * Math.PI / 180;
    const [px, py] = P(centro[0] + r * Math.cos(t), centro[1] + r * Math.sin(t));
    i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
  }
}

function pintarParte(h, c = ctx) {
  // Cada parte va por su plano, o por el de la ventana activa si no lo trae.
  const P = (x, y) => { const m = typeof Planos !== "undefined" ? Planos.aMundo(h.plano || estado.vista.plano || "XY", x, y, 0) : [x, y, 0]; return aPX(m[0], m[1], m[2]); };
  if (!h) return;
  c.beginPath();
  if (h.tipo === "linea") {
    const [ax, ay] = P(h.a[0], h.a[1]);
    const [bx, by] = P(h.b[0], h.b[1]);
    c.moveTo(ax, ay); c.lineTo(bx, by);
  } else if (h.tipo === "caja") {
    // Las cuatro esquinas, cada una por su plano. Con dos esquinas y c.rect
    // salía un cuadro derecho de pantalla, así que en la Perspectiva el
    // rectángulo en curso se veía flotando, no acostado en el suelo como va a
    // quedar. Lo pidió Mike el 24-sep: «ir representando el dibujo real sobre
    // el XY de la perspectiva», como Rhino.
    const esquinas = [[h.a[0], h.a[1]], [h.b[0], h.a[1]], [h.b[0], h.b[1]], [h.a[0], h.b[1]]];
    esquinas.forEach(([x, y], i) => {
      const [px, py] = P(x, y);
      i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
    });
    c.closePath();
  } else if (h.tipo === "polilinea") {
    const pts = h.puntos || [];
    for (let i = 0; i < pts.length; i++) {
      const [px, py] = P(pts[i][0], pts[i][1]);
      i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
    }
    if (h.cerrada && pts.length > 2) c.closePath();
  } else if (h.tipo === "circulo") {
    // Un círculo sobre el suelo, visto en la Perspectiva, es una elipse; y de
    // canto, una raya. c.arc con radio de pantalla siempre da un círculo, así
    // que el contorno se recorre punto a punto y cada punto pasa por el plano.
    arcoPorElPlano(h.c, Math.abs(h.r), 0, 360, P, c);
  } else if (h.tipo === "arco") {
    arcoPorElPlano(h.c, Math.abs(h.r), h.a0, h.a1, P, c);
  } else if (h.tipo === "texto") {
    // Texto de una previa (la cifra de una cota): mismo tamaño y giro que
    // tendrá la entidad, para que lo que se ve sea lo que va a quedar.
    const [px, py] = P(h.p[0], h.p[1]);
    const alturaPX = (h.altura || 2.5) * estado.vista.escala;
    if (alturaPX >= 3) {
      c.save();
      c.translate(px, py);
      if (h.rotacion) c.rotate(-h.rotacion * Math.PI / 180);
      c.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
      c.textAlign = h.alineacion === "CENTRO" ? "center" : h.alineacion === "DER" ? "right" : "left";
      c.textBaseline = "alphabetic";
      c.fillStyle = c.strokeStyle;
      c.fillText(String(h.texto), 0, 0);
      c.restore();
    }
    return;                                  // no hay trazo que dar
  } else if (h.tipo === "marca") {
    const [px, py] = P(h.p[0], h.p[1]);
    c.moveTo(px - 5, py); c.lineTo(px + 5, py);
    c.moveTo(px, py - 5); c.lineTo(px, py + 5);
  } else if (h.tipo === "relleno") {
    // La previa de un rayado sólido: el contorno relleno, translúcido.
    for (const pol of h.poligonos || []) {
      for (let i = 0; i < pol.length; i++) {
        const [px, py] = P(pol[i][0], pol[i][1]);
        i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
      }
      c.closePath();
    }
    c.save();
    c.globalAlpha = 0.35;
    c.fillStyle = c.strokeStyle;
    c.fill("evenodd");
    c.restore();
    return;
  } else if (h.tipo === "lineas") {
    // Muchas rayas de un jalón (la previa de un patrón de rayado).
    for (const par of h.lineas || []) {
      const [ax, ay] = P(par[0][0], par[0][1]);
      const [bx, by] = P(par[1][0], par[1][1]);
      c.moveTo(ax, ay); c.lineTo(bx, by);
    }
  }
  c.stroke();
}

/* El fantasma: lo seleccionado, dibujado donde va a quedar  ·  punto 13.
 *
 * Va translúcido y de un solo color a propósito. Si se pintara con los colores
 * de sus capas no se distinguiría del dibujo de verdad, y el usuario no sabría
 * cuál de las dos figuras es la que existe. */
function pintarFantasma(trazos, c, plano) {
  if (!trazos || !trazos.length) return;
  // El fantasma también va por el plano del trazo: sin esto, en la
  // Perspectiva se pintaba como si todo estuviera en el suelo, y en la
  // Frontal como si el suelo fuera la pared.
  const P = (x, y) => {
    const m = typeof Planos !== "undefined"
      ? Planos.aMundo(plano || estado.vista.plano || "XY", x, y, 0) : [x, y, 0];
    return aPX(m[0], m[1], m[2]);
  };
  c.save();
  c.globalAlpha = 0.45;
  c.strokeStyle = tema().acc2;
  c.fillStyle = tema().acc2;
  c.lineWidth = 1.2;
  c.setLineDash([]);
  for (const t of trazos) {
    if (t.clase === "texto") {
      const alturaPX = t.altura * estado.vista.escala;
      if (alturaPX < 4) continue;
      const [px, py] = P(t.p[0], t.p[1]);
      c.save();
      c.translate(px, py);
      if (t.rotacion) c.rotate(-t.rotacion * Math.PI / 180);
      c.font = `${alturaPX}px "Cifras", "Raleway", sans-serif`;
      c.textAlign = t.alineacion === "CENTRO" ? "center"
                    : t.alineacion === "DER" ? "right" : "left";
      c.textBaseline = "alphabetic";
      c.fillText(t.texto, 0, 0);
      c.restore();
      continue;
    }
    const pts = t.puntos || [];
    if (pts.length < 2) continue;
    c.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const [px, py] = P(pts[i][0], pts[i][1]);
      i === 0 ? c.moveTo(px, py) : c.lineTo(px, py);
    }
    c.stroke();
  }
  c.restore();
}

function pintarHule(c = ctx) {
  const h = estado.hule;
  if (!h) return;
  pintarFantasma(h.fantasma, c, h.plano);
  const T = tema();
  const css = { getPropertyValue: (n) => ({ "--acc2": T.acc2, "--texto3": T.texto3, "--lienzo": T.lienzo })[n] || "" };
  c.save();
  c.strokeStyle = T.acc2;
  c.lineWidth = 1;
  c.setLineDash(h.punteado === false ? [] : [5, 4]);
  // Las partes heredan el plano del hule: el plano es del trazo, no de la
  // ventana que lo esté pintando.
  const partes = (h.partes || [h]).map((parte) =>
    parte && h.plano && !parte.plano ? { ...parte, plano: h.plano } : parte);
  // Con una medida tecleada o fijada (ver Entrada.previaLargo): el vector de
  // dirección sigue punteado hasta el ratón, y encima, **lo que va a quedar**
  // —el tramo exacto de esa medida— va sólido y más grueso, con su cifra en
  // la punta. Lo pidió Mike: «una imagen previa de cómo va a quedar la
  // línea... que la sección equivalente a la longitud se marque diferente».
  const previa = (typeof Entrada !== "undefined") ? Entrada.previaLargo() : null;
  if (previa) {
    const [bx, by] = aPX(previa.base[0], previa.base[1]);
    const [cx, cy] = aPX(previa.cursor[0], previa.cursor[1]);
    const [px, py] = aPX(previa.p[0], previa.p[1]);
    // el rayo de dirección, más allá del ratón y de la punta
    const dx = px - bx, dy = py - by, l = Math.hypot(dx, dy) || 1;
    const lejos = Math.max(Math.hypot(cx - bx, cy - by), l) + 60;
    c.strokeStyle = css.getPropertyValue("--texto3").trim() || "#9aa3ad";
    c.setLineDash([3, 5]);
    c.beginPath(); c.moveTo(bx, by); c.lineTo(bx + dx / l * lejos, by + dy / l * lejos); c.stroke();
    c.setLineDash([]);
    c.strokeStyle = css.getPropertyValue("--acc2").trim();
    c.lineWidth = 2.2;
    for (const parte of partes) pintarParte(parte, c);
    // tope perpendicular en la punta y la cifra
    const nx = -dy / l, ny = dx / l, t = 6;
    c.lineWidth = 1.5;
    c.beginPath(); c.moveTo(px + nx * t, py + ny * t); c.lineTo(px - nx * t, py - ny * t); c.stroke();
    c.font = "600 11px Cifras, Raleway, sans-serif";
    c.fillStyle = css.getPropertyValue("--acc2").trim();
    c.textAlign = "center"; c.textBaseline = "middle";
    const etiqueta = mm(Math.abs(previa.valor));  // el signo es dirección, no tamaño
    const ex = (bx + px) / 2 + nx * 12, ey = (by + py) / 2 + ny * 12;
    const w = c.measureText(etiqueta).width + 8;
    c.save(); c.fillStyle = css.getPropertyValue("--lienzo").trim() || "#fff"; c.globalAlpha = 0.85;
    c.fillRect(ex - w / 2, ey - 8, w, 16); c.restore();
    c.fillText(etiqueta, ex, ey);
    c.restore();
    return;
  }
  for (const parte of partes) pintarParte(parte, c);
  c.setLineDash([]);
  c.restore();
}

// El marcador de la referencia encontrada. Cada modo tiene su forma, como en
// AutoCAD: el cuadrado es un extremo, el triángulo un punto medio, el círculo
// un centro. Se reconocen de reojo, sin leer.
function pintarReferencia(c = ctx) {
  const r = estado.ref;
  if (!r) return;
  const [px, py] = aPX(r.p[0], r.p[1]);
  const d = 6;
  c.save();
  // La línea de rastreo de la proyección perpendicular: punteada desde el
  // punto anterior hasta el punto encontrado, como en AutoCAD, para que se
  // vea de dónde sale.
  if (r.modo === "proyeccion" && r.desde) {
    const [bx, by] = aPX(r.desde[0], r.desde[1]);
    const dx = px - bx, dy = py - by, l = Math.hypot(dx, dy) || 1;
    c.strokeStyle = tema().texto3;
    c.lineWidth = 1;
    c.setLineDash([3, 4]);
    c.beginPath();
    c.moveTo(bx, by);
    c.lineTo(px + dx / l * 40, py + dy / l * 40);
    c.stroke();
  }
  c.strokeStyle = tema().ok;
  c.lineWidth = 1.8;
  c.setLineDash([]);
  c.beginPath();
  switch (r.modo) {
    case "proyeccion":
      // la escuadra de la perpendicular, hueca y con la rayita de rastreo
      c.moveTo(px - d, py - d); c.lineTo(px - d, py + d); c.lineTo(px + d, py + d);
      c.moveTo(px - d, py + 1); c.lineTo(px + 1, py + 1); c.lineTo(px + 1, py + d);
      c.moveTo(px + d, py - d); c.lineTo(px + d, py - d + 3);
      break;
    case "extremo":
      c.rect(px - d, py - d, d * 2, d * 2); break;
    case "medio":
      c.moveTo(px, py - d); c.lineTo(px + d, py + d);
      c.lineTo(px - d, py + d); c.closePath(); break;
    case "centro":
      c.arc(px, py, d, 0, Math.PI * 2); break;
    case "cuadrante":
      c.moveTo(px, py - d); c.lineTo(px + d, py);
      c.lineTo(px, py + d); c.lineTo(px - d, py); c.closePath(); break;
    case "interseccion":
      c.moveTo(px - d, py - d); c.lineTo(px + d, py + d);
      c.moveTo(px + d, py - d); c.lineTo(px - d, py + d); break;
    case "perpendicular":
      c.moveTo(px - d, py - d); c.lineTo(px - d, py + d);
      c.lineTo(px + d, py + d);
      c.moveTo(px - d, py + 1); c.lineTo(px + 1, py + 1); c.lineTo(px + 1, py + d);
      break;
    case "nodo":
      c.arc(px, py, d, 0, Math.PI * 2);
      c.moveTo(px - d, py); c.lineTo(px + d, py);
      c.moveTo(px, py - d); c.lineTo(px, py + d); break;
    default:  // cercano
      c.moveTo(px - d, py - d); c.lineTo(px + d, py + d);
      c.moveTo(px - d, py + d); c.lineTo(px + d, py - d);
      c.rect(px - d, py - d, d * 2, d * 2);
  }
  c.stroke();
  c.restore();
}

// La mira sólo aparece cuando hay una herramienta pidiendo un punto: mientras
// tanto el cursor de flecha dice mejor «aquí no estás dibujando».
let _cursorIconoPuesto = null;

function pintarMira(c = ctx) {
  // El puntero del sistema se esconde mientras una herramienta lleva icono
  // propio; si no, la flecha compite con la tijera.
  const icono = estado.cursorIcono || null;
  if (icono !== _cursorIconoPuesto) {
    _cursorIconoPuesto = icono;
    if (!arrastrePan && !cajaZoom) lienzo.style.cursor = icono ? "none" : "";
  }
  if (!estado.captura && !icono) return;
  const { px, py } = estado.cursor;
  c.save();
  if (estado.captura) {
    c.strokeStyle = tema().txt3;
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(px - 5000, py + 0.5); c.lineTo(px + 5000, py + 0.5);
    c.moveTo(px + 0.5, py - 5000); c.lineTo(px + 0.5, py + 5000);
    c.stroke();
  }
  if (icono) pintarIconoCursor(c, px, py, icono);
  c.restore();
}

/* El icono de la herramienta junto al cursor  ·  0.19.3.
 * Mike (7-sep-2026): «cuando esté activa la herramienta de trim, que el mouse
 * cambie a un ícono que parezca tijera, pero bien marcado el punto que
 * selecciona». El punto que selecciona es la caja: se pinta fuerte, en el
 * color de marca y con halo blanco para que se vea sobre cualquier fondo. La
 * tijera va abajo a la derecha, con las puntas apuntando a la caja, y no tapa
 * lo que se va a picar. */
function pintarIconoCursor(c, px, py, icono) {
  const T = tema();
  const acc = T.acc2 || "#0080C1";
  const halo = "rgba(255,255,255,.9)";
  // la caja de selección, bien marcada. Mike (9-sep-2026): «1 px de grosor
  // y la mitad de tamaño»: 6 px de lado, raya de 1 px y un halo fino.
  const h = 3;
  const x0 = Math.round(px) - h + 0.5, y0 = Math.round(py) - h + 0.5;
  c.lineWidth = 3; c.strokeStyle = halo;
  c.strokeRect(x0, y0, 2 * h, 2 * h);
  c.lineWidth = 1; c.strokeStyle = acc;
  c.strokeRect(x0, y0, 2 * h, 2 * h);

  const trazo = (dibuja) => {
    c.lineCap = "round"; c.lineJoin = "round";
    c.lineWidth = 4.5; c.strokeStyle = halo; c.fillStyle = halo;
    dibuja(true);
    c.lineWidth = 2; c.strokeStyle = T.txt || "#1A1F27"; c.fillStyle = T.lienzo || "#fff";
    dibuja(false);
  };
  c.translate(px + 17, py + 17);
  // El glifo vive en ui/iconos.js; aquí sólo se pone el halo y la tinta.
  trazo((fondo) => Iconos.pintar(c, icono, fondo));
}

/* --- Ratón: pan, zoom y zoom por ventana -------------------------------- */
let arrastrePan = null;
let cajaZoom = null;          // zoom por ventana en curso

/* Espacio apretado: con él, arrastrar con el botón izquierdo mueve la vista.
 * Es para la laptop sin botón central, ahora que el derecho es la rueda. */
let espacioApretado = false;
window.addEventListener("keydown", (e) => {
  if (e.key === " " && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
      && !Entrada.esperandoTextoLibre) espacioApretado = true;
});
window.addEventListener("keyup", (e) => { if (e.key === " ") espacioApretado = false; });
window.addEventListener("blur", () => { espacioApretado = false; });

function esPan(e) {
  // Botón central, o Espacio con el izquierdo (para la laptop).
  //
  // **Ni Shift ni el botón derecho son pan ya.** Shift suma a la selección y
  // suelta el ortho; el derecho es la rueda de herramientas (ver ui/radial.js)
  // y, corto, es Enter. Es el reparto de AutoCAD y de Maya, que es lo que las
  // manos ya saben.
  return e.button === 1 || (e.button === 0 && espacioApretado);
}

lienzo.addEventListener("mousedown", (e) => {
  // Cuatro ventanas: clic en una la activa; doble clic en su título la
  // maximiza o la devuelve. Se decide antes que nada, porque todo lo demás
  // trabaja sobre la ventana activa.
  if (typeof Ventanas !== "undefined") {
    const cajaV = lienzo.getBoundingClientRect();
    const vx0 = e.clientX - cajaV.left, vy0 = e.clientY - cajaV.top;
    // Los interruptores de rejilla del título van antes que nada: caen dentro
    // de la franja del título, y si no se atienden aquí el clic se lo come el
    // «activar esta ventana» de abajo.
    const bot = Ventanas.botonEn(vx0, vy0);
    if (bot) {
      const cambio = Ventanas.alternarRejilla(bot);
      if (typeof guardarPrefs === "function") guardarPrefs(cambio);
      if (typeof pintarInterruptores === "function") pintarInterruptores();
      invalidarPlano(); pintar(); e.preventDefault(); return;
    }
    const t = Ventanas.enTitulo(vx0, vy0);
    if (t >= 0) {
      if (e.detail >= 2) Ventanas.maximizar(t); else Ventanas.activar(t);
      invalidarPlano(); pintar(); e.preventDefault(); return;
    }
    const i = Ventanas.bajo(vx0, vy0);
    if (e.button === 0 && i >= 0 && i !== Ventanas.activa) { Ventanas.activar(i); invalidarPlano(); pintar(); }
    if (e.button === 1) Ventanas.navegarEn(vx0, vy0);      // pan u órbita donde está el cursor
  }
  // Botón derecho: la rueda si se arrastra, Enter si se suelta sin mover.
  if (e.button === 2) { Radial.abajo(e); e.preventDefault(); return; }
  // Alt + botón central: orbitar. Sin Alt, el central sigue siendo pan.
  // Botón central: en la Perspectiva orbita y Alt + central hace pan. En las
  // otras tres el central es pan, como siempre, y Alt + central orbita.
  if (e.button === 1 && typeof Camara !== "undefined" && estado.vista.persp && !e.shiftKey) { Camara.arrastrar(e); e.preventDefault(); return; }
  if (esPan(e)) {
    if (e.button === 0) window.__espacioArrastro = true;   // que el espacio no confirme al soltar
    arrastrePan = { px: e.clientX, py: e.clientY, vx: estado.vista.x, vy: estado.vista.y };
    lienzo.style.cursor = "grabbing";
    e.preventDefault();
    return;
  }
  // El 3D después del pan y antes de todo lo demás: si el clic cayó sobre la
  // cara de una pieza, es del 3D. Si no, sigue como siempre.
  // Antes que la cara: un tirador se ve encima de ella y se agarra antes.
  // Si el orden fuera el otro, jalar una esquina empezaría a jalar la cara que
  // tiene debajo y no habría manera de llegar nunca a la esquina.
  // La cota se pinta encima de todo, así que se agarra antes que todo: si
  // no, picar el número empezaría a jalar el tirador de debajo.
  if (typeof CotasPieza !== "undefined" && CotasPieza.abajo(e)) { e.preventDefault(); return; }
  if (typeof Tiradores !== "undefined" && Tiradores.abajo(e)) { e.preventDefault(); return; }
  if (typeof TresD !== "undefined" && TresD.abajo(e)) { e.preventDefault(); return; }
  if (cajaZoom) {
    const caja = lienzo.getBoundingClientRect();
    const [mx, my] = aMM(e.clientX - caja.left, e.clientY - caja.top);
    if (!cajaZoom.a) {
      cajaZoom.a = [mx, my];
      estado.hule = { tipo: "caja", a: cajaZoom.a, b: [mx, my], plano: estado.vista.plano };
    } else {
      encuadrarCaja(cajaZoom.a[0], cajaZoom.a[1], mx, my);
      cajaZoom = null;
      estado.hule = null;
      Comandos.terminar();
    }
    pintar();
    return;
  }
  if (e.button !== 0) return;
  const caja = lienzo.getBoundingClientRect();
  const p = aMM(e.clientX - caja.left, e.clientY - caja.top);
  if (estado.captura) { Entrada.clicEnLienzo(); return; }
  // Editando las ventanas de la hoja (EDITARVENTANA): el ratón es de los handles.
  if (window.VentanasHoja && VentanasHoja.activo && VentanasHoja.clicAbajo(p)) { e.preventDefault(); return; }
  // En la hoja también se selecciona: lo que se dibujó **sobre** la hoja son
  // entidades del espacio papel, y se agarran, se mueven y se borran como
  // cualquier otra. Lo que se ve por las ventanas no: eso es el modelo mirado
  // desde aquí, y se edita en el modelo (igual que en AutoCAD).
  if (typeof Seleccion !== "undefined") Seleccion.clicAbajo(e, p);
});

lienzo.addEventListener("mouseup", (e) => {
  if (typeof Tiradores !== "undefined" && Tiradores.arrastrando()) { Tiradores.arriba(); return; }
  if (typeof TresD !== "undefined" && TresD.arrastrando()) { TresD.arriba(); return; }
  if (e.button !== 0 || estado.captura || cajaZoom) return;
  const caja = lienzo.getBoundingClientRect();
  const p = aMM(e.clientX - caja.left, e.clientY - caja.top);
  if (window.VentanasHoja && VentanasHoja.activo) { VentanasHoja.clicArriba(p); return; }
  if (typeof Seleccion !== "undefined") Seleccion.clicArriba(e, p);
});

window.addEventListener("mouseup", (e) => {
  // También aquí: un arrastre que termina con el ratón fuera del lienzo tiene
  // que soltarse igual, o el tirador se queda pegado al cursor para siempre.
  // `arriba()` se desarma sola, así que llamarla dos veces no hace daño.
  if (typeof Tiradores !== "undefined" && Tiradores.arrastrando()) Tiradores.arriba();
  if (typeof Ventanas !== "undefined") Ventanas.terminarNavegacion();
  if (arrastrePan) { arrastrePan = null; lienzo.style.cursor = ""; Regen.terminarGesto(); }
  if (e.button === 2) Radial.arriba(e);
});
window.addEventListener("mousemove", (e) => {
  if ((e.buttons & 2) && Radial.activo) Radial.arrastre(e);
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && Radial.activo) Radial.cancelar();
  // Esc o Enter apagan la edición de ventanas de la hoja.
  if ((e.key === "Escape" || e.key === "Enter") && window.VentanasHoja && VentanasHoja.activo &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) VentanasHoja.activar(false);
});
lienzo.addEventListener("contextmenu", (e) => e.preventDefault());
document.addEventListener("contextmenu", (e) => { if (Radial.activo) e.preventDefault(); });

lienzo.addEventListener("mousemove", (e) => {
  if (typeof Tiradores !== "undefined" && Tiradores.mover(e)) return;
  if (typeof TresD !== "undefined" && TresD.mover(e)) return;
  const caja = lienzo.getBoundingClientRect();
  const px = e.clientX - caja.left, py = e.clientY - caja.top;
  // Con un comando pidiendo un punto, **manda la ventana donde está el ratón**
  // (Mike, 23-sep). Antes el punto se leía siempre con la cámara de la ventana
  // activa: medido el 24-sep, apuntar al centro de la Perspectiva con la
  // Superior activa tomaba un punto a 558 mm del que se estaba señalando. Eso
  // es «aparece en un lugar que no tienes control».
  //
  // El plano del comando manda sobre esto: una vez tomado el primer punto, una
  // ventana de otro plano ya no puede adoptar el trazo —la línea acabaría con
  // un extremo en el suelo y el otro en la pared—, así que el hule se queda
  // quieto mientras el cursor ande por ahí.
  if (typeof Ventanas !== "undefined" && estado.captura && estado.modo !== "papel" &&
      !arrastrePan && !cajaZoom) {
    const i = Ventanas.bajo(px, py);
    if (i >= 0 && i !== Ventanas.activa) {
      const fijo = typeof Entrada !== "undefined" ? Entrada.planoComando() : null;
      if (!fijo || Ventanas.la(i).plano === fijo) {
        Ventanas.activar(i);
        invalidarPlano();
      } else {
        estado.cursor = { ...estado.cursor, px, py };
        pintar();
        return;
      }
    }
  }
  const [mx, my] = aMM(px, py);
  estado.cursor = { px, py, x: mx, y: my };
  // El ratón sabe si Shift está apretado aunque el teclado se haya perdido un
  // keyup (cambiar de ventana con Shift puesto, por ejemplo). Con esto el
  // ortho momentáneo nunca se queda pegado.
  fijarShift(e.shiftKey);

  if (arrastrePan) {
    estado.vista.x = arrastrePan.vx - (e.clientX - arrastrePan.px) / estado.vista.escala;
    estado.vista.y = arrastrePan.vy + (e.clientY - arrastrePan.py) / estado.vista.escala;
    Regen.gesto();
    pintar();
    return;
  }
  if (cajaZoom && cajaZoom.a) {
    estado.hule = { tipo: "caja", a: cajaZoom.a, b: [mx, my], plano: estado.vista.plano };
    pintar();
    return;
  }
  // Los módulos de más abajo (seleccion.js, entrada.js) pueden no haber
  // cargado todavía si el ratón ya se mueve sobre la página: no es un error.
  if (typeof Seleccion === "undefined" || typeof Entrada === "undefined") return;
  if (!estado.captura && window.VentanasHoja && VentanasHoja.activo && VentanasHoja.alMover([mx, my])) return;
  if (!estado.captura && Seleccion.alMover([mx, my])) return;
  // Con icono de herramienta (tijera), el ratón lleva encima algo que se
  // mueve con él aunque no se esté pidiendo un punto.
  if (estado.cursorIcono && !estado.captura) pintar();
  Entrada.alMoverse();
});

lienzo.addEventListener("wheel", (e) => {
  e.preventDefault();
  const caja = lienzo.getBoundingClientRect();
  const f = (estado.prefs && estado.prefs.zoom_rueda) || 1.15;
  if (typeof Ventanas !== "undefined") Ventanas.navegarEn(e.clientX - caja.left, e.clientY - caja.top);
  zoomEn(e.clientX - caja.left, e.clientY - caja.top, e.deltaY < 0 ? f : 1 / f);
  if (typeof Ventanas !== "undefined") Ventanas.terminarNavegacion();
  Entrada.alMoverse();
}, { passive: false });

/* Doble clic: si cayó encima de un texto, se edita ahí mismo; si no, encuadra.
 *
 * Es lo que hace cualquier CAD y lo que la mano intenta sin pensarlo. Sin esto,
 * corregir una falta de ortografía en un rótulo obligaba a borrarlo y volver a
 * escribirlo entero en el sitio exacto. */
lienzo.addEventListener("dblclick", async () => {
  // En la hoja, doble clic sobre un dato del pie de plano lo edita ahí mismo.
  if (estado.modo === "papel" && !Entrada.activa) {
    const campo = Papel.campoEn(estado.cursor.x, estado.cursor.y);
    if (campo) { Papel.editarCampo(campo); return; }
  }
  if (estado.modo !== "papel" && !Entrada.activa) {
    // `candidatos` devuelve {id, d} ordenados por cercanía, no ids pelados.
    const c = (Seleccion.candidatos([estado.cursor.x, estado.cursor.y]) || [])[0];
    if (c && c.id && await Dibujar.editarTexto(c.id)) return;
  }
  estado.modo === "papel" ? Papel.encuadrarHoja() : encuadrar();
});

function iniciarZoomVentana() {
  cajaZoom = { a: null };
  lienzo.style.cursor = "crosshair";
}
