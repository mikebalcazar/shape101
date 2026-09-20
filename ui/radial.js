/* Menú radial  ·  lo pidió Mike el 4-sep, «tipo Maya».
 *
 * **Clic derecho sostenido y arrastrar**: sale una rueda de herramientas
 * centrada donde se apretó; se mueve el ratón hacia la que se quiere y se
 * suelta. No hay que atinarle a nada: manda el **ángulo**, no la posición. Con
 * un poco de uso el gesto se aprende con la mano —«derecha arriba es línea,
 * abajo son cotas»— y deja de hacer falta mirar la rueda.
 *
 * Las que tienen hijos (▸) abren un segundo anillo alrededor de sí mismas al
 * pasar por encima: las cotas están a las seis, y en ese anillo la cota recta
 * está también a las seis, así que «derecho, abajo, más abajo, soltar» es una
 * cota recta. Lo que se pone en cada gajo está en `RUEDA`, aquí abajo, y se
 * puede cambiar sin tocar nada más.
 *
 * Lo que cambió a cambio: el botón derecho ya no arrastra la vista. Eso queda
 * con el botón central y con **Espacio + arrastrar** (para la laptop). Y un
 * clic derecho corto, sin mover, es Enter — igual que en AutoCAD.
 */

const Radial = (() => {
  /* --- Qué hay en la rueda ------------------------------------------------
   * Ocho gajos, del de las doce en el sentido del reloj. `hijos` abre un
   * anillo aparte alrededor del gajo. */
  // Mike (9-sep-2026): «intercambia de posición Editar y Cuadrado».
  const RUEDA = [
    { et: "Línea",    icono: "╱",  cmd: "LINEA" },
    { et: "Círculo",  icono: "◯",  cmd: "CIRCULO" },
    { et: "Editar",   icono: "⧉",  hijos: [
        { et: "Espejear", icono: "⇋",  cmd: "ESPEJO" },
        { et: "Rotar",    icono: "↻",  cmd: "ROTAR" },
        { et: "Copiar",   icono: "⧉",  cmd: "COPIAR" },
        { et: "Escalar",  icono: "⤢",  cmd: "ESCALAR" },
        { et: "Borrar",   icono: "🗑", cmd: "BORRAR" },
      ] },
    { et: "Texto",    icono: "A",  cmd: "TEXTO" },
    // Los hijos van en abanico y **el de en medio es el que sale siguiendo
    // recto**: derecho, abajo, más abajo, soltar = cota recta.
    { et: "Cotas",    icono: "⊢⊣", hijos: [
        { et: "Alineada", icono: "⇗",  cmd: "COTAALINEADA" },
        { et: "Continua", icono: "⇹",  cmd: "COTACONTINUA" },
        { et: "Recta",    icono: "⊢⊣", cmd: "COTA" },
        { et: "Radio",    icono: "◠",  cmd: "COTARADIO" },
        { et: "Diámetro", icono: "⌀",  cmd: "COTADIAMETRO" },
      ] },
    { et: "Trimear",  icono: "✂",  cmd: "RECORTAR" },
    { et: "Mover",    icono: "✥",  cmd: "MOVER" },
    { et: "Cuadrado", icono: "▭",  cmd: "RECTANGULO" },
  ];

  const RADIO = 96;          // píxeles del centro a cada gajo
  const RADIO_HIJOS = 178;   // del centro de la rueda al anillo de hijos
  const ABANICO = 120;       // grados que abarca el anillo de hijos
  const ZONA_MUERTA = 18;    // cerca del centro no hay nada elegido
  // Cuánto hay que mover, con el botón apretado, para que salga la rueda.
  // Mike (9-sep-2026): «el radial sólo aplica si mientras está picado el
  // clic derecho el mouse se mueve más de X píxeles (creo que 2 es correcto…
  // probemos)». Soltar sin llegar a eso es el clic corto: propiedades sobre
  // una entidad, Enter en el vacío.
  const UMBRAL = 2;

  let inicio = null;         // {x, y, t} del clic derecho, antes de decidir
  let abierto = null;        // {caja, cx, cy, elegido, sub}

  /* --- Geometría de la rueda ------------------------------------------ */
  // El gajo i está en el ángulo i·(360/n), medido desde las doce en el sentido
  // del reloj. En pantalla la Y crece hacia abajo, así que las doce son -90°.
  const angDe = (i, n) => (-90 + i * (360 / n)) * Math.PI / 180;

  function gajoBajo(dx, dy, n, base = 0) {
    // `base`: ángulo (en grados, desde las doce) del primer hijo, para que el
    // anillo de hijos arranque donde apunta el padre.
    if (Math.hypot(dx, dy) < ZONA_MUERTA) return -1;
    let ang = Math.atan2(dy, dx) * 180 / Math.PI + 90 - base;   // 0 = doce
    ang = ((ang % 360) + 360) % 360;
    return Math.round(ang / (360 / n)) % n;
  }

  /* --- Pintado ---------------------------------------------------------- */
  function gajo(item, x, y, esHijo) {
    const b = document.createElement("div");
    b.className = "gajo" + (esHijo ? " hijo" : "") + (item.hijos ? " padre" : "");
    b.style.left = x + "px";
    b.style.top = y + "px";
    b.innerHTML = `<span class="ic"></span><span class="et"></span>`;
    b.querySelector(".ic").textContent = item.icono;
    b.querySelector(".et").textContent = item.et + (item.hijos ? " ▸" : "");
    return b;
  }

  /* --- La rueda del 3D  ·  Alt + clic derecho -------------------------------
   * Idea de Mike (16-sep): en vez de meterle un noveno gajo a la rueda de
   * siempre —que le movería el ángulo a los ocho que ya tiene aprendidos con
   * la mano—, el 3D tiene la suya. Mismo gesto, con Alt.
   *
   * Funciona igual estando en el dibujo o en la vista 3D: no hay que entrar al
   * 3D para levantar un contorno. */
  const RUEDA_3D = [
    { et: "Extruir",  icono: "⬒",  cmd: "EXTRUIR" },
    // El resto del grupo `model` cuelga de un gajo suyo: son hermanas de
    // Extruir —las cinco hacen un sólido de la nada— y así el gajo de Extruir
    // no se mueve del ángulo que la mano ya tiene aprendido.
    { et: "Model",    icono: "◆",  hijos: [
        { et: "Revolver", icono: "◕", cmd: "REVOLVER" },
        { et: "Barrer",   icono: "➟", cmd: "BARRER" },
        { et: "Loft",     icono: "⧉", cmd: "LOFT" },
        { et: "Crecer",   icono: "⬈", cmd: "CRECER" },
      ] },
    { et: "Ver 3D",   icono: "◳",  cmd: "3D" },
    { et: "Jalar",    icono: "↕",  cmd: "JALAR" },
    { et: "Orbitar",  icono: "⟳",  cmd: "ORBITAR" },
    { et: "Sacar",    icono: "⇪",  hijos: [
        { et: "STEP", icono: "S",  cmd: "STEP" },
        { et: "STL",  icono: "▲",  cmd: "STL" },
      ] },
  ];

  // Cuál de las dos ruedas está abierta. La elige `abrir` según el Alt.
  let rueda = RUEDA;

  function abrir(cx, cy) {
    rueda = (inicio && inicio.alt) ? RUEDA_3D : RUEDA;
    cerrar();
    const caja = document.createElement("div");
    caja.className = "radial";
    const centro = document.createElement("div");
    centro.className = "centro";
    centro.style.left = cx + "px";
    centro.style.top = cy + "px";
    caja.appendChild(centro);
    const gajos = rueda.map((item, i) => {
      const a = angDe(i, rueda.length);
      const g = gajo(item, cx + RADIO * Math.cos(a), cy + RADIO * Math.sin(a), false);
      caja.appendChild(g);
      return g;
    });
    document.body.appendChild(caja);
    abierto = { caja, cx, cy, gajos, elegido: -1, sub: null };
  }

  function abrirHijos(i) {
    const item = rueda[i];
    const angPadre = -90 + i * (360 / rueda.length);          // grados
    // Los hijos van en un anillo **más afuera**, en abanico centrado en la
    // dirección del padre: seguir recto cae en el de en medio, y los gajos
    // vecinos de la rueda no se tapan.
    const n = item.hijos.length;
    const abanico = Math.min(ABANICO, 30 * (n - 1));
    const paso = n > 1 ? abanico / (n - 1) : 0;
    const base = angPadre - abanico / 2;
    const gajos = item.hijos.map((h, k) => {
      const ang = (base + k * paso) * Math.PI / 180;
      const g = gajo(h, abierto.cx + RADIO_HIJOS * Math.cos(ang),
                     abierto.cy + RADIO_HIJOS * Math.sin(ang), true);
      abierto.caja.appendChild(g);
      return g;
    });
    abierto.sub = { padre: i, gajos, angPadre, paso, n, elegido: -1 };
    abierto.gajos[i].classList.add("abierto");
    abierto.caja.classList.add("con-hijos");
  }

  function cerrarHijos() {
    if (!abierto || !abierto.sub) return;
    for (const g of abierto.sub.gajos) g.remove();
    abierto.gajos[abierto.sub.padre].classList.remove("abierto");
    abierto.caja.classList.remove("con-hijos");
    abierto.sub = null;
  }

  function resaltar(lista, i) {
    lista.forEach((g, k) => g.classList.toggle("elegido", k === i));
  }

  /* --- Seguir al ratón -------------------------------------------------- */
  function mover(x, y) {
    if (!abierto) return;
    const sub = abierto.sub;
    if (sub) {
      // En el anillo de hijos manda el ángulo desde el centro de la rueda,
      // medido respecto al padre. Si el ratón vuelve hacia el centro, el
      // anillo se cierra y se sigue en la rueda.
      const dx = x - abierto.cx, dy = y - abierto.cy;
      if (Math.hypot(dx, dy) < RADIO * 0.7) {
        cerrarHijos(); resaltar(abierto.gajos, -1); abierto.elegido = -1; return;
      }
      let ang = Math.atan2(dy, dx) * 180 / Math.PI - sub.angPadre;
      ang = ((ang + 180) % 360 + 360) % 360 - 180;               // -180..180
      const mitad = (sub.n - 1) / 2;
      const k = sub.paso ? Math.round(ang / sub.paso + mitad) : 0;
      const dentro = Math.abs(ang) <= (sub.n - 1) / 2 * sub.paso + sub.paso / 2 + 8;
      sub.elegido = (dentro && k >= 0 && k < sub.n) ? k : -1;
      resaltar(sub.gajos, sub.elegido);
      return;
    }
    const i = gajoBajo(x - abierto.cx, y - abierto.cy, rueda.length);
    abierto.elegido = i;
    resaltar(abierto.gajos, i);
    // Con hijos: en cuanto el ratón pasa del gajo hacia afuera, se abren.
    if (i >= 0 && rueda[i].hijos && Math.hypot(x - abierto.cx, y - abierto.cy) > RADIO * 0.85) {
      abrirHijos(i);
      mover(x, y);
    }
  }

  function elegido() {
    if (!abierto) return null;
    if (abierto.sub) {
      const s = abierto.sub;
      return s.elegido >= 0 ? rueda[s.padre].hijos[s.elegido] : null;
    }
    const it = abierto.elegido >= 0 ? rueda[abierto.elegido] : null;
    return it && !it.hijos ? it : null;
  }

  function cerrar() {
    if (!abierto) return;
    abierto.caja.remove();
    abierto = null;
  }

  /* --- Los botones del ratón, desde vista.js ----------------------------- */
  function abajo(e) {
    inicio = { x: e.clientX, y: e.clientY, t: performance.now(), alt: e.shiftKey };   // Shift, no Alt (Mike, 18-sep)
  }

  function arrastre(e) {
    if (!inicio) return false;
    if (!abierto) {
      if (Math.hypot(e.clientX - inicio.x, e.clientY - inicio.y) < UMBRAL) return true;
      abrir(inicio.x, inicio.y);
    }
    mover(e.clientX, e.clientY);
    return true;
  }

  function arriba(e) {
    if (!inicio) return false;
    const habia = !!abierto;
    const item = elegido();
    cerrar();
    inicio = null;
    if (item) {
      Comandos.correr(item.cmd);
      return true;
    }
    if (habia) return true;            // se soltó en el vacío: nada
    // Clic derecho corto, sin mover, **sobre una entidad** y sin ningún
    // comando en curso: sus propiedades, ahí mismo (Mike, 9-sep-2026). «El
    // menú de propiedades no aparece hasta que no se suelta el clic, siempre y
    // cuando no se haya desplegado el radial antes.»
    if (window.PropsFlotante && !Comandos.corriendo && !Entrada.activa &&
        !Entrada.esperandoTexto && !Seleccion.pidiendo && estado.cursor) {
      const id = Seleccion.bajoElCursor([estado.cursor.x, estado.cursor.y]);
      if (id) { PropsFlotante.abrir(id, e.clientX, e.clientY); return true; }
    }
    // Clic derecho corto en el vacío: Enter. Confirma o termina lo que haya,
    // igual que en AutoCAD.
    $("#cmd").dispatchEvent(new KeyboardEvent("keydown",
      { key: "Enter", bubbles: false, cancelable: true }));
    return true;
  }

  function cancelar() {
    cerrar();
    inicio = null;
  }

  return { abajo, arrastre, arriba, cancelar, RUEDA, RUEDA_3D,
           get activo() { return !!abierto || !!inicio; } };
})();
window.Radial = Radial;
