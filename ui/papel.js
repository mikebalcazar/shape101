/* Espacio papel: hojas, ventanas e impresión  ·  features 60 a 68.
 *
 * La app tiene dos modos, como cualquier CAD: **modelo**, donde se dibuja a
 * tamaño real en milímetros, y **papel**, donde se arma la hoja que se va a
 * imprimir. Las pestañas de abajo cambian de uno a otro.
 *
 * La vista previa (feature 68) no es una imagen aparte: es la hoja pintada con
 * los mismos trazos que van al PDF, en el mismo lienzo. Lo que se ve es lo que
 * sale — literalmente el mismo arreglo de puntos.
 */

const Papel = (() => {
  let hoja = null;          // {ancho, alto, trazos, layout, indice}
  let logoImg = null;

  async function cargar(i) {
    hoja = await api(`/api/papel/${i}`);
    estado.papel = hoja;
    // Lo que se ve por las ventanas, en milímetros de papel, para poder
    // engancharse a ello al acotar sobre la hoja. Va aparte de
    // `estado.geometria` a propósito: se engancha, pero **no se selecciona**.
    // Lo que se ve por una ventana es el modelo mirado desde aquí y se edita
    // en el modelo, igual que en AutoCAD.
    estado.geometriaVentana = hoja.geometria_ventanas || [];
    return hoja;
  }

  /* Entrar a una hoja es **cambiar de espacio de dibujo**, no sólo de vista.
   *
   * Un CAD tiene dos espacios. En el modelo se dibuja el mueble a tamaño real;
   * en una hoja se dibuja sobre el papel, y lo que se pone ahí —una nota, un
   * símbolo, una viñeta— es de esa hoja y de ninguna otra.
   *
   * Hasta 0.13.1 entrar a una hoja sólo cambiaba lo que se pintaba: el motor
   * seguía creando todo en el modelo. Estando en la hoja, el clic daba
   * coordenadas de papel y la entidad se creaba en el modelo con esos números
   * — en un plano de obra, a cien metros del dibujo. Se trazaba y no aparecía
   * en ninguna parte. */
  async function cambiarEspacio(indice) {
    const d = await post("/api/espacio", { indice });
    estado.trazos = d.trazos || [];
    estado.geometria = d.geometria || [];
    if (estado.resumen) {
      estado.resumen.extension = d.extension;
      estado.resumen.espacio = d.espacio;
    }
    // El índice de selección se rehace solo: mira la identidad de los arreglos
    // y aquí se cambian los dos enteros. Ver `ui/indice.js`.
  }

  async function entrar(i) {
    estado.modo = "papel";
    estado.layoutActivo = i;
    Seleccion.limpiar();
    await cambiarEspacio(i);
    await cargar(i);
    encuadrarHoja();
    pintarPestanas();
  }

  async function salir() {
    estado.modo = "modelo";
    estado.papel = null;
    hoja = null;
    Seleccion.limpiar();
    await cambiarEspacio(null);
    pintarPestanas();
    invalidarPlano();
    encuadrar(false);
  }

  /** Encuadra la hoja completa en el lienzo, con un margen alrededor. */
  function encuadrarHoja() {
    if (!estado.papel) return;
    const ancho = lienzo.clientWidth, alto = lienzo.clientHeight;
    const escala = Math.min(ancho * 0.9 / estado.papel.ancho,
                            alto * 0.9 / estado.papel.alto);
    estado.vista.escala = escala;
    estado.vista.x = estado.papel.ancho / 2 - ancho / 2 / escala;
    estado.vista.y = estado.papel.alto / 2 + alto / 2 / escala;
    pintar();
  }

  /* --- Pestañas ---------------------------------------------------------- */
  async function pintarPestanas() {
    const caja = $("#pestanas");
    const { layouts } = await api("/api/layouts");
    estado.layouts = layouts;
    caja.innerHTML = "";

    const modelo = document.createElement("button");
    modelo.textContent = "Modelo";
    modelo.className = estado.modo === "modelo" ? "activa" : "";
    modelo.onclick = () => salir();
    caja.appendChild(modelo);

    layouts.forEach((L, i) => {
      const b = document.createElement("button");
      b.textContent = L.nombre;
      b.title = `${L.formato} · ${(L.ventanas || []).length} ventana(s)`;
      b.className = (estado.modo === "papel" && estado.layoutActivo === i) ? "activa" : "";
      b.onclick = () => entrar(i);
      caja.appendChild(b);
    });

    const mas = document.createElement("button");
    mas.textContent = "+";
    mas.className = "mas";
    mas.title = "Hoja nueva (PLANO)";
    mas.onclick = () => Comandos.correr("PLANO");
    caja.appendChild(mas);
  }

  /* --- Pintado de la hoja ------------------------------------------------ */
  function pintarHoja(ctx) {
    const h = estado.papel;
    if (!h) return;
    const css = getComputedStyle(document.documentElement);

    // el papel: blanco siempre, también en tema oscuro. El papel es blanco.
    const [x0, y0] = aPX(0, h.alto);
    const [x1, y1] = aPX(h.ancho, 0);
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,.28)";
    ctx.fillRect(x0 + 5, y0 + 5, x1 - x0, y1 - y0);      // sombrita
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    ctx.strokeStyle = css.getPropertyValue("--linea3").trim();
    ctx.lineWidth = 1;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);

    // Ventana arrastrada por dentro: sus trazos se pintan aparte, corridos
    // con el ratón y recortados a su marco (vista en vivo, 0.20.1).
    const corr = VentanasHoja.corrimiento();
    for (const t of h.trazos) {
      if (corr && t.ventana === corr.j && t.id !== "ventana") continue;
      pintarTrazoHoja(ctx, t, 0, 0);
    }
    if (corr) {
      const v = corr.v;
      const [cx0, cy1] = aPX(v.x, v.y + v.alto);
      const [cx1, cy0] = aPX(v.x + v.ancho, v.y);
      ctx.save();
      ctx.beginPath();
      ctx.rect(cx0, cy0, cx1 - cx0, cy1 - cy0);
      ctx.clip();
      // Mientras llega la previa ensanchada se corre lo que ya había.
      const lote = corr.previa || h.trazos.filter((t) => t.ventana === corr.j && t.id !== "ventana");
      for (const t of lote) pintarTrazoHoja(ctx, t, corr.dx, corr.dy);
      ctx.restore();
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  /** Un trazo de la hoja, corrido `dx, dy` mm de papel. */
  function pintarTrazoHoja(ctx, t, dx, dy) {
    const P = (x, y) => aPX(x + dx, y + dy);
    if (t.clase === "imagen") {
      // El logotipo: la vista previa carga el mismo PNG que la app enseña en
      // la barra, para que se vea aquí lo que va a salir impreso.
      if (!logoImg) {
        logoImg = new Image();
        logoImg.onload = () => pintar();
        logoImg.src = "vendor/marca/logo.png";
      }
      if (logoImg.complete && logoImg.naturalWidth) {
        const anchoPX = t.ancho * estado.vista.escala;
        const altoPX = anchoPX * logoImg.naturalHeight / logoImg.naturalWidth;
        const [px, py] = P(t.p[0], t.p[1]);
        ctx.drawImage(logoImg, px, py - altoPX, anchoPX, altoPX);
      }
      return;
    }
    ctx.strokeStyle = t.color || "#000";
    ctx.fillStyle = t.color || "#000";
    if (t.clase === "relleno") {
      ctx.beginPath();
      for (const pol of t.poligonos || []) {
        for (let i = 0; i < pol.length; i++) {
          const [px, py] = P(pol[i][0], pol[i][1]);
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.closePath();
      }
      ctx.fill("evenodd");
      return;
    }
    if (t.clase === "texto") {
      const alturaPX = t.altura * estado.vista.escala;
      if (alturaPX < 3.5) return;
      const [px, py] = P(t.p[0], t.p[1]);
      ctx.save();
      ctx.translate(px, py);
      if (t.rotacion) ctx.rotate(-t.rotacion * Math.PI / 180);
      ctx.font = `${alturaPX}px Cifras, Raleway, sans-serif`;
      ctx.textAlign = t.alineacion === "CENTRO" ? "center"
        : t.alineacion === "DER" ? "right" : "left";
      ctx.fillText(String(t.texto), 0, 0);
      ctx.restore();
      return;
    }
    const pts = t.puntos || [];
    if (pts.length < 2) return;
    ctx.lineWidth = Math.max(0.7, (t.grosor || 0.25) * estado.vista.escala);
    ctx.setLineDash(t.imprime === false ? [4, 3] : []);
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const [px, py] = P(pts[i][0], pts[i][1]);
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  /* --- Editar el pie de plano encima de la hoja  ·  6-sep-2026 ------------
   *
   * Mike: *«modificar los datos de la hoja directo sobre la hoja, con doble
   * clic, como si editara texto, pero sólo se puede editar el texto. No se
   * puede mover ni de tamaño ni de ubicación»*.
   *
   * El motor manda con la hoja la caja de cada dato (`campos`, ver
   * core/papel.py). Doble clic dentro de una → una cajita de texto encima,
   * del tamaño del dato; Enter o clic fuera guardan, Esc deja como estaba.
   * Se guarda en el layout y la hoja se rehace: lo que dice el cuadro PLANO y
   * lo que se ve impreso son el mismo dato. */
  function campoEn(x, y) {
    const h = estado.papel;
    if (!h || !h.campos) return null;
    return h.campos.find((c) => x >= c.caja[0] && x <= c.caja[2] && y >= c.caja[1] && y <= c.caja[3]) || null;
  }

  let editor = null;

  /* La escala del pie se elige de una lista, no se teclea con sus «:».
   * Mike (9-sep-2026): «que se edite como escalas predeterminadas, como
   * swatch de escala a escoger». Las de `papel.ESCALAS`, más la actual si no
   * está, y «Otra…» para teclear una a la medida. */
  const ESCALAS_HOJA = [1, 2, 5, 10, 20, 25, 50, 75, 100, 200];
  function opcionesEscala(actual) {
    const lista = [...ESCALAS_HOJA];
    if (actual && !lista.includes(actual)) { lista.push(actual); lista.sort((a, b) => a - b); }
    return lista;
  }

  function editarEscala(campo, i, px0, py0, px1, py1) {
    const v = (estado.papel.layout.ventanas || [])[0] || {};
    const actual = v.escala || 20;
    const sel = document.createElement("select");
    sel.className = "campo-hoja";
    sel.title = `${campo.etiqueta} · Esc cancela`;
    for (const e of opcionesEscala(actual)) {
      const o = document.createElement("option"); o.value = String(e); o.textContent = `1:${mm(e)}`;
      sel.appendChild(o);
    }
    const otra = document.createElement("option"); otra.value = "otra"; otra.textContent = Tr("Otra…");
    sel.appendChild(otra);
    sel.value = String(actual);
    sel.style.left = Math.round(px0) + "px";
    sel.style.top = Math.round(py0) + "px";
    sel.style.width = Math.max(90, Math.round(px1 - px0)) + "px";
    sel.style.height = Math.max(22, Math.round(py1 - py0)) + "px";
    sel.style.fontSize = Math.max(11, Math.min(16, Math.round((py1 - py0) * 0.28))) + "px";
    $("#lienzo-caja").appendChild(sel);
    sel.focus();
    let cerrado = false;
    const aplicar = async (esc) => {
      if (cerrado) return;
      cerrado = true; editor = null; sel.remove();
      if (!esc || esc === actual) return;
      await patch(`/api/layout/${i}`, { cambios: { rotulo: { escala: "" } } });
      await aplicarEscalaVentanas(i, esc);
      await cargar(i);
      await pintarPestanas();
      pintar();
      Comandos.eco(`Escala de la hoja: 1:${mm(esc)}. La ventana se dibujó a esa escala.`, "bien");
    };
    sel.addEventListener("change", async () => {
      if (sel.value === "otra") {
        // A la medida: se teclea el número (1:37 no, pero 1:30 sí puede hacer falta).
        cerrado = true; editor = null; sel.remove();
        try {
          const n = await Entrada.pedirNumero({ mensaje: "Escala 1:?", valor: actual, minimo: 0.01, recordar: false });
          cerrado = false; await aplicar(n);
        } catch (_) { /* cancelado */ }
        return;
      }
      aplicar(parseFloat(sel.value));
    });
    sel.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); cerrado = true; editor = null; sel.remove(); }
      else if (e.key === "Enter") { e.preventDefault(); sel.dispatchEvent(new Event("change")); }
      e.stopPropagation();
    });
    sel.addEventListener("keyup", (e) => e.stopPropagation());
    sel.addEventListener("blur", () => { if (!cerrado) { cerrado = true; editor = null; sel.remove(); } });
    editor = { cerrar: () => { cerrado = true; editor = null; sel.remove(); }, campo };
  }

  function editarCampo(campo) {
    if (editor) editor.cerrar(false);
    const i = estado.layoutActivo;
    const [px0, py0] = aPX(campo.caja[0], campo.caja[3]);
    const [px1, py1] = aPX(campo.caja[2], campo.caja[1]);
    if (campo.clave === "escala") return editarEscala(campo, i, px0, py0, px1, py1);
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "campo-hoja";
    inp.value = campo.valor || "";
    inp.placeholder = campo.etiqueta;
    inp.title = `${campo.etiqueta} · Enter guarda · Esc cancela · vacío = automático`;
    inp.spellcheck = false;
    inp.style.left = Math.round(px0) + "px";
    inp.style.top = Math.round(py0) + "px";
    inp.style.width = Math.max(60, Math.round(px1 - px0)) + "px";
    inp.style.height = Math.max(22, Math.round(py1 - py0)) + "px";
    inp.style.fontSize = Math.max(11, Math.min(16, Math.round((py1 - py0) * 0.28))) + "px";
    $("#lienzo-caja").appendChild(inp);
    inp.focus();
    inp.select();
    let cerrado = false;
    const cerrar = async (guardar) => {
      if (cerrado) return;
      cerrado = true;
      editor = null;
      const valor = inp.value.trim();
      inp.remove();
      if (!guardar || valor === (campo.valor || "")) return;
      const esc = campo.clave === "escala" ? escalaEscrita(valor) : null;
      if (esc) {
        // Lo escrito en el pie manda: la ventana se pone a esa escala y el
        // rótulo vuelve a escribirla solo (por eso se guarda vacío).
        await patch(`/api/layout/${i}`, { cambios: { rotulo: { escala: "" } } });
        await aplicarEscalaVentanas(i, esc);
      } else {
        await patch(`/api/layout/${i}`, { cambios: { rotulo: { [campo.clave]: valor } } });
      }
      await cargar(i);
      await pintarPestanas();
      pintar();
      Comandos.eco(esc ? `Escala de la hoja: 1:${esc}. La ventana se dibujó a esa escala.` : `${campo.etiqueta}: ${valor || "(automático)"}`, "bien");
    };
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); cerrar(true); }
      else if (e.key === "Escape") { e.preventDefault(); cerrar(false); }
      e.stopPropagation();
    });
    inp.addEventListener("keyup", (e) => e.stopPropagation());
    inp.addEventListener("blur", () => cerrar(true));
    editor = { cerrar, campo };
  }

  return { entrar, salir, cargar, pintarHoja, pintarPestanas, encuadrarHoja,
           campoEn, editarCampo, opcionesEscala,
           get hoja() { return hoja; }, get editando() { return !!editor; } };
})();

/* ===================================================================== */
/* Editar las ventanas con el ratón  ·  0.20.0                            */
/* ===================================================================== */
/* Mike (9-sep-2026): «arriba una herramienta/ícono para editar viewport, y
 * se activen handles de los viewports disponibles. Siempre serán un
 * rectángulo: si arrastro una esquina, modifica el tamaño; si lo agarro del
 * handle del midpoint, aumenta ancho o alto; si lo arrastro de algún otro
 * punto del cuadro, lo muevo. Si arrastro en el interior, sólo puedo arrastrar
 * la ubicación del dibujo dentro del viewport, no lo puedo editar ni hacer
 * zoom: eso se hace con la escala directo en el pie de plano».
 *
 * Es un **modo** (EDITARVENTANA, o el botón de la barra): mientras está
 * encendido, cada ventana enseña sus ocho handles y el ratón los agarra; se
 * apaga con Esc, con Enter o volviendo a apretar el botón. Lo que se arrastra
 * se ve en la capa de encima; al soltar se manda al motor y la hoja se rehace. */
const VentanasHoja = (() => {
  let activo = false;
  let arrastre = null;          // {j, tipo, cual, origen:[x,y], v0:{…}}
  let sobre = null;             // {j, tipo, cual} bajo el cursor, para el cursor del ratón
  const HANDLE_PX = 7;

  const ventanas = () => (estado.modo === "papel" && estado.papel && estado.papel.layout && estado.papel.layout.ventanas) || [];

  function handles(v) {
    const x0 = v.x, y0 = v.y, x1 = v.x + v.ancho, y1 = v.y + v.alto, xm = (x0 + x1) / 2, ym = (y0 + y1) / 2;
    return [
      { tipo: "esquina", cual: "sw", p: [x0, y0] }, { tipo: "esquina", cual: "se", p: [x1, y0] },
      { tipo: "esquina", cual: "ne", p: [x1, y1] }, { tipo: "esquina", cual: "nw", p: [x0, y1] },
      { tipo: "lado", cual: "s", p: [xm, y0] }, { tipo: "lado", cual: "e", p: [x1, ym] },
      { tipo: "lado", cual: "n", p: [xm, y1] }, { tipo: "lado", cual: "w", p: [x0, ym] },
    ];
  }

  /** Qué hay bajo el punto (en mm de papel): un handle, el marco, el interior. */
  function bajo(p) {
    const vs = ventanas();
    const tol = HANDLE_PX / estado.vista.escala;
    for (let j = vs.length - 1; j >= 0; j--) {
      for (const h of handles(vs[j])) {
        if (Math.abs(h.p[0] - p[0]) <= tol && Math.abs(h.p[1] - p[1]) <= tol) return { j, ...h };
      }
    }
    for (let j = vs.length - 1; j >= 0; j--) {
      const v = vs[j];
      const x0 = v.x, y0 = v.y, x1 = v.x + v.ancho, y1 = v.y + v.alto;
      const cercaX = Math.abs(p[0] - x0) <= tol || Math.abs(p[0] - x1) <= tol;
      const cercaY = Math.abs(p[1] - y0) <= tol || Math.abs(p[1] - y1) <= tol;
      const enX = p[0] >= x0 - tol && p[0] <= x1 + tol, enY = p[1] >= y0 - tol && p[1] <= y1 + tol;
      if ((cercaX && enY) || (cercaY && enX)) return { j, tipo: "marco" };
      if (p[0] > x0 && p[0] < x1 && p[1] > y0 && p[1] < y1) return { j, tipo: "interior" };
    }
    return null;
  }

  const CURSORES = { esquina: { sw: "nesw-resize", ne: "nesw-resize", se: "nwse-resize", nw: "nwse-resize" },
                     lado: { n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize" },
                     marco: "move", interior: "grab" };

  function cursorDe(h) {
    if (!h) return "default";
    const c = CURSORES[h.tipo];
    return typeof c === "string" ? c : (c && c[h.cual]) || "default";
  }

  function activar(si) {
    activo = !!si;
    arrastre = null;
    sobre = null;
    const b = document.querySelector('#herramientas button[data-cmd="EDITARVENTANA"]');
    if (b) b.classList.toggle("activo", activo);
    lienzo.style.cursor = activo ? "default" : "";
    if (activo) Comandos.pedir(Tr("Arrastra las esquinas, los lados o el marco de la ventana; el interior mueve el dibujo. Esc termina"));
    else Comandos.terminar();
    pintar();
  }

  function clicAbajo(p) {
    if (!activo || estado.modo !== "papel") return false;
    const h = bajo(p);
    if (!h) return true;                      // en el vacío no hace nada (y no selecciona)
    const v = ventanas()[h.j];
    arrastre = { ...h, origen: p, v0: { x: v.x, y: v.y, ancho: v.ancho, alto: v.alto, centro: v.centro.slice(), escala: v.escala },
                 previa: null, dx: 0, dy: 0 };
    lienzo.style.cursor = h.tipo === "interior" ? "grabbing" : cursorDe(h);
    if (h.tipo === "interior") pedirPrevia(arrastre);
    return true;
  }

  /* La vista en vivo al correr el dibujo (Mike, 9-sep-2026: «si lo quiero
   * mover ahorita, lo muevo a ciegas»). Al agarrar el interior se pide al
   * motor lo que la ventana vería alrededor de su encuadre —la misma ventana
   * ensanchada— y el lienzo lo corre con el ratón, recortado al marco. Si el
   * arrastre terminó antes de que llegue, se tira. */
  async function pedirPrevia(a) {
    try {
      const d = await api(`/api/layout/${estado.layoutActivo}/ventana/${a.j}/previa`);
      if (arrastre === a) { a.previa = d.trazos || []; pintar(); }
    } catch (e) { /* sin previa se corre lo que ya había en la ventana */ }
  }

  /** Cuánto va corrido el dibujo de la ventana que se arrastra por dentro. */
  function corrimiento() {
    if (!arrastre || arrastre.tipo !== "interior") return null;
    const v = ventanas()[arrastre.j];
    return v ? { j: arrastre.j, v, dx: arrastre.dx, dy: arrastre.dy, previa: arrastre.previa } : null;
  }

  function alMover(p) {
    if (!activo || estado.modo !== "papel") return false;
    if (!arrastre) {
      const h = bajo(p);
      const llave = h ? `${h.j}|${h.tipo}|${h.cual || ""}` : "";
      if (llave !== (sobre && sobre.llave)) {
        sobre = h ? { ...h, llave } : null;
        lienzo.style.cursor = cursorDe(h);
        pintar();
      }
      return true;
    }
    const v = ventanas()[arrastre.j];
    const v0 = arrastre.v0;
    const dx = p[0] - arrastre.origen[0], dy = p[1] - arrastre.origen[1];
    const MIN = 20;
    if (arrastre.tipo === "marco") {
      v.x = v0.x + dx; v.y = v0.y + dy;
    } else if (arrastre.tipo === "interior") {
      // El dibujo se corre dentro de la ventana: el centro va al revés del
      // arrastre, en unidades del modelo (mm de papel × escala / k).
      const f = (v0.escala || 20) / mmPorUnidad();
      v.centro = [v0.centro[0] - dx * f, v0.centro[1] - dy * f];
      arrastre.dx = dx; arrastre.dy = dy;
    } else {
      const c = arrastre.cual;
      let x0 = v0.x, y0 = v0.y, x1 = v0.x + v0.ancho, y1 = v0.y + v0.alto;
      if (c.includes("w")) x0 = Math.min(v0.x + dx, x1 - MIN);
      if (c.includes("e")) x1 = Math.max(v0.x + v0.ancho + dx, x0 + MIN);
      if (c.includes("s")) y0 = Math.min(v0.y + dy, y1 - MIN);
      if (c.includes("n")) y1 = Math.max(v0.y + v0.alto + dy, y0 + MIN);
      v.x = x0; v.y = y0; v.ancho = x1 - x0; v.alto = y1 - y0;
    }
    estado.hule = null;
    if (arrastre.tipo === "interior") invalidarPlano();     // la hoja se repinta corrida
    pintar();
    return true;
  }

  async function clicArriba(p) {
    if (!activo || !arrastre) return false;
    const a = arrastre;
    arrastre = null;
    estado.hule = null;
    const v = ventanas()[a.j];
    const i = estado.layoutActivo;
    const cambios = a.tipo === "interior" ? { centro: v.centro }
      : { x: v.x, y: v.y, ancho: v.ancho, alto: v.alto };
    const igual = a.tipo === "interior"
      ? Math.hypot(v.centro[0] - a.v0.centro[0], v.centro[1] - a.v0.centro[1]) < 1e-9
      : (v.x === a.v0.x && v.y === a.v0.y && v.ancho === a.v0.ancho && v.alto === a.v0.alto);
    lienzo.style.cursor = cursorDe(bajo(p));
    invalidarPlano();                          // la hoja corrida en vivo ya no vale
    if (igual) { pintar(); return true; }
    try {
      await patch(`/api/layout/${i}/ventana/${a.j}`, { cambios });
      await Papel.cargar(i);
      if (a.tipo !== "interior") Comandos.eco(`${Tr("Ventana")} ${a.j + 1}: ${mm(v.ancho)} × ${mm(v.alto)} mm ${Tr("en")} (${mm(v.x)}, ${mm(v.y)}).`);
    } catch (e) { avisar(e.message, true); }
    pintar();
    return true;
  }

  /** Los marcos y los handles, en la capa de encima. */
  function pintarEncima(c) {
    if (!activo || estado.modo !== "papel") return;
    const T = tema();
    c.save();
    ventanas().forEach((v, j) => {
      const [x0, y1] = aPX(v.x, v.y + v.alto);
      const [x1, y0] = aPX(v.x + v.ancho, v.y);
      const resaltada = (arrastre && arrastre.j === j) || (sobre && sobre.j === j);
      c.strokeStyle = T.acc2;
      c.lineWidth = resaltada ? 2 : 1.2;
      c.setLineDash(arrastre && arrastre.j === j ? [6, 4] : []);
      c.strokeRect(x0, y0, x1 - x0, y1 - y0);
      c.setLineDash([]);
      c.fillStyle = T.panel;
      for (const h of handles(v)) {
        const [px, py] = aPX(h.p[0], h.p[1]);
        const s = h.tipo === "esquina" ? 4 : 3.5;
        c.beginPath();
        if (h.tipo === "esquina") c.rect(px - s, py - s, 2 * s, 2 * s);
        else c.arc(px, py, s, 0, Math.PI * 2);
        c.fill(); c.stroke();
      }
      c.fillStyle = T.acc2;
      c.font = "600 11px Cifras, Raleway, sans-serif";
      c.fillText(`${Tr("Ventana")} ${j + 1} · 1:${mm(v.escala)}`, x0 + 6, y0 + 14);
    });
    c.restore();
  }

  return { activar, clicAbajo, alMover, clicArriba, pintarEncima, bajo, handles, corrimiento,
           get activo() { return activo; }, get arrastrando() { return !!arrastre; } };
})();
window.VentanasHoja = VentanasHoja;

/* ===================================================================== */
/* Comandos de papel                                                      */
/* ===================================================================== */

/* --- La hoja, en un cuadro  ·  punto 7 ---------------------------------
 *
 * Mike: *«hacer más amigable la creación de planos/hojas, no en la línea de
 * comandos»*. Antes esto eran nueve preguntas seguidas —formato, nombre y los
 * siete campos del pie— sin poder ver lo contestado ni corregir hacia atrás.
 *
 * El mismo cuadro sirve para crear y para editar: son los mismos datos, y
 * tener dos formularios distintos para lo mismo es cómo se acaba con uno de
 * los dos desactualizado. */

const FORMATOS_ET = {
  A4: "A4 · 297 × 210", A3: "A3 · 420 × 297", A2: "A2 · 594 × 420",
  A1: "A1 · 841 × 594", A0: "A0 · 1189 × 841",
  CARTA: "Carta · 279 × 216", TABLOIDE: "Tabloide · 432 × 279",
  CUSTOM: "A la medida…",
};

/* «1:50», «1 : 50», «1/50» o «50» → 50. Lo que no se entienda → null.
 * Mike (8-sep): lo escrito en la hoja manda sobre la escala dibujada. */
function escalaEscrita(texto) {
  const t = String(texto || "").trim().replace(",", ".");
  const m = t.match(/^1\s*[:/]\s*(\d+(?:\.\d+)?)$/) || t.match(/^(\d+(?:\.\d+)?)$/);
  if (!m) return null;
  const n = parseFloat(m[1]);
  return n > 0 ? n : null;
}

async function aplicarEscalaVentanas(indice, escala) {
  const L = (estado.layouts || [])[indice] || (estado.papel && estado.papel.layout) || {};
  const n = (L.ventanas || []).length || 1;
  for (let j = 0; j < n; j++) {
    await patch(`/api/layout/${indice}/ventana/${j}`, { cambios: { escala } });
  }
}

async function cuadroDeHoja(L, indice, { caja = null } = {}) {
  const nueva = indice == null;
  const { escalas } = await api("/api/layouts");
  const r = (L && L.rotulo) || {};
  const v = (L && (L.ventanas || [])[0]) || {};
  const hoy = new Date().toISOString().slice(0, 10);

  const datos = await Dialogo.abrir({
    titulo: nueva ? "Hoja nueva" : `Hoja «${L.nombre}»`,
    pista: nueva
      ? "Se crea con una ventana ya encuadrada sobre el dibujo."
      : "Lo que se deje en blanco lo rellena el plano solo: cliente, fecha y escala.",
    ancho: "500px",
    campos: [
      { clave: "nombre", etiqueta: "Nombre de la hoja", tipo: "texto",
        valor: (L && L.nombre) || Tr(`Plano ${(estado.layouts || []).length + 1}`) },
      { clave: "formato", etiqueta: "Formato", tipo: "lista",
        valor: (L && L.formato) || "A3",
        opciones: Object.entries(FORMATOS_ET) },
      { clave: "ancho", etiqueta: "Ancho del papel", tipo: "numero", sufijo: "mm",
        valor: (L && L.ancho) || 420, visible: (x) => x.formato === "CUSTOM" },
      { clave: "alto", etiqueta: "Alto del papel", tipo: "numero", sufijo: "mm",
        valor: (L && L.alto) || 297, visible: (x) => x.formato === "CUSTOM" },
      // La escala se elige de la lista (Mike, 9-sep: sin teclear los «:»);
      // «Otra…» abre un campo para una a la medida.
      ...(nueva ? [] : [{ clave: "escala", etiqueta: "Escala de la ventana", tipo: "lista",
        valor: String(v.escala || 20),
        opciones: [...Papel.opcionesEscala(v.escala || 20).map((e) => [String(e), `1:${mm(e)}`]), ["otra", Tr("Otra…")]],
        pista: Tr("El rótulo escribe esta escala solo.") },
        { clave: "escala_otra", etiqueta: "Escala 1:?", tipo: "numero", valor: v.escala || 20,
          visible: (x) => x.escala === "otra" }]),
      { clave: "unidades", etiqueta: "Unidades del dibujo", tipo: "lista", valor: U(),
        opciones: [["mm", "mm — " + Tr("milímetros")], ["cm", "cm — " + Tr("centímetros")], ["m", "m — " + Tr("metros")]],
        pista: "Cambiarla escala lo dibujado para conservar su tamaño real (UNIDADES)." },
      // Mike (9-sep-2026): «cada página de plano tiene su propio tamaño de
      // cota». La altura del texto de cota en mm de papel, para esta hoja.
      { clave: "tam_cotas", etiqueta: "Tamaño de cotas", tipo: "numero", sufijo: "mm en papel",
        valor: (L && L.tam_cotas) || ((estado.resumen && estado.resumen.estilo_cota) || {}).altura_texto || 2.5,
        pista: "Altura del texto de las cotas en esta hoja. Cada hoja tiene el suyo; el modelo no cambia." },
      { clave: "_t", etiqueta: "Pie de plano", tipo: "titulo" },
      { clave: "proyecto", etiqueta: "Proyecto", tipo: "texto", valor: r.proyecto || "" },
      { clave: "cliente", etiqueta: "Cliente", tipo: "texto", valor: r.cliente || "",
        marcador: estado.resumen.cliente || "— el del dibujo —" },
      { clave: "dibujo", etiqueta: "Dibujo", tipo: "texto", valor: r.dibujo || "",
        marcador: estado.resumen.nombre || "" },
      { clave: "dibujo_por", etiqueta: "Dibujó", tipo: "texto", valor: r.dibujo_por || "" },
      { clave: "folio", etiqueta: "Folio", tipo: "texto", valor: r.folio || "1/1" },
      { clave: "revision", etiqueta: "Revisión", tipo: "texto", valor: r.revision || "A" },
      { clave: "fecha", etiqueta: "Fecha", tipo: "texto", valor: r.fecha || "",
        marcador: hoy },
    ],
    aceptar: nueva ? "Crear la hoja" : "Guardar",
    extra: nueva ? null : { etiqueta: "Centrar el dibujo", accion: async () => {
      await patch(`/api/layout/${indice}/ventana/0`, { cambios: { centrar: true } });
      await Papel.cargar(indice);
      pintar();
      Comandos.eco("El dibujo quedó centrado en la ventana.", "bien");
    } },
    validar: (x) => {
      if (!String(x.nombre).trim()) return "La hoja necesita un nombre.";
      if (x.escala === "otra" && !(x.escala_otra > 0)) return "La escala tiene que ser mayor que cero.";
      if (!(x.tam_cotas > 0)) return "El tamaño de cotas tiene que ser mayor que cero.";
      if (x.formato === "CUSTOM" && (!(x.ancho >= 50 && x.ancho <= 5000) ||
                                     !(x.alto >= 50 && x.alto <= 5000))) {
        return "A la medida: entre 50 y 5000 mm por lado.";
      }
      return null;
    },
  });
  if (!datos) return null;

  const rotulo = {};
  for (const k of ["proyecto", "cliente", "dibujo", "dibujo_por", "folio",
                   "revision", "fecha"]) rotulo[k] = datos[k];

  if (nueva) {
    if (datos.unidades && datos.unidades !== U()) await Ajustes.unidades([datos.unidades]);
    // `caja`: el recuadro del modelo que debe enseñar la ventana (VENTANAHOJA).
    const res = await post("/api/layout", { nombre: datos.nombre, formato: datos.formato, caja });
    const i = res.indice;
    await patch(`/api/layout/${i}`, {
      cambios: { rotulo, ancho: datos.ancho, alto: datos.alto,
                 formato: datos.formato, tam_cotas: datos.tam_cotas },
    });
    await Papel.entrar(i);
    Comandos.eco(`Hoja «${datos.nombre}» en ${datos.formato}, ${caja ? "con la ventana sobre el recuadro elegido" : "encuadrada sobre el dibujo"}.`, "bien");
    return i;
  }

  await patch(`/api/layout/${indice}`, {
    cambios: { nombre: datos.nombre, formato: datos.formato,
               ancho: datos.ancho, alto: datos.alto, rotulo, tam_cotas: datos.tam_cotas },
  });
  const escNueva = datos.escala === "otra" ? parseFloat(datos.escala_otra) : parseFloat(datos.escala);
  if (escNueva > 0 && Math.abs(escNueva - (v.escala || 20)) > 1e-9) {
    await patch(`/api/layout/${indice}`, { cambios: { rotulo: { escala: "" } } });
    await aplicarEscalaVentanas(indice, escNueva);
  }
  if (datos.unidades && datos.unidades !== U()) await Ajustes.unidades([datos.unidades]);
  await Papel.cargar(indice);
  await Papel.pintarPestanas();
  pintar();
  Comandos.eco("Hoja actualizada.", "bien");
  return indice;
}

Comandos.registrar({
  nombre: "PLANO", alias: ["HOJA", "LAYOUT"],
  ayuda: "Hoja nueva, o edita la hoja abierta, en un cuadro",
  correr: async (args) => {
    // Con un formato por argumento se salta el cuadro: `PLANO A2` sigue
    // funcionando para quien ya se sabe el atajo.
    const arg = (args[0] || "").toUpperCase();
    if (arg && (arg in FORMATOS_ET) && arg !== "CUSTOM") {
      const r = await post("/api/layout", { nombre: Tr(`Plano ${(estado.layouts || []).length + 1}`), formato: arg });
      await Papel.entrar(r.indice);
      return Comandos.eco(`Hoja en ${arg}, encuadrada sobre el dibujo.`);
    }
    if (estado.modo === "papel") return cuadroDeHoja(estado.papel.layout, estado.layoutActivo);
    return cuadroDeHoja(null, null);
  },
});

/* «Agregar ventana a hoja»  ·  0.20.0.
 * Mike (9-sep-2026): «se traza un rectángulo en el modelo sobre lo que se
 * quiere englobar → Enter → abre el cuadro de Hoja nueva → al crear, la
 * ventana de la hoja enseña exactamente ese recuadro». Centro = centro del
 * rectángulo; escala = la normalizada más grande en que quepa. */
Comandos.registrar({
  nombre: "VENTANAHOJA", alias: ["AGREGARVENTANA", "VH"],
  ayuda: "Recuadra una zona del modelo y crea una hoja cuya ventana enseña justo eso",
  correr: async () => {
    if (estado.modo === "papel") return Comandos.eco("Se usa desde el modelo: encuadra ahí lo que va a la hoja.", "malo");
    const a = await Entrada.pedirPunto({ mensaje: "Primera esquina de lo que va en la hoja" });
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina opuesta (o teclea ancho, Enter, alto, Enter)", base: a, dinamica: "xy",
      hule: (q) => ({ tipo: "caja", a, b: q }),
    });
    const caja = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
    if (caja[2] - caja[0] < 1e-9 || caja[3] - caja[1] < 1e-9) return Comandos.eco("El recuadro no tiene tamaño.", "malo");
    estado.hule = { tipo: "caja", a, b, punteado: true };
    pintar();
    try {
      return await cuadroDeHoja(null, null, { caja });
    } finally {
      estado.hule = null;
      pintar();
    }
  },
});

Comandos.registrar({
  nombre: "EDITARHOJA", alias: ["HOJACONF"],
  ayuda: "Cuadro de la hoja abierta: formato, escala y pie de plano",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    return cuadroDeHoja(estado.papel.layout, estado.layoutActivo);
  },
});

Comandos.registrar({
  nombre: "MODELO", alias: ["MO"],
  ayuda: "Vuelve al espacio modelo",
  correr: async () => Papel.salir(),
});

/* Centrar el modelo en la ventana de la hoja, a mano  ·  Mike, 8-sep-2026.
 * Enter (o T) centra todo el dibujo; un clic sobre la hoja lleva ese punto
 * del modelo al centro de la ventana. La escala no se toca. */
Comandos.registrar({
  nombre: "CENTRAR", alias: ["CENTRARVENTANA", "CV"],
  ayuda: "Centra el dibujo en la ventana de la hoja (Enter: todo el dibujo; clic: ese punto al centro)",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const i = estado.layoutActivo;
    const vs = estado.papel.layout.ventanas || [];
    if (!vs.length) return Comandos.eco("Esta hoja no tiene ventana.", "malo");
    let p = null;
    try {
      p = await Entrada.pedirPunto({ mensaje: "Clic en la hoja: ese punto queda al centro (Enter o T: todo el dibujo)", opciones: ["T"] });
    } catch (e) {
      if (!(e && e.message === "cancelado")) throw e;
      if (e.motivo !== "enter") return Comandos.eco("Cancelado.");
      p = null;          // Enter en vacío: todo el dibujo
    }
    if (Array.isArray(p)) {
      // ¿En qué ventana cayó? Papel → modelo: centro + (p − centro de la ventana) × escala / k
      const v = vs.find((w) => p[0] >= w.x && p[0] <= w.x + w.ancho && p[1] >= w.y && p[1] <= w.y + w.alto) || vs[0];
      const j = vs.indexOf(v);
      const k = mmPorUnidad(), f = (v.escala || 20) / k;
      const cx = v.x + v.ancho / 2, cy = v.y + v.alto / 2;
      const centro = [v.centro[0] + (p[0] - cx) * f, v.centro[1] + (p[1] - cy) * f];
      await patch(`/api/layout/${i}/ventana/${j}`, { cambios: { centro } });
      Comandos.eco(`Ventana centrada en ${mm(centro[0])}, ${mm(centro[1])} ${U()}.`, "bien");
    } else {
      await patch(`/api/layout/${i}/ventana/0`, { cambios: { centrar: true } });
      Comandos.eco("El dibujo quedó centrado en la ventana.", "bien");
    }
    await Papel.cargar(i);
    pintar();
  },
});

Comandos.registrar({
  nombre: "EDITARVENTANA", alias: ["VENTANAS", "VP"],
  ayuda: "Enciende o apaga los handles de las ventanas de la hoja: esquinas y lados cambian el tamaño, el marco la mueve, el interior corre el dibujo",
  correr: async (args) => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const a = (args[0] || "").toUpperCase();
    const si = a === "ON" ? true : a === "OFF" ? false : !VentanasHoja.activo;
    VentanasHoja.activar(si);
    if (!si) Comandos.eco("Edición de ventanas terminada.");
  },
});

/* Una ventana más: se recuadra sobre la hoja (dos esquinas) y enseña el
 * dibujo a la escala de la primera. Mike (9-sep): «agregar viewports
 * adicionales». */
Comandos.registrar({
  nombre: "VENTANANUEVA", alias: ["NV", "NUEVAVENTANA"],
  ayuda: "Agrega una ventana a la hoja: se recuadra con dos esquinas sobre el papel",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const i = estado.layoutActivo;
    const a = await Entrada.pedirPunto({ mensaje: "Primera esquina de la ventana, sobre la hoja" });
    const b = await Entrada.pedirPunto({
      mensaje: "Esquina opuesta (o teclea ancho, Enter, alto, Enter)", base: a, dinamica: "xy",
      hule: (q) => ({ tipo: "caja", a, b: q }),
    });
    const x = Math.min(a[0], b[0]), y = Math.min(a[1], b[1]);
    const ancho = Math.abs(b[0] - a[0]), alto = Math.abs(b[1] - a[1]);
    if (ancho < 10 || alto < 10) return Comandos.eco("La ventana tiene que medir al menos 10 × 10 mm.", "malo");
    const r = await post(`/api/layout/${i}/ventana`, { x, y, ancho, alto });
    await Papel.cargar(i);
    pintar();
    Comandos.eco(`Ventana ${r.indice + 1} agregada (${mm(ancho)} × ${mm(alto)} mm). EDITARVENTANA para acomodarla.`, "bien");
  },
});

Comandos.registrar({
  nombre: "BORRARVENTANA", alias: ["BV"],
  ayuda: "Quita una ventana de la hoja (clic sobre ella)",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const i = estado.layoutActivo;
    const vs = estado.papel.layout.ventanas || [];
    if (vs.length < 2) return Comandos.eco("La hoja necesita al menos una ventana; no se borra la única.", "malo");
    const p = await Entrada.pedirPunto({ mensaje: "Clic sobre la ventana que se quita" });
    const j = vs.findIndex((v) => p[0] >= v.x && p[0] <= v.x + v.ancho && p[1] >= v.y && p[1] <= v.y + v.alto);
    if (j < 0) return Comandos.eco("Ahí no hay ventana.", "malo");
    await api(`/api/layout/${i}/ventana/${j}`, { method: "DELETE" });
    await Papel.cargar(i);
    pintar();
    Comandos.eco(`Ventana ${j + 1} quitada.`);
  },
});

Comandos.registrar({
  nombre: "ESCALAVENTANA", alias: ["EV", "ESCALA"],
  ayuda: "Cambia la escala de la ventana de la hoja",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const { escalas } = await api("/api/layouts");
    const actual = estado.papel.layout.ventanas[0].escala;
    const e = await Entrada.pedirNumero({
      mensaje: `Escala 1:? (${escalas.join(", ")})`, valor: actual, minimo: 0.01 });
    await patch(`/api/layout/${estado.layoutActivo}/ventana/0`, { cambios: { escala: e } });
    await Papel.cargar(estado.layoutActivo);
    pintar();
    // La escala de las cotas la ajusta el motor (feature 59); se recarga el
    // modelo para que la pantalla lo enseñe también.
    Comandos.eco(`Ventana a 1:${e}. Las cotas se ajustaron para leerse en papel.`);
  },
});

Comandos.registrar({
  nombre: "ENCUADRARVENTANA", alias: ["EVE"],
  ayuda: "Vuelve a centrar la ventana sobre todo el dibujo",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    await patch(`/api/layout/${estado.layoutActivo}/ventana/0`, { cambios: { encuadrar: true } });
    await Papel.cargar(estado.layoutActivo);
    pintar();
    Comandos.eco("Ventana encuadrada.");
  },
});

Comandos.registrar({
  nombre: "ROTULO", alias: ["PIE"],
  ayuda: "Rellena el pie de plano de la hoja",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    // Es el mismo cuadro que la hoja: el pie **es** parte de la hoja, y tener
    // dos formularios para los mismos siete campos acaba con uno de los dos
    // olvidado.
    return cuadroDeHoja(estado.papel.layout, estado.layoutActivo);
  },
});

Comandos.registrar({
  nombre: "BORRARPLANO",
  ayuda: "Borra la hoja abierta",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    if (!confirm(`¿Borrar la hoja «${estado.papel.layout.nombre}»?`)) return;
    await api(`/api/layout/${estado.layoutActivo}`, { method: "DELETE" });
    await Papel.salir();
    Comandos.eco("Hoja borrada.");
  },
});

/* --- Imprimir  ·  features 64, 65, 67 ---------------------------------- */
Comandos.registrar({
  nombre: "IMPRIMIR", alias: ["PDF", "PLOT"],
  ayuda: "IMPRIMIR [TODO] — la hoja abierta, o todas en un PDF",
  correr: async (args) => {
    const layouts = await api("/api/layouts");
    if (!layouts.layouts.length) {
      return Comandos.eco("No hay ninguna hoja. Crea una con PLANO.", "malo");
    }
    const todo = (args[0] || "").toUpperCase().startsWith("TOD");
    const cuales = todo || estado.modo !== "papel" ? null : [estado.layoutActivo];
    const sugerido = (estado.resumen.nombre || "plano") + ".pdf";
    const ruta = await pedirRuta("guardar", [{ name: "PDF", extensions: ["pdf"] }], sugerido);
    if (!ruta) return;
    try {
      const r = await post("/api/imprimir", { ruta, layouts: cuales });
      avisar(`PDF listo: ${r.hojas} hoja(s) en ${r.ruta}`, false, 9000);
      Comandos.eco(`PDF con ${r.hojas} hoja(s).`, "bien");
      if (enElectron() && window.t101.abrirArchivo) window.t101.abrirArchivo(r.ruta);
    } catch (e) { avisar(e.message, true); }
  },
});

Comandos.registrar({
  nombre: "IMAGEN", alias: ["PNG"],
  ayuda: "Guarda la hoja como PNG",
  correr: async () => {
    if (estado.modo !== "papel") return Comandos.eco("Primero abre una hoja.", "malo");
    const dpi = await Entrada.pedirNumero({ mensaje: "Puntos por pulgada", valor: 150, minimo: 30 });
    const ruta = await pedirRuta("guardar", [{ name: "PNG", extensions: ["png"] }],
      (estado.papel.layout.nombre || "plano") + ".png");
    if (!ruta) return;
    const r = await post("/api/imagen", { ruta, layouts: [estado.layoutActivo], dpi });
    avisar(`Imagen de ${r.ancho}×${r.alto} px guardada.`, false, 8000);
  },
});

/* ===================================================================== */
/* Imprimir en impresora de verdad  ·  punto 12                          */
/* ===================================================================== */
/* El PDF ya existía; lo que faltaba era el papel. El camino es el mismo hasta
 * el final: se arma el PDF de la hoja —con su marco, su pie y su escala— y ése
 * es el que se manda a la impresora.
 *
 * Imprimir la pantalla habría sido más corto y habría salido mal: el lienzo no
 * tiene marco, sale con el zoom que tuviera y a una escala que no es ninguna.
 * Un plano que no se puede medir con escalímetro no sirve en obra.
 *
 * El PDF va a una carpeta temporal, no al escritorio del usuario: imprimir no
 * es exportar, y llenarle la carpeta de archivos que no pidió es de mala
 * educación. Si quiere el archivo, para eso está IMPRIMIR. */
/* El cuadro de impresión: qué impresora, cuántas copias, qué hojas.
 *
 * Las impresoras salen de Windows (`getPrintersAsync`), así que la lista es
 * **la misma** que ve cualquier otro programa de la máquina. Elegida una, se
 * imprime directo a ella; el cuadro de Windows queda como opción para cuando
 * hay que tocar bandeja, dúplex o tamaño de papel.
 *
 * Por qué se recuerda la última: en un taller la impresora es siempre la
 * misma, y pasar por el cuadro de Windows en cada hoja son doscientos clics al
 * mes que no deciden nada. */
async function cuadroDeImpresion(cuantas) {
  let impresoras = [];
  try { impresoras = await window.t101.impresoras(); } catch (_) {}

  if (!impresoras.length) {
    // No es un error del programa: es que la PC no tiene ninguna instalada, o
    // que Windows todavía no las entrega. Se dice cuál de las dos cosas puede
    // ser, en vez de un «no se pudo imprimir» que no ayuda.
    const seguir = confirm(
      "Windows no reporta ninguna impresora instalada en esta PC.\n\n" +
      "¿Abrir de todos modos el cuadro de impresión de Windows? " +
      "Desde ahí se puede elegir «Microsoft Print to PDF» o agregar una impresora.");
    return seguir ? { deviceName: null, copias: 1 } : null;
  }

  const guardada = (estado.prefs && estado.prefs.impresora) || "";
  const porOmision = impresoras.find((i) => i.omision);
  const inicial = impresoras.some((i) => i.nombre === guardada) ? guardada
                : porOmision ? porOmision.nombre : impresoras[0].nombre;

  const papelGuardado = (estado.prefs && estado.prefs.papel) || "HOJA";
  const v = await Dialogo.abrir({
    titulo: "Imprimir",
    pista: `${cuantas} hoja(s) · sale la hoja con su marco y su pie, ` +
           "centrada en el papel, no lo que se ve en pantalla.",
    campos: [
      { clave: "impresora", etiqueta: "Impresora", tipo: "lista", valor: inicial,
        opciones: impresoras.map((i) => [i.nombre,
          i.nombre + (i.omision ? "  (predeterminada)" : "")]),
        pista: "Las instaladas en esta PC, las mismas que ve Windows." },
      { clave: "papel", etiqueta: "Tamaño de papel", tipo: "lista", valor: papelGuardado,
        opciones: [["HOJA", "Como la hoja"], ...Object.entries(PAPELES).map(([k, p]) => [k, p.et])],
        pista: "Centrado en el papel (no en los márgenes). Si la hoja es más grande, se reduce para que quepa." },
      { clave: "copias", etiqueta: "Copias", tipo: "numero", valor: 1 },
      { clave: "color", etiqueta: "A color", tipo: "casilla", valor: true },
      { clave: "cuadro", etiqueta: "Abrir el cuadro de Windows", tipo: "casilla",
        valor: false,
        pista: "Para tocar bandeja, dúplex o tamaño de papel." },
    ],
    aceptar: "Imprimir",
    validar: (x) => (x.copias >= 1 && x.copias <= 99
      ? null : "Copias: de 1 a 99."),
    extra: { etiqueta: "Vista previa", accion: (x) => Papel.vistaPrevia({ papel: x.papel, impresora: x.impresora }) },
  });
  if (!v) return null;
  const cambios = {};
  if (v.impresora !== guardada && !v.cuadro) cambios.impresora = v.impresora;
  if (v.papel !== papelGuardado) cambios.papel = v.papel;
  if (Object.keys(cambios).length) await guardarPrefs(cambios);
  return {
    deviceName: v.cuadro ? null : v.impresora,
    copias: Math.round(v.copias),
    color: v.color,
    papel: v.papel,
  };
}

/* --- Papel, centrado y vista previa  ·  6-sep-2026 --------------------------
 *
 * Mike: *«a la hora de mandar a imprimir, quiero un botón de "vista previa"
 * donde renderice cómo queda impreso el plano en la impresora seleccionada y
 * con el tamaño de hoja seleccionado. El default siempre debe ser que la
 * impresión esté centrada a la hoja, no a los márgenes de impresión»*.
 *
 * Cómo se centra de verdad: la impresora recibe una página del tamaño exacto
 * del papel, sin márgenes, con la hoja puesta en el centro (ver
 * `armarHTMLImpresion`). Lo que la impresora no alcanza a pintar —sus 3 a
 * 5 mm de borde— se queda en blanco, pero el dibujo no se corre: el centro
 * sigue siendo el centro. La vista previa enseña ese borde en gris. */
const PAPELES = {
  A4: { ancho: 297, alto: 210, et: "A4 · 297 × 210" },
  A3: { ancho: 420, alto: 297, et: "A3 · 420 × 297" },
  A2: { ancho: 594, alto: 420, et: "A2 · 594 × 420" },
  A1: { ancho: 841, alto: 594, et: "A1 · 841 × 594" },
  A0: { ancho: 1189, alto: 841, et: "A0 · 1189 × 841" },
  CARTA: { ancho: 279.4, alto: 215.9, et: "Carta · 279 × 216" },
  OFICIO: { ancho: 355.6, alto: 215.9, et: "Oficio · 356 × 216" },
  TABLOIDE: { ancho: 431.8, alto: 279.4, et: "Tabloide · 432 × 279" },
};
const BORDE_IMPRESORA = 5;   // mm que una impresora de oficina no suele alcanzar

/** Dónde cae la hoja (anchoH × altoH) en el papel elegido: papel en mm,
 *  orientado como la hoja, escala (1 = tamaño real) y desplazamiento. Pura. */
function calcularImpresion(anchoH, altoH, papel) {
  let pw, ph;
  if (!papel || papel === "HOJA" || !PAPELES[papel]) { pw = anchoH; ph = altoH; }
  else {
    const p = PAPELES[papel];
    // el papel se orienta como la hoja: apaisado si la hoja es apaisada
    const apaisada = anchoH >= altoH;
    pw = apaisada ? Math.max(p.ancho, p.alto) : Math.min(p.ancho, p.alto);
    ph = apaisada ? Math.min(p.ancho, p.alto) : Math.max(p.ancho, p.alto);
  }
  const escala = Math.min(1, pw / anchoH, ph / altoH);
  const w = anchoH * escala, h = altoH * escala;
  return { papelAncho: pw, papelAlto: ph, escala, x: (pw - w) / 2, y: (ph - h) / 2, ancho: w, alto: h,
           horizontal: pw >= ph, recorte: Math.max(0, BORDE_IMPRESORA - (pw - w) / 2, BORDE_IMPRESORA - (ph - h) / 2) };
}

/** La página HTML que se imprime: una @page por hoja, del tamaño del papel,
 *  sin márgenes, con el SVG de la hoja centrado. */
function armarHTMLImpresion(hojas, papel) {
  const paginas = hojas.map(({ ancho, alto, svg }) => {
    const c = calcularImpresion(ancho, alto, papel);
    return `<div class="pag" style="width:${c.papelAncho}mm;height:${c.papelAlto}mm">` +
           `<div class="hoja" style="left:${c.x}mm;top:${c.y}mm;width:${c.ancho}mm;height:${c.alto}mm">${svg}</div></div>`;
  });
  const c0 = calcularImpresion(hojas[0].ancho, hojas[0].alto, papel);
  return `<!doctype html><html><head><meta charset="utf-8"><title>shape101</title><style>
@page{size:${c0.papelAncho}mm ${c0.papelAlto}mm;margin:0}
html,body{margin:0;padding:0;background:#fff}
.pag{position:relative;overflow:hidden;page-break-after:always;break-after:page}
.pag:last-child{page-break-after:auto;break-after:auto}
.hoja{position:absolute}
.hoja svg{width:100%;height:100%;display:block}
</style></head><body>${paginas.join("")}</body></html>`;
}

Papel.calcularImpresion = calcularImpresion;
Papel.armarHTMLImpresion = armarHTMLImpresion;
Papel.PAPELES = PAPELES;

/** La vista previa: el papel elegido con la hoja centrada, a escala. */
Papel.vistaPrevia = async function ({ papel = "HOJA", impresora = "", layouts = null } = {}) {
  const cuales = layouts || (estado.modo === "papel" ? [estado.layoutActivo] : null);
  const { layouts: todos } = await api("/api/layouts");
  if (!todos.length) { Comandos.eco("No hay ninguna hoja que imprimir. Crea una con PLANO.", "malo"); return null; }
  const indices = cuales || todos.map((_, i) => i);
  const i0 = indices[0];
  const L = todos[i0];
  const svg = await (await fetch(`/api/papel/${i0}/svg`)).text();
  const hoja = await api(`/api/papel/${i0}`);
  const c = calcularImpresion(hoja.ancho, hoja.alto, papel);

  const capa = document.createElement("div");
  capa.className = "previa-imp";
  const etPapel = papel === "HOJA" || !PAPELES[papel] ? `${Math.round(c.papelAncho)} × ${Math.round(c.papelAlto)} mm` : PAPELES[papel].et;
  const nota = c.escala < 0.999
    ? Tr(`La hoja (${Math.round(hoja.ancho)} × ${Math.round(hoja.alto)}) es más grande que el papel (${Math.round(c.papelAncho)} × ${Math.round(c.papelAlto)}): se escala a ${Math.round(c.escala * 100)} %.`)
    : Tr("Sale a tamaño real.");
  const recorte = c.recorte > 0.05 ? " " + Tr(`Se recorta: ${c.recorte.toFixed(1)} mm se salen del área imprimible.`) : "";
  capa.innerHTML = `
    <div class="panel">
      <div class="cab"><b>${Tr("Vista previa de impresión")}</b>
        <span class="det">${(impresora ? impresora + " · " : "") + etPapel}${indices.length > 1 ? ` · ${indices.length} ${Tr("hojas")}` : ""}</span>
        <button class="cerrar" title="${Tr("Cerrar")}">×</button></div>
      <div class="lienzo"><div class="papel"><div class="borde"></div><div class="hoja"></div></div></div>
      <div class="pie"><span class="nota">${nota}${recorte} ${Tr("Centrado en el papel (no en los márgenes)")}.</span>
        <span class="crece"></span>
        <button class="gh cerrar">${Tr("Cerrar")}</button>
        <button class="pri imprimir">${Tr("Imprimir")}</button></div>
    </div>`;
  document.body.appendChild(capa);
  const zona = capa.querySelector(".lienzo"), papelEl = capa.querySelector(".papel");
  const hojaEl = capa.querySelector(".hoja"); hojaEl.innerHTML = svg;
  const acomodar = () => {
    const aw = zona.clientWidth - 40, ah = zona.clientHeight - 40;
    const k = Math.min(aw / c.papelAncho, ah / c.papelAlto);
    papelEl.style.width = (c.papelAncho * k) + "px"; papelEl.style.height = (c.papelAlto * k) + "px";
    hojaEl.style.left = (c.x * k) + "px"; hojaEl.style.top = (c.y * k) + "px";
    hojaEl.style.width = (c.ancho * k) + "px"; hojaEl.style.height = (c.alto * k) + "px";
    capa.querySelector(".borde").style.borderWidth = (BORDE_IMPRESORA * k) + "px";
  };
  acomodar();
  window.addEventListener("resize", acomodar);
  const cerrar = () => { window.removeEventListener("resize", acomodar); capa.remove(); };
  capa.querySelectorAll(".cerrar").forEach((b) => b.onclick = cerrar);
  capa.querySelector(".imprimir").onclick = async () => {
    cerrar();
    if (typeof Dialogo !== "undefined" && Dialogo.activo()) Dialogo.cerrar(null);
    await Papel.imprimirEn({ deviceName: impresora || null, copias: 1, color: true, papel }, indices);
  };
  capa.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
  return { calculo: c, hoja: L, indices };
};

/** Manda las hojas a la impresora, centradas en el papel (HTML + @page). */
Papel.imprimirEn = async function (elegido, indices) {
  if (!enElectron() || !window.t101.imprimirHTML) {
    return Comandos.eco("Imprimir en papel sólo funciona en la aplicación instalada.", "malo");
  }
  avisar("Preparando la hoja…");
  try {
    const hojas = [];
    for (const i of indices) {
      const h = await api(`/api/papel/${i}`);
      const svg = await (await fetch(`/api/papel/${i}/svg`)).text();
      hojas.push({ ancho: h.ancho, alto: h.alto, svg });
    }
    const c = calcularImpresion(hojas[0].ancho, hojas[0].alto, elegido.papel);
    const html = armarHTMLImpresion(hojas, elegido.papel);
    const fallo = await window.t101.imprimirHTML(html, {
      deviceName: elegido.deviceName, copias: elegido.copias, color: elegido.color,
      anchoMM: c.papelAncho, altoMM: c.papelAlto, horizontal: c.horizontal,
    });
    if (fallo === "cancelado") return Comandos.eco("Impresión cancelada.");
    if (fallo) return avisar("No se pudo imprimir: " + fallo, true, 9000);
    const donde = elegido.deviceName ? ` en ${elegido.deviceName}` : "";
    avisar(`Mandado a imprimir: ${hojas.length} hoja(s)${donde}.`);
    Comandos.eco(`${hojas.length} hoja(s) a la impresora${donde}.`, "bien");
  } catch (e) { avisar(e.message, true, 9000); }
};

Comandos.registrar({
  nombre: "VISTAPREVIA", alias: ["PREVIA", "PREVIEW"],
  ayuda: "Enseña cómo sale la hoja en la impresora y el papel elegidos",
  correr: async () => {
    const { layouts } = await api("/api/layouts");
    if (!layouts.length) return Comandos.eco("No hay ninguna hoja que imprimir. Crea una con PLANO.", "malo");
    await Papel.vistaPrevia({ papel: (estado.prefs && estado.prefs.papel) || "HOJA",
                              impresora: (estado.prefs && estado.prefs.impresora) || "" });
  },
});

Comandos.registrar({
  nombre: "IMPRIMIRFISICO", alias: ["IMPRESORA", "PLOTEAR"],
  ayuda: "Manda la hoja a una impresora de la PC (Ctrl+P)",
  correr: async (args) => {
    const { layouts } = await api("/api/layouts");
    if (!layouts.length) {
      return Comandos.eco("No hay ninguna hoja que imprimir. Crea una con PLANO.", "malo");
    }
    if (!enElectron() || !window.t101.imprimirPDF) {
      return Comandos.eco(
        "Imprimir en papel sólo funciona en la aplicación instalada. " +
        "Desde el navegador, exporta el PDF con IMPRIMIR.", "malo");
    }
    const todo = (args[0] || "").toUpperCase().startsWith("TOD");
    const cuales = todo || estado.modo !== "papel" ? null : [estado.layoutActivo];
    const cuantas = cuales ? cuales.length : layouts.length;

    const elegido = await cuadroDeImpresion(cuantas);
    if (!elegido) return Comandos.eco("Impresión cancelada.");
    const indices = cuales || layouts.map((_, i) => i);
    await Papel.imprimirEn(elegido, indices);
  },
});
