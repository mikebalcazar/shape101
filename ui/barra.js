/* Barra de herramientas movible  ·  shape101
 *
 * La barra se ancla a la izquierda, la derecha, arriba o abajo, o se queda
 * flotando donde la dejen. Los iconos **se reacomodan solos**: si anclada
 * arriba no caben a lo largo, se parten en dos filas; si está a un lado y no
 * caben a lo alto, en dos columnas.
 *
 * Cómo se mueve: se arrastra del asa. Mientras se arrastra, si se acerca a un
 * borde del lienzo, ese borde se ilumina y al soltar se ancla ahí. Si se suelta
 * en medio, se queda flotando. Doble clic en el asa la devuelve al último
 * anclaje.
 *
 * Dónde quedó se guarda en las **preferencias del usuario**, no en el
 * documento: dónde te gusta la barra es tuyo y no del plano, igual que la
 * rejilla y las referencias. Misma lección que el resto del programa.
 *
 * El reacomodo no se calcula a mano: es `flex-wrap`. Lo único que hace este
 * archivo es decidir la dirección y dejar que el navegador reparta. Contar
 * píxeles para partir filas es el tipo de código que se rompe con el primer
 * icono que se agregue.
 */

const Barra = (() => {
  const LADOS = ["izquierda", "derecha", "arriba", "abajo"];
  const IMAN = 64;          // a cuántos píxeles de un borde se ancla al soltar

  let nav, asa, guia;
  let ultimoAnclaje = "izquierda";
  let arrastrando = null;

  /* --- Estado ------------------------------------------------------------ */

  function estadoActual() {
    const anclaje = nav.dataset.anclaje || "flotante";
    const p = { anclaje };
    if (anclaje === "flotante") {
      p.x = parseInt(nav.style.left, 10) || 0;
      p.y = parseInt(nav.style.top, 10) || 0;
    }
    return p;
  }

  async function recordar() {
    try {
      await guardarPrefs({ barra: estadoActual() });
    } catch (_) { /* que no se pueda recordar no rompe nada */ }
  }

  function aplicar(p) {
    const anclaje = LADOS.includes(p && p.anclaje) ? p.anclaje : "flotante";
    nav.dataset.anclaje = anclaje;
    if (anclaje === "flotante") {
      const caja = document.getElementById("zona").getBoundingClientRect();
      // Que no se quede fuera de la ventana si la pantalla cambió de tamaño
      // entre sesiones: una barra invisible es una barra perdida.
      const x = Math.min(Math.max(0, p.x || 20), Math.max(0, caja.width - 60));
      const y = Math.min(Math.max(0, p.y || 20), Math.max(0, caja.height - 60));
      nav.style.left = x + "px";
      nav.style.top = y + "px";
    } else {
      ultimoAnclaje = anclaje;
      nav.style.left = nav.style.top = "";
    }
    // El lienzo cambió de tamaño: hay que volver a medirlo o el ratón deja de
    // caer donde se ve que cae. Ya pasó una vez, con el historial de comandos
    // que crecía y encogía el lienzo medio milímetro.
    if (typeof ajustarLienzo === "function") ajustarLienzo();
  }

  /* --- Arrastre ---------------------------------------------------------- */

  function ladoCercano(x, y) {
    const c = document.getElementById("zona").getBoundingClientRect();
    const d = {
      izquierda: x - c.left,
      derecha: c.right - x,
      arriba: y - c.top,
      abajo: c.bottom - y,
    };
    let mejor = null;
    for (const lado of LADOS) {
      if (d[lado] <= IMAN && (!mejor || d[lado] < d[mejor])) mejor = lado;
    }
    return mejor;
  }

  function pintarGuia(lado) {
    guia.className = lado ? "si " + lado : "";
  }

  function alBajar(e) {
    if (e.button !== 0) return;
    const r = nav.getBoundingClientRect();
    const c = document.getElementById("zona").getBoundingClientRect();
    arrastrando = { dx: e.clientX - r.left, dy: e.clientY - r.top, movido: false, c };
    // Pasa a flotante en cuanto se mueve de verdad, no al primer clic: un clic
    // sin arrastre no debería despegarla.
    asa.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function alMover(e) {
    if (!arrastrando) return;
    const a = arrastrando;
    if (!a.movido) {
      if (Math.abs(e.movementX) + Math.abs(e.movementY) < 2) return;
      a.movido = true;
      nav.dataset.anclaje = "flotante";
    }
    nav.style.left = (e.clientX - a.dx - a.c.left) + "px";
    nav.style.top = (e.clientY - a.dy - a.c.top) + "px";
    pintarGuia(ladoCercano(e.clientX, e.clientY));
  }

  function alSoltar(e) {
    if (!arrastrando) return;
    const movido = arrastrando.movido;
    arrastrando = null;
    pintarGuia(null);
    try { asa.releasePointerCapture(e.pointerId); } catch (_) { /* da igual */ }
    if (!movido) return;
    const lado = ladoCercano(e.clientX, e.clientY);
    aplicar(lado ? { anclaje: lado } : estadoActual());
    recordar();
  }

  /* --- Arranque ---------------------------------------------------------- */

  function conectar() {
    nav = document.getElementById("herramientas");
    asa = nav.querySelector(".asa");
    guia = document.createElement("div");
    guia.id = "guia-anclaje";
    document.getElementById("lienzo-caja").appendChild(guia);

    asa.addEventListener("pointerdown", alBajar);
    asa.addEventListener("pointermove", alMover);
    asa.addEventListener("pointerup", alSoltar);
    asa.addEventListener("pointercancel", alSoltar);
    asa.addEventListener("dblclick", () => {
      aplicar({ anclaje: ultimoAnclaje });
      recordar();
    });

    window.addEventListener("resize", () => {
      if (nav.dataset.anclaje === "flotante") aplicar(estadoActual());
    });
  }

  /** Lo llama app.js cuando llegan las preferencias del usuario. */
  function desdePrefs(prefs) {
    aplicar((prefs && prefs.barra) || { anclaje: "flotante", x: 12, y: 12 });
  }

  /** Manda la barra a un lado por comando. */
  function anclar(donde) {
    const d = String(donde || "").toLowerCase();
    const mapa = {
      i: "izquierda", izq: "izquierda", izquierda: "izquierda",
      d: "derecha", der: "derecha", derecha: "derecha",
      a: "arriba", arr: "arriba", arriba: "arriba",
      b: "abajo", ab: "abajo", abajo: "abajo",
      f: "flotante", flot: "flotante", flotante: "flotante",
    };
    const lado = mapa[d];
    if (!lado) return null;
    aplicar(lado === "flotante"
      ? { anclaje: "flotante", x: 24, y: 24 }
      : { anclaje: lado });
    recordar();
    return lado;
  }

  return { conectar, desdePrefs, anclar, get anclaje() { return nav.dataset.anclaje; } };
})();

Comandos.registrar({
  nombre: "BARRA", alias: ["BH"],
  ayuda: "BARRA [izquierda · derecha · arriba · abajo · flotante]",
  correr: async (args) => {
    let donde = args[0];
    if (!donde) {
      donde = await Entrada.pedirTexto({
        mensaje: "¿Dónde va la barra?",
        opciones: ["Izquierda", "Derecha", "Arriba", "Abajo", "Flotante"],
        omision: "Izquierda",
      });
    }
    const lado = Barra.anclar(donde);
    if (!lado) Comandos.eco(`No sé dónde es «${donde}».`, "malo");
    else Comandos.eco(`Barra de herramientas: ${lado}.`);
  },
});
