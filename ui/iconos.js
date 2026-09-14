/* Los iconos de las herramientas, junto al cursor  ·  0.19.3
 *
 * Mike (7-sep-2026): primero la tijera de RECORTAR («que el mouse cambie a un
 * ícono que parezca tijera, pero bien marcado el punto que selecciona») y
 * luego «sí, agreguemos sus íconos a las herramientas».
 *
 * Cada glifo se dibuja en canvas dentro de una caja de ±10 px centrada en
 * (0, 0); vista.js lo coloca abajo a la derecha del cursor y lo pinta dos
 * veces, primero con un halo blanco grueso y luego con la tinta, para que se
 * lea sobre cualquier fondo. Nada de imágenes: un glifo son diez líneas y así
 * se ve igual de nítido a cualquier zoom y en cualquier pantalla.
 *
 * `POR_COMANDO` dice qué glifo lleva cada comando; Comandos.correr lo pone en
 * `estado.cursorIcono` mientras el comando dura. Una herramienta puede
 * cambiarlo a medio camino (Seleccion.pedirUna({icono})).
 */
const Iconos = (() => {
  const R = Math.PI / 180;

  // Ayudas para dibujar: `L` una polilínea, `O` un círculo o arco, `F` relleno.
  const L = (c, pts, cerrar = false) => {
    c.beginPath();
    pts.forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])));
    if (cerrar) c.closePath();
    c.stroke();
  };
  const O = (c, x, y, r, a0 = 0, a1 = 360) => { c.beginPath(); c.arc(x, y, r, a0 * R, a1 * R); c.stroke(); };
  const punta = (c, x, y, ang, t = 4) => {          // punta de flecha en (x,y) mirando a `ang`
    const a = ang * R;
    L(c, [[x - t * Math.cos(a - 0.5), y - t * Math.sin(a - 0.5)], [x, y], [x - t * Math.cos(a + 0.5), y - t * Math.sin(a + 0.5)]]);
  };

  const GLIFOS = {
    tijera(c, fondo) {
      c.save(); c.rotate(45 * R);
      L(c, [[-11, -2.5], [0, 0], [7, 4.5]]);
      L(c, [[-11, 2.5], [0, 0], [7, -4.5]]);
      for (const y of [6.5, -6.5]) {
        c.beginPath(); c.arc(9.5, y, 3.2, 0, Math.PI * 2);
        if (fondo) c.stroke(); else { c.fill(); c.stroke(); }
      }
      c.restore();
    },
    extender(c) {
      c.save(); c.rotate(45 * R);
      L(c, [[8, 0], [-8, 0]]); punta(c, -9, 0, 180, 5); L(c, [[8, -5], [8, 5]]);
      c.restore();
    },
    linea(c) { L(c, [[-8, 7], [8, -7]]); O(c, -8, 7, 1.6); O(c, 8, -7, 1.6); },
    polilinea(c) { L(c, [[-9, 6], [-3, -6], [3, 4], [9, -6]]); },
    rectangulo(c) { L(c, [[-9, -6], [9, -6], [9, 6], [-9, 6]], true); },
    poligono(c) { L(c, [0, 60, 120, 180, 240, 300].map((a) => [9 * Math.cos(a * R), 9 * Math.sin(a * R)]), true); },
    circulo(c) { O(c, 0, 0, 8); O(c, 0, 0, 1.2); },
    arco(c) { O(c, 0, 2, 8, 200, 340); O(c, 0, 2, 1.2); },
    elipse(c) { c.save(); c.scale(1, 0.6); O(c, 0, 0, 9); c.restore(); },
    spline(c) { c.beginPath(); c.moveTo(-9, 6); c.bezierCurveTo(-4, -12, 4, 14, 9, -6); c.stroke(); },
    punto(c) { O(c, 0, 0, 2); L(c, [[-6, 0], [-3, 0]]); L(c, [[3, 0], [6, 0]]); L(c, [[0, -6], [0, -3]]); L(c, [[0, 3], [0, 6]]); },
    rayado(c) { L(c, [[-8, -8], [8, -8], [8, 8], [-8, 8]], true); for (const d of [-6, 0, 6]) L(c, [[-8, d + 8], [8, d - 8]].map((p) => [Math.max(-8, Math.min(8, p[0])), Math.max(-8, Math.min(8, p[1]))])); },
    texto(c) { L(c, [[-7, 8], [0, -8], [7, 8]]); L(c, [[-4, 2], [4, 2]]); },
    textom(c) { for (const y of [-6, -1, 4]) L(c, [[-8, y], [y === 4 ? 2 : 8, y]]); },
    borrar(c) { L(c, [[-7, -7], [7, 7]]); L(c, [[-7, 7], [7, -7]]); },
    mover(c) { L(c, [[-9, 0], [9, 0]]); L(c, [[0, -9], [0, 9]]); punta(c, 9, 0, 0); punta(c, -9, 0, 180); punta(c, 0, -9, -90); punta(c, 0, 9, 90); },
    copiar(c, fondo) { L(c, [[-8, -8], [3, -8], [3, 3], [-8, 3]], true); c.beginPath(); c.rect(-3, -3, 11, 11); if (fondo) c.stroke(); else { c.fill(); c.stroke(); } },
    rotar(c) { O(c, 0, 0, 8, 200, 470); punta(c, 8 * Math.cos(110 * R), 8 * Math.sin(110 * R), 200); },
    escalar(c) { L(c, [[-8, 2], [-8, 8], [-2, 8]], false); L(c, [[-8, 8], [7, -7]]); punta(c, 7, -7, -45); L(c, [[1, -7], [7, -7], [7, -1]]); },
    espejo(c) { L(c, [[-3, -7], [-3, 7], [-9, 7]], true); L(c, [[3, -7], [3, 7], [9, 7]], true); c.save(); c.setLineDash([2, 2]); L(c, [[0, -10], [0, 10]]); c.restore(); },
    desfase(c) { O(c, -6, 8, 12, 270, 360); O(c, -6, 8, 7, 270, 360); },
    empalme(c) { c.beginPath(); c.moveTo(-8, 8); c.lineTo(-8, -1); c.arcTo(-8, -8, -1, -8, 7); c.lineTo(8, -8); c.stroke(); },
    chaflan(c) { L(c, [[-8, 8], [-8, -2], [-2, -8], [8, -8]]); },
    arreglo(c) { for (const x of [-6, 0, 6]) for (const y of [-6, 0, 6]) O(c, x, y, 1.4); },
    estirar(c) { L(c, [[-9, -6], [2, -6], [2, 6], [-9, 6]], true); L(c, [[2, 0], [9, 0]]); punta(c, 9, 0, 0); },
    igualar(c) { L(c, [[-8, -5], [8, -5]]); c.save(); c.setLineDash([3, 2]); L(c, [[-8, 1], [8, 1]]); c.restore(); L(c, [[0, -3], [0, 8]]); punta(c, 0, 8, 90); },
    unir(c) { L(c, [[-9, 3], [-1, 3]]); L(c, [[1, -3], [9, -3]]); L(c, [[-1, 3], [1, -3]]); O(c, 0, 0, 2); },
    grupo(c) { c.save(); c.setLineDash([2, 2]); L(c, [[-9, -9], [9, -9], [9, 9], [-9, 9]], true); c.restore(); O(c, -4, -3, 2.5); L(c, [[1, 1], [7, 1], [7, 6], [1, 6]], true); },
    desagrupar(c) { O(c, -5, -4, 2.5); L(c, [[1, 1], [7, 1], [7, 6], [1, 6]], true); L(c, [[-2, 6], [2, -2]]); },
    explotar(c) { for (let i = 0; i < 8; i++) { const a = i * 45 * R; L(c, [[3 * Math.cos(a), 3 * Math.sin(a)], [9 * Math.cos(a), 9 * Math.sin(a)]]); } },
    cota(c) { L(c, [[-9, -6], [-9, 6]]); L(c, [[9, -6], [9, 6]]); L(c, [[-9, 2], [9, 2]]); L(c, [[-7, 4], [-11, 0]]); L(c, [[11, 4], [7, 0]]); },
    cotaangular(c) { L(c, [[-8, 8], [8, 8]]); L(c, [[-8, 8], [4, -6]]); O(c, -8, 8, 9, 310, 360); },
    cotaradio(c) { O(c, 0, 0, 8); L(c, [[0, 0], [8 * Math.cos(-40 * R), 8 * Math.sin(-40 * R)]]); punta(c, 8 * Math.cos(-40 * R), 8 * Math.sin(-40 * R), -40, 3.5); },
    cotadiametro(c) { O(c, 0, 0, 8); L(c, [[-8 * Math.cos(40 * R), 8 * Math.sin(40 * R)], [8 * Math.cos(40 * R), -8 * Math.sin(40 * R)]]); },
    directriz(c) { L(c, [[-9, 7], [0, -3], [9, -3]]); punta(c, -9, 7, 135, 4); },
    bloque(c) { L(c, [[-8, -3], [0, -8], [8, -3], [8, 5], [0, 10], [-8, 5]], true); L(c, [[-8, -3], [0, 2], [8, -3]]); L(c, [[0, 2], [0, 10]]); },
    insertar(c) { L(c, [[-8, -3], [0, -8], [8, -3], [8, 5], [0, 10], [-8, 5]], true); L(c, [[0, 2], [0, 10]]); L(c, [[-8, -3], [0, 2], [8, -3]]); },
    biblioteca(c) { for (const x of [-8, -2, 4]) L(c, [[x, -8], [x + 4, -8], [x + 4, 8], [x, 8]], true); },
    imagen(c) { L(c, [[-9, -7], [9, -7], [9, 7], [-9, 7]], true); L(c, [[-9, 4], [-3, -2], [1, 2], [4, -1], [9, 4]]); O(c, 5, -3, 1.5); },
    medir(c) { c.save(); c.rotate(-45 * R); L(c, [[-10, -3], [10, -3], [10, 3], [-10, 3]], true); for (const x of [-6, -2, 2, 6]) L(c, [[x, -3], [x, x % 4 ? 0 : 1]]); c.restore(); },
    ventana(c) { L(c, [[-9, -7], [9, -7], [9, 7], [-9, 7]], true); c.save(); c.setLineDash([2, 2]); L(c, [[-5, -3], [4, -3], [4, 4], [-5, 4]], true); c.restore(); },
    zoom(c) { O(c, -2, -2, 6); L(c, [[2.5, 2.5], [9, 9]]); },
    pan(c) { L(c, [[-9, 0], [9, 0]]); punta(c, 9, 0, 0); punta(c, -9, 0, 180); },
  };

  const POR_COMANDO = {
    LINEA: "linea", POLILINEA: "polilinea", RECTANGULO: "rectangulo", POLIGONO: "poligono",
    CIRCULO: "circulo", ARCO: "arco", ELIPSE: "elipse", SPLINE: "spline", PUNTO: "punto",
    RAYADO: "rayado", TEXTO: "textom", VENTANAHOJA: "ventana", VENTANANUEVA: "ventana", BORRARVENTANA: "ventana",
    BORRAR: "borrar", MOVER: "mover", COPIAR: "copiar", ROTAR: "rotar", ESCALAR: "escalar",
    ESPEJO: "espejo", DESFASE: "desfase", RECORTAR: "tijera", EXTENDER: "extender",
    EMPALME: "empalme", CHAFLAN: "chaflan", ARREGLO: "arreglo", ESTIRAR: "estirar",
    IGUALAR: "igualar", UNIR: "unir", GRUPO: "grupo", DESAGRUPAR: "desagrupar", EXPLOTAR: "explotar",
    COTA: "cota", COTAH: "cota", COTAV: "cota", COTAALINEADA: "cota", COTACONTINUA: "cota",
    COTABASE: "cota", COTAANGULAR: "cotaangular", COTARADIO: "cotaradio", COTADIAMETRO: "cotadiametro",
    DIRECTRIZ: "directriz", BLOQUE: "bloque", INSERTAR: "insertar", BIBLIOTECA: "biblioteca",
    IMAGENREF: "imagen", PDFFONDO: "imagen", DISTANCIA: "medir", MEDIR: "medir", AREA: "medir",
  };

  /** Pinta el glifo `nombre` centrado en (0,0) del contexto ya trasladado. */
  function pintar(c, nombre, fondo) {
    const g = GLIFOS[nombre];
    if (!g) return false;
    g(c, fondo);
    return true;
  }

  return { pintar, POR_COMANDO, GLIFOS, tiene: (n) => !!GLIFOS[n] };
})();
window.Iconos = Iconos;
