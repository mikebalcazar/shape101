/* Variantes de cada herramienta  ·  clic derecho sobre el botón  ·  6-sep
 *
 * Mike: *«si das clic en una herramienta con el clic derecho, que se despliegue
 * un recuadrito con más herramientas derivadas de esa. Ej. Círculo: la base es
 * centro a radio, pero las secundarias podrían ser 2 puntos, 3 puntos, tangente
 * + diámetro… revisa en Rhino y AutoCAD cuáles son las más comunes»*.
 *
 * Es el «flyout» de AutoCAD y el botón con triangulito de Rhino. El botón corre
 * la variante base; el clic derecho abre las demás. Cada variante es **el mismo
 * comando con una opción** (CIRCULO 3P, ARCO CIF…), así que también se teclean,
 * y la consola enseña lo que se hizo. Lo que está aquí es lo que se ve en los
 * dos programas de referencia, sin las que nadie usa en un taller:
 *
 *   AutoCAD  CIRCLE: centro-radio, centro-diámetro, 2P, 3P, TTR, TTT
 *            ARC: 3P, inicio-centro-fin, inicio-centro-ángulo, inicio-fin-radio…
 *            RECTANG: esquinas, dimensiones, rotación · POLYGON
 *            ELLIPSE: ejes, centro · SPLINE: fit, CV
 *   Rhino    Circle: center-radius, 2pt, 3pt, tangent… · Rectangle: corner,
 *            center, 3 point · Line: from midpoint · Curve: control points,
 *            interpolate
 *
 * Las tangentes (TTR, TTT) no están todavía: necesitan resolver tangencias
 * contra lo que ya hay y son un comando aparte, no una opción.
 */

const Variantes = (() => {
  //: comando del botón → variantes. La primera es la base (la del clic normal).
  const TABLA = {
    LINEA: [
      { et: "Línea", cmd: "LINEA", ic: "╱", nota: "encadenadas · L" },
      { et: "Desde el punto medio", cmd: "LINEA", args: ["M"], ic: "┼", nota: "L M" },
    ],
    POLILINEA: [
      { et: "Polilínea", cmd: "POLILINEA", ic: "⌇", nota: "PL" },
      { et: "Polígono regular", cmd: "POLIGONO", ic: "⬡", nota: "POL · centro y vértice" },
    ],
    RECTANGULO: [
      { et: "Dos esquinas", cmd: "RECTANGULO", ic: "▭", nota: "REC" },
      { et: "Por el centro", cmd: "RECTANGULO", args: ["C"], ic: "⊡", nota: "REC C" },
      { et: "Por medidas", cmd: "RECTANGULO", args: ["M"], ic: "⧈", nota: "REC M · ancho y alto" },
      { et: "Tres puntos (girado)", cmd: "RECTANGULO", args: ["3P"], ic: "◊", nota: "REC 3P" },
    ],
    CIRCULO: [
      { et: "Centro y radio", cmd: "CIRCULO", ic: "◯", nota: "C" },
      { et: "Centro y diámetro", cmd: "CIRCULO", args: ["D"], ic: "⌀", nota: "C D" },
      { et: "Dos puntos (diámetro)", cmd: "CIRCULO", args: ["2P"], ic: "⊖", nota: "C 2P" },
      { et: "Tres puntos", cmd: "CIRCULO", args: ["3P"], ic: "⊙", nota: "C 3P" },
    ],
    ARCO: [
      { et: "Tres puntos", cmd: "ARCO", ic: "◜", nota: "A" },
      { et: "Centro, inicio, fin", cmd: "ARCO", args: ["CIF"], ic: "◠", nota: "A CIF" },
      { et: "Inicio, fin, radio", cmd: "ARCO", args: ["IFR"], ic: "⌒", nota: "A IFR" },
      { et: "Inicio, centro, ángulo", cmd: "ARCO", args: ["ICA"], ic: "∠", nota: "A ICA" },
    ],
    ELIPSE: [
      { et: "Centro y ejes", cmd: "ELIPSE", ic: "⬭", nota: "EL" },
      { et: "Por los extremos del eje", cmd: "ELIPSE", args: ["E"], ic: "⊜", nota: "EL E" },
    ],
    SPLINE: [
      { et: "Por puntos (pasa por ellos)", cmd: "SPLINE", ic: "∿", nota: "SPL" },
      { et: "Puntos de control (Bézier)", cmd: "SPLINE", args: ["CV"], ic: "⌁", nota: "SPL CV · curva orgánica" },
    ],
    // TEXTO ya no tiene variantes: un solo texto, de párrafo (0.20.0).
    PLANO: [
      { et: "Hoja nueva (todo el dibujo)", cmd: "PLANO", ic: "▤", nota: "PLANO" },
      { et: "Ventana a hoja (recuadrar)", cmd: "VENTANAHOJA", ic: "⧉", nota: "VH · lo que enmarques" },
    ],
    COTA: [
      { et: "Cota recta", cmd: "COTA", ic: "⊢⊣", nota: "CO_" },
      { et: "Alineada", cmd: "COTAALINEADA", ic: "⇗", nota: "CAL" },
      { et: "Encadenadas", cmd: "COTACONTINUA", ic: "⇹", nota: "CC" },
      { et: "Desde una base", cmd: "COTABASE", ic: "⊧", nota: "CB" },
    ],
    COPIAR: [
      { et: "Copiar", cmd: "COPIAR", ic: "⧉", nota: "CP" },
      { et: "Arreglo (matriz)", cmd: "ARREGLO", ic: "⋮⋮", nota: "AR · rectangular o polar" },
    ],
  };

  let caja = null;

  function cerrar() {
    if (!caja) return;
    caja.remove();
    caja = null;
    document.removeEventListener("mousedown", fuera, true);
    document.removeEventListener("keydown", tecla, true);
  }
  function fuera(e) { if (caja && !caja.contains(e.target)) cerrar(); }
  function tecla(e) { if (e.key === "Escape") { e.preventDefault(); cerrar(); } }

  /** Abrir el recuadro de variantes junto al botón. */
  function mostrar(boton) {
    const lista = TABLA[boton.dataset.cmd];
    cerrar();
    if (!lista) return false;
    caja = document.createElement("div");
    caja.className = "variantes";
    const hd = document.createElement("div");
    hd.className = "hd";
    hd.textContent = boton.title.split(" (")[0].split(" · ")[0];
    caja.appendChild(hd);
    for (const v of lista) {
      const b = document.createElement("button");
      b.className = "op";
      const ic = document.createElement("span"); ic.className = "ic"; ic.textContent = v.ic || "";
      const et = document.createElement("span"); et.className = "et"; et.textContent = v.et;
      const nt = document.createElement("span"); nt.className = "nt"; nt.textContent = v.nota || "";
      b.append(ic, et, nt);
      b.onclick = () => { cerrar(); Comandos.correr([v.cmd, ...(v.args || [])].join(" ")); };
      caja.appendChild(b);
    }
    document.body.appendChild(caja);
    // Junto al botón, hacia donde haya sitio.
    const r = boton.getBoundingClientRect();
    const w = caja.offsetWidth, h = caja.offsetHeight;
    let x = r.right + 6, y = r.top;
    if (x + w > window.innerWidth - 8) x = r.left - w - 6;
    if (x < 8) { x = r.left; y = r.bottom + 6; }
    if (y + h > window.innerHeight - 8) y = Math.max(8, window.innerHeight - 8 - h);
    caja.style.left = x + "px";
    caja.style.top = y + "px";
    setTimeout(() => {
      document.addEventListener("mousedown", fuera, true);
      document.addEventListener("keydown", tecla, true);
    }, 0);
    return true;
  }

  /** Marcar los botones que tienen variantes (el triangulito de la esquina). */
  function marcar() {
    for (const b of document.querySelectorAll("#herramientas button[data-cmd]")) {
      if (TABLA[b.dataset.cmd]) {
        b.classList.add("con-variantes");
        if (!/clic derecho/.test(b.title)) b.title += " · clic derecho: más formas";
      }
    }
  }

  return { TABLA, mostrar, cerrar, marcar, get abierto() { return !!caja; } };
})();
window.Variantes = Variantes;
