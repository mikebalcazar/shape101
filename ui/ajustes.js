/* Ajustes con cuadro de diálogo: referencias a objetos y estilo de cota.
 *
 * Los dos existían, pero sólo por línea de comandos —`REF EXTREMO` para
 * encender un modo, `PROPCOTA` para tocar el estilo—, que es tanto como no
 * existir: nadie descubre lo que no ve. Mike preguntó si había siquiera
 * referencias a extremo, medio, intersección y cuadrante. Las hay, las ocho de
 * AutoCAD, desde el primer día; lo que faltaba era enseñarlas.
 */

const Ajustes = (() => {

  /* --- Referencias a objetos  ·  punto 2 -------------------------------- */
  /* Con qué se engancha el cursor. El orden de la lista es el de prioridad
   * real (ver ui/osnap.js): si dos referencias caen igual de cerca, gana la de
   * arriba. Por eso «cercano» va al final y apagado — siempre acierta, y si
   * compitiera de tú a tú taparía a todas las demás. */
  const ORDEN = ["extremo", "interseccion", "medio", "centro", "cuadrante",
                 "nodo", "perpendicular", "proyeccion", "cercano"];

  const PISTAS = {
    extremo: "La punta de una línea, un arco o un lado de polilínea.",
    interseccion: "Donde dos trazos se cruzan de verdad.",
    medio: "La mitad exacta del trazo.",
    centro: "El centro de un círculo, un arco o una elipse.",
    cuadrante: "Los cuatro puntos del reloj: 0°, 90°, 180° y 270°.",
    nodo: "Un punto suelto o el origen de un bloque insertado.",
    perpendicular: "El pie de la perpendicular desde el punto anterior.",
    proyeccion: "Seguir la perpendicular desde el punto anterior aunque se salga del trazo, y donde cruza con otro.",
    cercano: "Cualquier punto sobre el trazo. Siempre acierta, por eso estorba.",
  };

  async function referencias() {
    const p = estado.prefs || {};
    const modos = p.osnap_modos || {};
    const campos = [
      { clave: "osnap", etiqueta: "Referencias encendidas (F3)", tipo: "casilla",
        valor: !!p.osnap },
      { clave: "_t1", etiqueta: "A qué se engancha", tipo: "titulo" },
    ];
    for (const m of ORDEN) {
      campos.push({ clave: m, etiqueta: estado.modosOsnap[m] || m, tipo: "casilla",
                    valor: !!modos[m], pista: PISTAS[m] });
    }
    campos.push({ clave: "_t2", etiqueta: "Puntería", tipo: "titulo" });
    campos.push({ clave: "osnap_apertura", etiqueta: "Apertura", tipo: "numero",
                  valor: p.osnap_apertura || 14, sufijo: "píxeles",
                  pista: "Cuánto se aleja el cursor y sigue enganchando." });

    const v = await Dialogo.abrir({
      titulo: "Referencias a objetos",
      pista: "Se aplican también al jalar un grip: así un extremo se pega a otro.",
      campos, aceptar: "Guardar",
      validar: (x) => (x.osnap_apertura >= 2 && x.osnap_apertura <= 60
        ? null : "La apertura razonable va de 2 a 60 píxeles."),
    });
    if (!v) return;
    const nuevos = {};
    for (const m of ORDEN) nuevos[m] = !!v[m];
    await guardarPrefs({ osnap: !!v.osnap, osnap_modos: nuevos,
                         osnap_apertura: v.osnap_apertura });
    pintarInterruptores();
    const encendidos = ORDEN.filter((m) => nuevos[m]).length;
    Comandos.eco(`Referencias: ${v.osnap ? encendidos + " modo(s)" : "apagadas"}.`, "bien");
  }

  /* --- Estilo de cota  ·  punto 3 --------------------------------------- */
  /* Las dos medidas que importan y por qué son dos:
   *
   *   · **altura en el papel** — lo que mide el texto impreso. 2.5 mm es el
   *     estándar de dibujo técnico y es lo que se manda al DXF como DIMTXT.
   *   · **escala de la cota** (el DIMSCALE de AutoCAD) — por cuánto se
   *     multiplica en el modelo. A 1:12, 2.5 × 12 = 30 mm en el dibujo.
   *
   * Mike pidió «30 mm o 30 unidades» de texto, que es la segunda columna. Se
   * hizo así y no poniendo 30 de altura a secas porque al meter el dibujo en
   * una hoja el motor ajusta esa escala solo (ver core/papel.py): con 30 de
   * altura, una hoja a 1:20 sacaría letras de 60 cm. Se enseñan las dos
   * columnas para que no haya que adivinar cuál es cuál. */
  async function estiloCota() {
    let est;
    try {
      const r = await api("/api/estilos_cota");
      est = r.estilos[r.activo] || {};
    } catch (e) { return avisar(e.message, true); }
    const enModelo = (v) => `= ${(v * (est.factor_escala || 1)).toFixed(1)} mm en el dibujo`;

    const v = await Dialogo.abrir({
      titulo: "Estilo de cota",
      pista: "Cambiar esto cambia las cotas del plano entero, no sólo las nuevas.",
      campos: [
        { clave: "factor_escala", etiqueta: "Escala de la cota", tipo: "numero",
          valor: est.factor_escala, sufijo: "×",
          pista: "El DIMSCALE. Al poner el dibujo en una hoja se ajusta solo a la escala de la ventana." },
        { clave: "_t1", etiqueta: "Texto", tipo: "titulo" },
        { clave: "altura_texto", etiqueta: "Altura", tipo: "numero",
          valor: est.altura_texto, sufijo: "mm en papel",
          pista: enModelo(est.altura_texto) },
        { clave: "decimales", etiqueta: "Decimales", tipo: "numero",
          valor: est.decimales },
        { clave: "sufijo", etiqueta: "Sufijo", tipo: "texto",
          valor: est.sufijo || "", marcador: "mm, cm…" },
        { clave: "_t2", etiqueta: "Flechas y líneas", tipo: "titulo" },
        { clave: "flecha", etiqueta: "Punta", tipo: "lista",
          valor: (est.flecha || "ARCHTICK").toUpperCase(),
          opciones: [["ARCHTICK", "Palomita de arquitectura"], ["CERRADA", "Flecha llena"],
                     ["ABIERTA", "Flecha abierta"], ["PUNTO", "Punto"]] },
        { clave: "tam_flecha", etiqueta: "Tamaño", tipo: "numero",
          valor: est.tam_flecha, sufijo: "mm en papel",
          pista: enModelo(est.tam_flecha) },
        { clave: "ext_linea", etiqueta: "Sobresale", tipo: "numero",
          valor: est.ext_linea, sufijo: "mm en papel",
          pista: "Cuánto pasa la línea de extensión de la línea de cota." },
        { clave: "hueco_origen", etiqueta: "Hueco", tipo: "numero",
          valor: est.hueco_origen, sufijo: "mm en papel",
          pista: "Separación entre la pieza y donde arranca la línea." },
      ],
      aceptar: "Aplicar",
      validar: (x) => {
        if (!(x.altura_texto > 0)) return "El texto no puede medir cero.";
        if (!(x.factor_escala > 0)) return "La escala de la cota tiene que ser mayor que cero.";
        if (x.decimales < 0 || x.decimales > 4) return "Decimales: de 0 a 4.";
        return null;
      },
    });
    if (!v) return;
    const cambios = { ...v };
    delete cambios._t1; delete cambios._t2;
    cambios.decimales = Math.round(cambios.decimales);
    const r = await post("/api/estilo_cota", { nombre: "T101", cambios });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
    Comandos.eco(`Estilo de cota: texto de ${(r.estilo.altura_texto * r.estilo.factor_escala).toFixed(1)} mm en el dibujo.`, "bien");
  }

  /* --- ODA File Converter  ·  6-sep ------------------------------------- */
  /* Mike: «¿no hay manera de integrar el ODA, o agregar la opción de
   * instalarlo?». Integrarlo no (su licencia no deja redistribuirlo);
   * instalarlo desde aquí sí. El motor lo baja de ODA —la versión la dice el
   * puntero fijo de Taller 101, ver core/oda.py— y corre su instalador, que es
   * el que enseña la licencia y pide el permiso de Windows. Aquí sólo se
   * pregunta, se enseña el avance y se avisa cuando quedó. */
  let vigilando = null;

  function vigilar() {
    if (vigilando) return;
    vigilando = setInterval(async () => {
      let e;
      try { e = await api("/api/oda/estado"); } catch (_) { return; }
      if (e.fase === "descargando") {
        avisar(e.mensaje, false, 0);
      } else if (e.fase === "instalando") {
        avisar(e.mensaje, false, 0);
      } else {
        clearInterval(vigilando); vigilando = null;
        if (e.fase === "listo") {
          estado.resumen.dwg = e.dwg;
          aplicar(estado.resumen);
          avisar(e.mensaje, false, 8000);
          Comandos.eco("ODA File Converter instalado. Los DWG se convierten con él desde ahora.", "bien");
        } else if (e.fase === "cancelado") {
          avisar(e.mensaje, false, 4000);
        } else if (e.fase === "error") {
          avisar(e.mensaje, true, 10000);
        }
      }
    }, 700);
  }

  async function oda({ motivo } = {}) {
    let r;
    try { r = await api("/api/oda"); }
    catch (e) { avisar("No se pudo consultar el ODA: " + e.message, true); return; }
    const inst = r.instalado, ult = r.ultimo || {};
    const lineas = [];
    if (motivo) lineas.push(motivo);
    lineas.push(inst
      ? `Instalado: ODA File Converter ${inst.version || "(versión desconocida)"}.`
      : "No está instalado. Ahora los DWG se convierten con el motor propio (LibreDWG), que es más lento y menos fiel.");
    if (ult.fuente === "taller101") lineas.push(`Última versión según Taller 101: ${ult.version}${ult.actualizado ? " (" + ult.actualizado + ")" : ""}.`);
    else if (ult.fuente === "oda") lineas.push(`Última versión según la página de ODA: ${ult.version}.`);
    else lineas.push("No se pudo consultar la última versión (¿sin internet?).");
    lineas.push("Es gratuito; lo baja de opendesign.com (~60 MB) y corre su instalador: hay que aceptar su licencia y el permiso de Windows.");

    let accion = null;
    if (!r.se_puede_instalar) accion = ult.url ? "abrir" : null;
    else if (!inst) accion = "instalar";
    else if (r.hay_nueva) accion = "actualizar";

    if (r.estado && (r.estado.fase === "descargando" || r.estado.fase === "instalando")) {
      avisar(r.estado.mensaje, false, 0); vigilar(); return;
    }

    const v = await Dialogo.abrir({
      titulo: "ODA File Converter",
      pista: lineas.join("\n"),
      campos: [],
      aceptar: accion === "instalar" ? "Instalar" : accion === "actualizar" ? `Actualizar a ${ult.version}`
             : accion === "abrir" ? "Abrir la página de ODA" : "Cerrar",
      cancelar: accion ? "Ahora no" : "Cancelar",
    });
    if (!v || !accion) return;
    if (accion === "abrir") { window.open(ult.url, "_blank"); return; }
    const e = await post("/api/oda/instalar", {});
    if (e.abrir) { avisar(e.mensaje, true, 8000); window.open(e.abrir, "_blank"); return; }
    avisar("Bajando el ODA File Converter…", false, 0);
    vigilar();
  }

  /* --- Configuración general: idioma y tema  ·  0.19.0 ------------------ */
  async function general() {
    const prefs = estado.prefs || {};
    const v = await Dialogo.abrir({
      titulo: "Configuración de shape101",
      pista: "Los comandos se aceptan en los dos idiomas siempre (LINE y LINEA). Cambiar el idioma recarga la ventana.",
      campos: [
        { clave: "idioma", etiqueta: "Idioma", tipo: "lista", valor: prefs.idioma === "es" ? "es" : "en",
          opciones: [["en", "English"], ["es", "Español"]] },
        { clave: "tema", etiqueta: "Tema", tipo: "lista", valor: prefs.tema === "oscuro" ? "oscuro" : "claro",
          opciones: [["claro", "Claro"], ["oscuro", "Oscuro"]] },
        { clave: "parpadeo_comando", etiqueta: "Parpadeo al ejecutar", tipo: "casilla",
          valor: prefs.parpadeo_comando !== false,
          pista: "Un parpadeo casi imperceptible del lienzo cuando un comando cambia algo" },
      ],
      aceptar: "Aplicar",
    });
    if (!v) return;
    if (!!v.parpadeo_comando !== (prefs.parpadeo_comando !== false)) {
      await guardarPrefs({ parpadeo_comando: !!v.parpadeo_comando });
    }
    if (v.tema !== (prefs.tema || "claro")) {
      document.documentElement.dataset.tema = v.tema;
      await guardarPrefs({ tema: v.tema });
      if (typeof logoDelTema === "function") logoDelTema();
      pintarCapas(); pintar();
    }
    if (v.idioma !== (prefs.idioma === "es" ? "es" : "en")) {
      Comandos.eco(Tr(`Idioma: ${v.idioma === "es" ? "Español" : "English"}. Recargando…`));
      await Idioma.cambiar(v.idioma);
    }
  }

  return { referencias, estiloCota, oda, general };
})();

Comandos.registrar({
  nombre: "CONFIGURACION", alias: ["CONFIG", "OPCIONES", "AJUSTES", "PREFERENCIAS"],
  ayuda: "Cambia el idioma de la interfaz y el tema",
  correr: () => Ajustes.general(),
});

/* Unidades del dibujo  ·  0.19.3. Mike (7-sep-2026): «necesitamos poder editar
 * en qué unidades (metro, centímetro o milímetro) se va a trabajar el plano». */
Ajustes.unidades = async function (args = []) {
  const actual = U();
  const nombres = { mm: "milímetros", cm: "centímetros", m: "metros" };
  let elegida = String(args[0] || "").toLowerCase(), escalar = true;
  if (!(elegida in nombres)) {
    const v = await Dialogo.abrir({
      titulo: Tr("Unidades del dibujo"),
      pista: Tr("Todo lo que se teclea, se ve y se acota va en esta unidad; el DXF sale con ella declarada. Con «escalar», la mesa de 600 mm pasa a medir 0.6 m; sin escalar, los números se quedan y sólo cambia lo que significan."),
      campos: [
        { clave: "unidades", etiqueta: Tr("Unidad de trabajo"), tipo: "lista", valor: actual,
          opciones: [["mm", "mm — " + Tr("milímetros")], ["cm", "cm — " + Tr("centímetros")], ["m", "m — " + Tr("metros")]] },
        { clave: "escalar", etiqueta: Tr("Escalar lo dibujado para conservar el tamaño real"), tipo: "casilla", valor: true },
      ],
      aceptar: Tr("Aplicar"),
    });
    if (!v) return;
    elegida = v.unidades; escalar = !!v.escalar;
  }
  if (elegida === actual) { Comandos.eco(F("El dibujo ya está en {0}.", elegida)); return; }
  let r;
  try { r = await post("/api/unidades", { unidades: elegida, escalar }); }
  catch (e) { avisar(e.message, true); return; }
  aplicar(r);
  await recargarTrazos();
  pintarCapas(); pintar();
  Comandos.eco(r.escalado
    ? F("Unidades: {0} (lo dibujado se escaló ×{1}; las cotas con {2} decimales).", elegida, r.factor, { mm: 0, cm: 1, m: 3 }[elegida])
    : F("Unidades: {0} (sin escalar: los números se quedan).", elegida), "bien");
};

/* La guía de herramientas en PDF (assets/ayuda, la arma build/hacer_guia.py).
 * En la app de escritorio se abre con el visor de PDF del sistema; en un
 * navegador, en otra pestaña. */
Comandos.registrar({
  nombre: "GUIA", alias: ["MANUAL", "GUIDE", "HERRAMIENTAS"],
  ayuda: "Abre la guía de herramientas en PDF: icono, nombre y qué hace cada una",
  correr: async () => {
    let r;
    try { r = await api("/api/ayuda/guia"); }
    catch (e) { avisar(e.message, true); return; }
    if (enElectron() && window.t101.abrirArchivo) {
      const err = await window.t101.abrirArchivo(r.ruta);
      if (err) { avisar(err, true); return; }
    } else {
      window.open(r.url, "_blank");
    }
    Comandos.eco(Tr("Guía de herramientas abierta."));
  },
});

Comandos.registrar({
  nombre: "UNIDADES", alias: ["UNITS", "UN"],
  ayuda: "Cambia la unidad de trabajo del dibujo: mm, cm o m",
  correr: (args) => Ajustes.unidades(args),
});

Comandos.registrar({
  nombre: "IDIOMA", alias: ["LANG"],
  ayuda: "Cambia el idioma de la interfaz: IDIOMA EN · IDIOMA ES",
  correr: async (args) => {
    const a = (args[0] || "").toLowerCase();
    if (a !== "en" && a !== "es") return Ajustes.general();
    await Idioma.cambiar(a);
  },
});

/* El menú Ayuda ▾ del encabezado. */
(() => {
  const b = $("#b-ayuda"), m = $("#menu-ayuda");
  if (!b || !m) return;
  const cerrar = () => { m.hidden = true; document.removeEventListener("mousedown", fuera, true); };
  const fuera = (e) => { if (!m.contains(e.target) && e.target !== b) cerrar(); };
  b.onclick = () => {
    if (!m.hidden) return cerrar();
    m.hidden = false;
    document.addEventListener("mousedown", fuera, true);
  };
  m.querySelectorAll("button[data-cmd]").forEach((x) => {
    x.onclick = () => { cerrar(); Comandos.correr(x.dataset.cmd); };
  });
})();

Comandos.registrar({
  nombre: "ODA", alias: ["INSTALARODA", "ODAINSTALAR"],
  ayuda: "Instalar o actualizar el ODA File Converter (convierte DWG más rápido y más fiel)",
  correr: () => Ajustes.oda(),
});

/* Ayuda ▾ → Licencias: lo ajeno que viaja dentro del programa y bajo qué
 * licencia. Las MIT/BSD/OFL piden justo esto: que el aviso llegue al usuario. */
Ajustes.licencias = async function () {
  const r = await fetch("/api/licencias").then((x) => x.json()).catch(() => ({ componentes: [] }));
  const comps = r.componentes || [];
  const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const filas = comps.map((c) =>
    `<tr><td><a href="#" data-lic="${esc(c.archivo)}">${esc(c.componente)}</a>` +
    (c.version ? ` <span class="v">${esc(c.version)}</span>` : "") +
    (c.nota ? `<div class="subpista">${esc(c.nota)}</div>` : "") +
    `</td><td class="lic">${esc(c.licencia)}</td></tr>`).join("");
  const tabla = `<table>${filas}</table>`;
  const texto = { tipo: "nota", clave: "texto", etiqueta: "", alto: true, valor: Tr("Elige un componente para ver el texto de su licencia.") };
  const cuadro = Dialogo.abrir({
    titulo: Tr("Licencias de terceros"),
    pista: Tr("shape101 lleva dentro estos componentes de otros. Cada uno viaja con su aviso de licencia, como pide cada licencia."),
    ancho: "640px",
    campos: [
      { tipo: "nota", clave: "lista", etiqueta: "", html: tabla },
      texto,
    ],
    aceptar: Tr("Cerrar"), cancelar: null,
  });
  const caja = document.querySelector(".dlg");
  if (caja) caja.querySelectorAll("a[data-lic]").forEach((a) => {
    a.onclick = async (e) => {
      e.preventDefault();
      const archivo = a.dataset.lic;
      if (archivo.endsWith(".html")) { window.open("/api/licencias/" + archivo, "_blank"); return; }
      const t = await fetch("/api/licencias/" + archivo).then((x) => x.text()).catch(() => "");
      const n = caja.querySelector('[data-clave="texto"]');
      if (n) { n.textContent = t || Tr("No se encontró el texto."); n.scrollTop = 0; }
    };
  });
  return cuadro;
};

Comandos.registrar({
  nombre: "LICENCIAS", alias: ["LICENSES", "TERCEROS", "CREDITOS"],
  ayuda: "Componentes de terceros que van dentro de shape101 y sus licencias",
  correr: () => Ajustes.licencias(),
});

Comandos.registrar({
  nombre: "MODOSREF", alias: ["REFCONF", "OSNAPCONF"],
  ayuda: "Cuadro con los modos de referencia a objetos",
  correr: Ajustes.referencias,
});

Comandos.registrar({
  nombre: "ESTILOCOTA", alias: ["DIMESTILO", "EC"],
  ayuda: "Altura del texto y tamaño de las flechas de las cotas",
  correr: Ajustes.estiloCota,
});
window.Ajustes = Ajustes;
