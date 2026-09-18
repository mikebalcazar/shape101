/* La cámara  ·  orbitar, y planta / frente / isométrica  ·  0.6.0
 *
 * El dibujo siempre estuvo en un espacio de tres dimensiones; lo que pasaba es
 * que sólo se miraba desde arriba. Aquí se le da al usuario el mando de esa
 * mirada.
 *
 * **Planta no es un modo, es un ángulo.** Con la cámara en cero se dibuja como
 * siempre, con la misma cuenta de siempre: nada de lo que ya funciona cambia.
 * Girarla no modifica el dibujo, modifica desde dónde se ve.
 *
 * Al orbitar se gira alrededor de **lo que se está mirando**, no del origen
 * del dibujo. Girar alrededor del origen manda la pieza fuera de la pantalla en
 * cuanto el dibujo está lejos del cero, que en un plano de taller es siempre.
 */

const Camara = (() => {
  const GRADO = Math.PI / 180;
  const VISTAS = {
    PLANTA: [0, 0],
    FRENTE: [-90 * GRADO, 0],
    DERECHA: [-90 * GRADO, -90 * GRADO],
    ISO: [-60 * GRADO, 45 * GRADO],
  };

  function lienzo() { return document.getElementById("lienzo"); }

  function repintar() {
    if (typeof invalidarPlano === "function") invalidarPlano();
    if (window.pintar) window.pintar();
  }

  /** Pone la cámara en unos ángulos **sin que se mueva de sitio lo que estás
   *  mirando**: se anota qué punto del plano está en el centro, se gira, y se
   *  vuelve a poner ese punto en el centro. Sin esto, cada giro manda el
   *  dibujo a otra parte y hay que encuadrar de nuevo cada vez. */
  function poner(rx, rz, pivote) {
    const el = lienzo();
    const v = estado.vista;
    const w = el ? el.clientWidth : 0, h = el ? el.clientHeight : 0;
    // El pivote: lo que está bajo el cursor al empezar (lo pasa `arrastrar`),
    // o el centro de la ventana activa. Ese punto se queda clavado en su sitio
    // de la pantalla mientras todo lo demás gira alrededor.
    const cx = (v.ox || 0) + (v.w || w) / 2, cy = (v.oy || 0) + (v.h || h) / 2;
    const centro = pivote || (window.aMM ? window.aMM(cx, cy) : null);
    const antes = centro && window.aPX ? window.aPX(centro[0], centro[1], 0) : null;
    v.rx = rx;
    v.rz = rz;
    if (antes) {
      const q = window.aPX(centro[0], centro[1], 0);
      // Ojo con el signo de la Y: en el dibujo crece hacia arriba y en la
      // pantalla hacia abajo, así que la corrección va al revés que la de X.
      v.x += (q[0] - antes[0]) / v.escala;
      v.y += (antes[1] - q[1]) / v.escala;
    }
    repintar();
  }

  function ver(nombre) {
    const a = VISTAS[String(nombre || "").toUpperCase()];
    if (!a) return false;
    poner(a[0], a[1]);
    return true;
  }

  function enPlanta() {
    return !estado.vista.rx && !estado.vista.rz;
  }

  // --- orbitar -------------------------------------------------------------
  let orbitando = null;

  function empezarAOrbitar() {
    const el = lienzo();
    if (!el || orbitando) return;
    Comandos.eco("Arrastra para girar. Escape o clic derecho para terminar.");
    el.style.cursor = "grab";

    const abajo = (e) => {
      if (e.button !== 0) return;
      orbitando.arrastre = { x: e.clientX, y: e.clientY, rx: estado.vista.rx, rz: estado.vista.rz };
      el.style.cursor = "grabbing";
      e.preventDefault();
      e.stopPropagation();
    };
    const mover = (e) => {
      const a = orbitando && orbitando.arrastre;
      if (!a) return;
      // Media pantalla ≈ media vuelta. Más rápido marea; más lento obliga a
      // arrastrar tres veces para ver la pieza por detrás.
      const rz = a.rz + (e.clientX - a.x) * 0.008;
      const rx = Math.max(-Math.PI / 2, Math.min(0, a.rx + (e.clientY - a.y) * 0.008));
      poner(rx, rz);
      e.preventDefault();
      e.stopPropagation();
    };
    const arriba = (e) => {
      if (orbitando) orbitando.arrastre = null;
      el.style.cursor = "grab";
      if (e && e.button === 2) terminar();
    };
    const tecla = (e) => { if (e.key === "Escape" || e.key === "Enter") terminar(); };

    orbitando = { arrastre: null, quitar: () => {
      el.removeEventListener("mousedown", abajo, true);
      window.removeEventListener("mousemove", mover, true);
      window.removeEventListener("mouseup", arriba, true);
      window.removeEventListener("keydown", tecla, true);
      el.style.cursor = "";
    } };
    // En captura, para ganarle a la selección y al pan: mientras se orbita, el
    // ratón es de la cámara y de nadie más.
    el.addEventListener("mousedown", abajo, true);
    window.addEventListener("mousemove", mover, true);
    window.addEventListener("mouseup", arriba, true);
    window.addEventListener("keydown", tecla, true);
  }

  function terminar() {
    if (!orbitando) return;
    orbitando.quitar();
    orbitando = null;
    Comandos.eco("cámara: " + (enPlanta() ? "planta" : `girada ${Math.round(estado.vista.rz / GRADO)}°`));
  }

  /** Orbitar arrastrando desde un botón del ratón, sin entrar en un modo:
   *  Alt + botón central, idea de Mike (17-sep). Se suelta el botón y se
   *  acabó. Lo llama el lienzo desde su propio mousedown. */
  function arrastrar(e) {
    const r = lienzo().getBoundingClientRect();
    // El pivote es lo que está bajo el cursor al apretar: es lo que la mano
    // espera que se quede quieto mientras gira lo demás.
    const pivote = window.aMM ? window.aMM(e.clientX - r.left, e.clientY - r.top) : null;
    const a = { x: e.clientX, y: e.clientY, rx: estado.vista.rx, rz: estado.vista.rz };
    const mover = (ev) => {
      poner(Math.max(-Math.PI / 2, Math.min(0, a.rx + (ev.clientY - a.y) * 0.008)),
            a.rz + (ev.clientX - a.x) * 0.008, pivote);
      ev.preventDefault();
      ev.stopPropagation();
    };
    const soltar = () => {
      window.removeEventListener("mousemove", mover, true);
      window.removeEventListener("mouseup", soltar, true);
    };
    window.addEventListener("mousemove", mover, true);
    window.addEventListener("mouseup", soltar, true);
  }

  return { poner, ver, enPlanta, empezarAOrbitar, terminar, arrastrar, VISTAS };
})();

window.Camara = Camara;

/* --- los comandos --------------------------------------------------------- */

Comandos.registrar({
  nombre: "ORBITAR", alias: ["ORBIT", "GIRAR3D"],
  ayuda: "Gira la vista arrastrando · Escape o clic derecho para terminar",
  correr: () => Camara.empezarAOrbitar(),
});

for (const [nombre, alias, ayuda] of [
  ["PLANTA", ["ARRIBA", "TOP"], "Mira el dibujo desde arriba, como siempre"],
  ["FRENTE", ["FRONT"], "Mira el dibujo de frente"],
  ["DERECHA", ["RIGHT"], "Mira el dibujo desde la derecha"],
  ["ISO", ["ISOMETRICA"], "Vista isométrica, para ver las piezas en volumen"],
]) {
  Comandos.registrar({
    nombre, alias, ayuda,
    correr: () => {
      Camara.ver(nombre);
      Comandos.eco(nombre === "PLANTA" ? "vista de planta: se dibuja como siempre" : `vista: ${nombre.toLowerCase()}`);
    },
  });
}
