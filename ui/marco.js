/* El marco de la ventana: ancho del panel, pestañas de dibujos y pantalla de
 * inicio. Tres cosas que no dibujan nada y que deciden si la app se siente
 * cómoda. Puntos 5, 10 y 14 de la lista de Mike.
 */

const Marco = (() => {

  /* ===================================================================== */
  /* Ancho del panel de la derecha  ·  punto 5                             */
  /* ===================================================================== */
  /* El panel de capas era de 340 px fijos. Con nombres de capa de plano ajeno
   * —«A-MURO-EXIST-CARP-01»— no cabía nada, y en una pantalla chica se comía
   * el lienzo. Se arrastra del borde y se queda: es preferencia del usuario,
   * como el anclaje de la barra. */
  const ANCHO_MIN = 200, ANCHO_MAX = 720, ANCHO_NORMAL = 340;

  function aplicarAncho(px) {
    const v = Math.round(Math.min(Math.max(px, ANCHO_MIN), ANCHO_MAX));
    document.documentElement.style.setProperty("--panel-ancho", v + "px");
    return v;
  }

  function conectarPanel() {
    const asa = $("#asa-panel");
    if (!asa) return;
    aplicarAncho((estado.prefs && estado.prefs.panel_ancho) || ANCHO_NORMAL);
    let arrastre = null;

    asa.addEventListener("mousedown", (e) => {
      arrastre = { x: e.clientX, ancho: $("aside").getBoundingClientRect().width };
      asa.classList.add("activa");
      // Sin esto, arrastrar sobre el lienzo empieza a seleccionar entidades.
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!arrastre) return;
      // Se arrastra hacia la izquierda para ensanchar: el panel está pegado al
      // borde derecho, así que el ancho crece cuando el ratón retrocede.
      aplicarAncho(arrastre.ancho + (arrastre.x - e.clientX));
      ajustarLienzo();
    });
    window.addEventListener("mouseup", async () => {
      if (!arrastre) return;
      arrastre = null;
      asa.classList.remove("activa");
      const ancho = Math.round($("aside").getBoundingClientRect().width);
      await guardarPrefs({ panel_ancho: ancho });
    });
    asa.addEventListener("dblclick", async () => {
      aplicarAncho(ANCHO_NORMAL);
      ajustarLienzo();
      await guardarPrefs({ panel_ancho: ANCHO_NORMAL });
    });
  }

  /* ===================================================================== */
  /* Pestañas de dibujos abiertos  ·  punto 14                             */
  /* ===================================================================== */
  /* La vista de cada pestaña se guarda al salir de ella. Volver a un plano y
   * encontrarlo encuadrado de otra manera es pequeño y molesta mucho: se
   * pierde dónde estabas mirando. */
  const vistas = new Map();

  function pintarDocs(esc) {
    if (!esc) return;
    estado.escritorio = esc;
    const barra = $("#docs"), tiras = $("#doc-tiras");
    if (!barra || !tiras) return;
    // Una sola pestaña no es una pestaña: se esconde la fila entera.
    barra.hidden = esc.documentos.length < 2;
    tiras.textContent = "";
    for (const d of esc.documentos) {
      const t = document.createElement("div");
      t.className = "pest" + (d.indice === esc.activo ? " activa" : "");
      t.title = d.ruta || "Sin guardar";
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = d.nombre || "Sin título";
      const punto = document.createElement("span");
      punto.className = "punto" + (d.sucio ? " si" : "");
      const x = document.createElement("button");
      x.className = "x";
      x.textContent = "×";
      x.title = "Cerrar";
      x.onclick = (e) => { e.stopPropagation(); cerrarDoc(d.indice); };
      t.append(punto, n, x);
      t.onclick = () => activarDoc(d.indice);
      tiras.appendChild(t);
    }
  }

  function recordarVista() {
    const esc = estado.escritorio;
    if (esc) vistas.set(esc.activo, { ...estado.vista });
  }

  async function tras(r, indice) {
    aplicar(r);
    estado.modo = "modelo";
    estado.sel.clear();
    await recargarTrazos();
    await Papel.pintarPestanas();
    const v = vistas.get(indice);
    if (v) { Object.assign(estado.vista, { x: v.x, y: v.y, escala: v.escala }); pintar(); } else encuadrar(false);
  }

  async function activarDoc(i) {
    if (estado.escritorio && i === estado.escritorio.activo) return;
    recordarVista();
    await tras(await post("/api/documentos/activar", { indice: i }), i);
  }

  async function cerrarDoc(i) {
    const d = (estado.escritorio.documentos || [])[i];
    if (d && d.sucio &&
        !confirm(`«${d.nombre}» tiene cambios sin guardar. ¿Cerrarlo de todos modos?`)) {
      return;
    }
    vistas.clear();          // los índices se recorren: guardarlas mentiría
    const r = await post("/api/documentos/cerrar", { indice: i });
    await tras(r, -1);
  }

  /** Un dibujo nuevo en su propia pestaña. */
  async function nuevoDoc() {
    recordarVista();
    const r = await post("/api/nuevo", { pestana: true });
    await tras(r, -1);
    Comandos.eco("Dibujo nuevo.");
  }

  /** ¿La pestaña de enfrente está en blanco? Entonces abrir aquí no pierde
   *  nada, y así no se acumulan pestañas vacías al abrir tres planos. */
  const enBlanco = () =>
    !!estado.resumen && !estado.resumen.sucio && !estado.resumen.ruta &&
    estado.resumen.entidades === 0;

  function conectarDocs() {
    const mas = $("#doc-mas");
    if (mas) mas.onclick = nuevoDoc;
  }

  /* ===================================================================== */
  /* Pantalla de inicio  ·  punto 10                                       */
  /* ===================================================================== */
  /* La misma del Despiezador, y por la misma razón: al abrir el programa, lo
   * primero que uno quiere no es un lienzo en blanco, es *el plano en el que
   * estaba*. */

  function cuando(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const min = Math.round((Date.now() - d.getTime()) / 60000);
    if (min < 1) return "hace un momento";
    if (min < 60) return `hace ${min} min`;
    const h = Math.round(min / 60);
    if (h < 24) return `hace ${h} h`;
    const dias = Math.round(h / 24);
    if (dias === 1) return "ayer";
    if (dias < 30) return `hace ${dias} días`;
    return d.toLocaleDateString();
  }

  function pintarRecientes() {
    const caja = $("#iRecientes");
    if (!caja) return;
    const lista = (estado.prefs && estado.prefs.recientes) || [];
    caja.textContent = "";
    if (!lista.length) {
      const v = document.createElement("div");
      v.className = "vacio";
      v.textContent = "Todavía no has abierto ningún plano.";
      caja.appendChild(v);
      return;
    }
    for (const r of lista) {
      const b = document.createElement("button");
      b.className = "rec";
      const n1 = document.createElement("div");
      n1.className = "n1";
      const nom = document.createElement("span");
      nom.textContent = r.nombre || "(sin nombre)";
      const c = document.createElement("span");
      c.className = "cuando";
      c.textContent = cuando(r.cuando);
      n1.append(nom, c);
      const n2 = document.createElement("div");
      n2.className = "n2";
      n2.textContent = r.ruta || "";
      b.append(n1, n2);
      b.onclick = async () => {
        cerrarInicio();
        try { await Archivo.abrir(r.ruta); }
        catch (e) { avisar(e.message, true, 9000); abrirInicio(); }
      };
      caja.appendChild(b);
    }
  }

  function abrirInicio() {
    const caja = $("#inicio");
    if (!caja) return;
    caja.classList.add("on");
    // El aspa sólo aparece si hay a dónde volver: con el dibujo en blanco
    // recién arrancado, cerrar la pantalla no lleva a ninguna parte.
    caja.classList.toggle("hayDibujo", !enBlanco());
    const v = $("#iVersion");
    if (v && estado.version) v.textContent = `versión ${estado.version.version}`;
    pintarRecientes();
  }

  function cerrarInicio() {
    const caja = $("#inicio");
    if (caja) caja.classList.remove("on");
  }

  const inicioAbierto = () => !!$("#inicio") && $("#inicio").classList.contains("on");

  function conectarInicio() {
    $("#iCerrar").onclick = () => { if (!enBlanco()) cerrarInicio(); };
    $("#iNuevo").onclick = async () => {
      cerrarInicio();
      if (!enBlanco()) await nuevoDoc();
    };
    $("#iAbrir").onclick = async () => {
      cerrarInicio();
      if (!(await Archivo.pedirYAbrir())) abrirInicio();
    };
    $("#iT101x").onclick = async () => {
      cerrarInicio();
      await Comandos.correr("T101X");
    };
    $("#iOlvidar").onclick = async (e) => {
      e.stopPropagation();
      await guardarPrefs({ recientes: [] });
      pintarRecientes();
    };
    const b = $("#b-inicio");
    if (b) b.onclick = () => (inicioAbierto() ? cerrarInicio() : abrirInicio());

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && inicioAbierto() && !enBlanco()) {
        e.preventDefault();
        cerrarInicio();
      }
      if (e.ctrlKey && !e.shiftKey && (e.key === "i" || e.key === "I")) {
        e.preventDefault();
        inicioAbierto() ? cerrarInicio() : abrirInicio();
      }
    });
  }

  /* --- Arranque --------------------------------------------------------- */
  function conectar() {
    conectarPanel();
    conectarDocs();
    conectarInicio();
    if (estado.resumen) pintarDocs(estado.resumen.escritorio);

    // Se enseña sólo si de verdad no hay nada abierto: si Windows arrancó la
    // app con doble clic en un .t101d, tapar el plano con una portada sería
    // exactamente lo contrario de lo que se pidió.
    //
    // Y hay que **esperar a saberlo**. Este archivo se ejecuta antes de que
    // app.js haya terminado de pedir el estado al motor, así que preguntar de
    // inmediato es preguntar sin datos: la portada no saldría nunca. Se espera
    // a que llegue el resumen, con tope por si el motor no contesta.
    let intentos = 0;
    (function esperar() {
      if (estado.resumen) {
        if (enBlanco()) abrirInicio();
        return;
      }
      if (intentos++ > 60) return;
      setTimeout(esperar, 80);
    })();
  }

  return { conectar, pintarDocs, activarDoc, cerrarDoc, nuevoDoc, enBlanco,
           abrirInicio, cerrarInicio, inicioAbierto, recordarVista };
})();

/* `const` en el ámbito del script **no** crea una propiedad de `window`. app.js
 * se carga antes que este archivo y pregunta por `window.Marco` para saber si
 * ya está —tabla de pestañas incluida—, así que hay que colgarlo a mano. Sin
 * esta línea las pestañas no se pintan nunca y no truena nada: el peor tipo de
 * fallo. */
window.Marco = Marco;

Marco.conectar();
