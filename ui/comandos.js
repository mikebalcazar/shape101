/* Línea de comando  ·  feature 17.
 *
 * Es la puerta por la que van a entrar todas las herramientas que faltan: una
 * herramienta se registra aquí con su nombre y sus alias y ya tiene teclado,
 * historial, cancelación con Escape y repetición con Enter, sin escribir nada
 * de eso otra vez. Por eso vale la pena que exista en F1, cuando todavía casi
 * no hay comandos que registrar.
 *
 * Los alias son los de AutoCAD a propósito. Quien dibuja lleva veinte años
 * tecleando `L` y `Z E`; obligarlo a aprender otros nombres no lo hace mejor
 * dibujante, sólo más lento.
 */

const Comandos = (() => {
  const registro = new Map();     // nombre → {nombre, alias, ayuda, correr}
  const porAlias = new Map();     // alias → nombre
  const historial = [];
  let iHist = -1;
  let ultimo = null;
  let corriendo = null;

  function registrar(cmd) {
    registro.set(cmd.nombre, cmd);
    porAlias.set(cmd.nombre, cmd.nombre);
    for (const a of cmd.alias || []) porAlias.set(a.toUpperCase(), cmd.nombre);
  }

  // Un comando se acepta en español o en inglés, siempre (ver Idioma.comando):
  // primero el nombre/alias tal cual, si no, su equivalente en inglés.
  const resolver = (txt) => {
    const k = String(txt).trim().toUpperCase();
    return registro.get(porAlias.get(k))
        || (typeof Idioma !== "undefined" ? registro.get(porAlias.get(Idioma.comando(k))) : undefined);
  };
  const existe = (txt) => !!resolver(txt);

  /** Atajos que inventó el usuario  ·  feature 80.
   *  Se aplican encima de los de fábrica y se vuelven a poner en cada arranque
   *  desde las preferencias, que es donde viven. */
  let atajosPropios = {};
  function aplicarAtajos(atajos) {
    for (const clave of Object.keys(atajosPropios)) porAlias.delete(clave);
    atajosPropios = { ...(atajos || {}) };
    for (const [clave, destino] of Object.entries(atajosPropios)) {
      const cmd = resolver(destino);
      if (cmd) porAlias.set(clave.toUpperCase(), cmd.nombre);
    }
  }

  /* La consola: dos renglones, o diez con el botoncito de la esquina o F2.
   * Se recuerda entre sesiones; abrirla cada vez sería una manía nueva. */
  function consolaAbierta(abierta) {
    const con = $("#consola");
    if (abierta === undefined) abierta = !con.classList.contains("abierta");
    con.classList.toggle("abierta", abierta);
    const b = $("#cmd-mas");
    if (b) b.title = abierta ? "Ver menos líneas (F2)" : "Ver más líneas de la consola (F2)";
    try { localStorage.setItem("consola_abierta", abierta ? "1" : "0"); } catch (_) {}
    const caja = $("#cmd-historial");
    caja.scrollTop = caja.scrollHeight;
    if (typeof ajustarLienzo === "function") ajustarLienzo();
    return abierta;
  }
  try { if (localStorage.getItem("consola_abierta") === "1") $("#consola").classList.add("abierta"); } catch (_) {}
  const _bMas = $("#cmd-mas");
  if (_bMas) _bMas.onclick = () => { consolaAbierta(); $("#cmd").focus(); };

  function eco(texto, clase = "") {
    const caja = $("#cmd-historial");
    const linea = document.createElement("div");
    linea.className = "eco " + clase;
    linea.textContent = texto;
    caja.appendChild(linea);
    while (caja.childElementCount > 200) caja.firstElementChild.remove();
    caja.scrollTop = caja.scrollHeight;
  }

  function pedir(mensaje) {
    $("#cmd-etiqueta").textContent = mensaje + ":";
    // Mientras se pide un punto, la pista deja de ser la lista de comandos:
    // lo que toca teclear ahí son coordenadas.
    $("#cmd").placeholder = "100,50 · @100,50 · @100<45 · o clic en el dibujo";
  }

  function terminar() {
    $("#cmd-etiqueta").textContent = "Comando:";
    $("#cmd").placeholder = "Z E · MD · REF · AYUDA";
    corriendo = null;
  }

  async function correr(texto) {
    const partes = String(texto).trim().split(/\s+/);
    const cmd = resolver(partes[0]);
    if (!cmd) {
      eco(`Comando desconocido: ${partes[0]}. Teclea AYUDA para la lista.`, "malo");
      return;
    }
    ultimo = texto.trim();
    eco("› " + ultimo);
    corriendo = cmd.nombre;
    // El icono de la herramienta junto al cursor mientras el comando dure
    // (ui/iconos.js). Una herramienta puede cambiarlo a medio camino.
    estado.cursorIcono = (typeof Iconos !== "undefined" && Iconos.POR_COMANDO[cmd.nombre]) || null;
    try {
      await cmd.correr(partes.slice(1));
    } catch (err) {
      // Cancelar con Escape es normal, no es un error que reportar.
      if (err && err.message && err.message !== "cancelado") eco(err.message, "malo");
      else eco("Cancelado.");
    } finally {
      estado.cursorIcono = null;
      if (typeof pintar === "function") pintar();
      terminar();
    }
  }

  /* --- El campo de texto ------------------------------------------------ */
  function conectar() {
    const campo = $("#cmd");

    campo.addEventListener("keydown", async (e) => {
      if (e.key === "Escape") {
        campo.value = "";
        if (Entrada.activa) Entrada.cancelar("escape");
        if (Entrada.esperandoTexto) Entrada.cancelarTexto();
        if (Seleccion.pidiendo) Seleccion.alTeclear(e);
        terminar();
        return;
      }
      // Supr con la caja vacía borra lo seleccionado. Con texto escrito, no:
      // ahí Supr es lo que hace en cualquier caja de texto.
      if (e.key === "Delete" && !campo.value && estado.sel.size && !Seleccion.pidiendo) {
        e.preventDefault();
        correr("BORRAR");
        return;
      }
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault();
        if (!historial.length) return;
        iHist = e.key === "ArrowUp"
          ? Math.min(historial.length - 1, iHist + 1)
          : Math.max(-1, iHist - 1);
        campo.value = iHist < 0 ? "" : historial[historial.length - 1 - iHist];
        return;
      }
      // **El espacio confirma, igual que Enter.** Es la costumbre de AutoCAD y
      // el dedo la tiene hecha: se dibuja con la izquierda en el espacio y la
      // derecha en el ratón, sin cruzar el teclado para buscar el Enter.
      //
      // Una excepción, y es la que importa: cuando una herramienta está pidiendo
      // **texto libre** —el contenido de un rótulo, el nombre de una capa o de
      // un bloque— el espacio es un espacio. «MESA DE TRABAJO» tiene que poder
      // escribirse. Se sabe por lo que el programa está esperando, no
      // adivinando por el contenido. Cuando pide un **número** (distancia del
      // desfase, radio) el espacio confirma: ahí un espacio no sirve de nada
      // (Mike, 7-sep-2026).
      //
      // El costo, dicho para que no sorprenda: los comandos que aceptan
      // argumentos en la misma línea —`ZOOM 2`— ya no se pueden rematar con
      // espacio, porque el espacio los dispara antes. Para ésos, Enter. Es el
      // mismo trato que hace AutoCAD, donde los argumentos se contestan a la
      // pregunta siguiente y no en la misma línea.
      const confirma = e.key === "Enter" || (e.key === " " && !Entrada.esperandoTextoLibre);
      if (!confirma) return;

      e.preventDefault();
      const texto = campo.value.trim();
      campo.value = "";
      iHist = -1;

      // Enter en vacío mientras se selecciona cierra la selección, no repite
      // el comando: es lo que hace AutoCAD y lo que espera el dedo.
      if (Seleccion.pidiendo && !texto) { Seleccion.alTeclear({ key: "Enter" }); return; }

      // Si una herramienta está preguntando algo, lo tecleado es la respuesta.
      if (Entrada.esperandoTexto) {
        eco("› " + (texto || "(por omisión)"));
        Entrada.textoRecibido(texto);
        return;
      }

      // Si una herramienta está esperando un punto, lo tecleado son
      // coordenadas, no un comando.  ·  feature 16
      if (Entrada.activa) {
        // **Enter (o espacio) en vacío termina el comando.** Es la costumbre
        // de AutoCAD y lo que espera el dedo: se trazan tres líneas, se
        // remata con Enter y se acabó. Antes no hacía nada y la herramienta
        // se quedaba abierta encadenando desde el último punto, que es lo que
        // reportó Mike.
        //
        // Termina *el pedido de punto*, no la herramienta: por eso una
        // polilínea se cierra y se crea con lo que lleva, en vez de perderse.
        // Cada herramienta ya sabe qué hacer cuando se le acaban los puntos.
        // Con una medida ya fijada, Enter en vacío no cancela: confirma con la
        // dirección que tenga el cursor. Cancelar ahí sería tirar el número
        // que la persona acaba de teclear.
        if (!texto) {
          if (Entrada.largoFijo) Entrada.entregar(Entrada.puntoDelCursor());
          else Entrada.cancelar("enter");
          return;
        }
        if (Entrada.opcionTecleada(texto)) { eco("› " + texto); return; }
        // Un número que es la respuesta (el factor de ESCALAR), no un punto.
        if (Entrada.numeroTecleado(texto)) { eco("› " + texto); return; }
        // Una medida a secas, donde la dirección importa, se fija y espera el
        // clic que la apunta.  ·  ver `Entrada.fijarLargo`
        if (Entrada.fijarLargo(texto)) { eco("› " + texto); return; }
        const p = Entrada.parsearCoordenadas(texto, Entrada.base);
        if (p) { eco("› " + texto); Entrada.entregar(p); }
        else eco(`No entendí «${texto}». Usa 100,50 · @100,50 · 100<45 · @100<45`, "malo");
        return;
      }

      if (!texto) {                       // Enter en vacío repite el último
        if (ultimo) await correr(ultimo);
        return;
      }
      historial.push(texto);
      await correr(texto);
    });

    window.addEventListener("keyup", (e) => {
      if (e.key !== " " || Entrada.esperandoTextoLibre) return;
      const et0 = document.activeElement.tagName;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(et0)) return;
      if (typeof Dialogo !== "undefined" && Dialogo.activo()) return;
      if (window.__espacioArrastro) { window.__espacioArrastro = false; return; }
      campo.dispatchEvent(new KeyboardEvent("keydown",
        { key: "Enter", bubbles: false, cancelable: true }));
    });

    // Teclear en cualquier parte escribe en la línea de comando, como en
    // AutoCAD. Salvo cuando el foco está en un campo de verdad.
    window.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      // Con un cuadro de diálogo abierto, el teclado es suyo. Sin esto, un
      // Enter dentro del cuadro llegaba también a la toma de puntos que había
      // detrás, y una tecla suelta robaba el foco para la línea de comandos.
      if (typeof Dialogo !== "undefined" && Dialogo.activo()) return;

      // Lo que se teclea EN la línea de comando ya lo atendió el manejador de
      // arriba. Volver a mirarlo aquí producía un error feo y difícil de ver:
      // el Enter que contestaba «20» a una pregunta llegaba también, un
      // instante después, a la selección que esa misma respuesta acababa de
      // abrir, y la cerraba vacía.
      if (e.target === campo) return;

      // Enter y espacio con el foco en el lienzo confirman igual que en la
      // caja: quien dibuja tiene la mano en el ratón y no debería tener que
      // picar la línea de comando para rematar. De paso, el espacio deja de
      // desplazar la página, que es lo que hace en un navegador.
      //
      // Sin esto, el Enter que cierra una línea no llegaba a ninguna parte si
      // el último clic había sido en el lienzo — que es siempre.
      //
      // **El espacio confirma al soltarlo, no al apretarlo.** Sostenido y
      // arrastrando con el ratón es el pan de la laptop (ver `esPan` en
      // vista.js): si confirmara al apretar, cada arrastre remataría el
      // comando que estuviera abierto. Se confirma al soltar sólo si no hubo
      // arrastre en medio. Un toque de espacio se siente igual que antes.
      if (e.key === "Enter" || (e.key === " " && !Entrada.esperandoTextoLibre)) {
        const et0 = document.activeElement.tagName;
        if (!["INPUT", "SELECT", "TEXTAREA"].includes(et0)) {
          e.preventDefault();
          if (e.key === " ") { if (!e.repeat) window.__espacioArrastro = false; return; }
          campo.dispatchEvent(new KeyboardEvent("keydown",
            { key: "Enter", bubbles: false, cancelable: true }));
          return;
        }
      }

      if (Entrada.alTeclear(e)) return;
      if (Seleccion.alTeclear(e)) return;
      const et = document.activeElement.tagName;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(et)) return;
      if (e.key.length === 1 || e.key === "Backspace") {
        campo.focus();
      } else if (e.key === "Escape") {
        if (Entrada.activa) Entrada.cancelar("escape");
        if (Entrada.esperandoTexto) Entrada.cancelarTexto();
        $("#aviso").classList.remove("si");
      }
    });
  }

  return { registrar, correr, pedir, terminar, eco, conectar, existe, aplicarAtajos, consolaAbierta,
           get lista() { return [...registro.values()]; },
           get corriendo() { return corriendo; } };
})();


/* ===================================================================== */
/* Los comandos de F1                                                     */
/* ===================================================================== */

const sion = (v) => (v ? "encendido" : "apagado");

function interruptor(clave, args, etiqueta) {
  const v = (args[0] || "").toUpperCase();
  const nuevo = v === "ON" || v === "SI" ? true
    : v === "OFF" || v === "NO" ? false
    : !estado.prefs[clave];
  guardarPrefs({ [clave]: nuevo });
  Comandos.eco(`${etiqueta}: ${sion(nuevo)}`);
}

Comandos.registrar({
  nombre: "ZOOM", alias: ["Z"],
  ayuda: "ZOOM [E extensión · V ventana · P previo · factor]",
  correr: async (args) => {
    const op = (args[0] || "E").toUpperCase();
    if (op === "E" || op === "EXT") return encuadrar();
    if (op === "P" || op === "PREVIO") return vistaPrevia();
    if (op === "V" || op === "VENTANA") {
      Comandos.pedir("Primera esquina de la ventana");
      return iniciarZoomVentana();
    }
    const f = parseFloat(op);
    if (isFinite(f) && f > 0) {
      // Se apunta la vista antes de saltar. La rueda no lo hace —apuntaría una
      // vista por muesca y ZOOM P dejaría de servir para nada.
      recordarVista();
      return zoomEn(lienzo.clientWidth / 2, lienzo.clientHeight / 2, f);
    }
    Comandos.eco("ZOOM: usa E (extensión), V (ventana), P (previo) o un factor.", "malo");
  },
});

Comandos.registrar({
  nombre: "ENCUADRAR", alias: ["ZE", "EX"],
  ayuda: "Encuadra todo el dibujo",
  correr: async () => encuadrar(),
});

Comandos.registrar({
  nombre: "PAN", alias: ["P"],
  ayuda: "Mueve la vista (o arrastra con el botón central o derecho)",
  correr: async () => Comandos.eco("Arrastra con el botón central, el derecho, o Shift+izquierdo."),
});

/* REGEN, como en AutoCAD: redibujar fino y rehacer el índice, sin ir al motor.
 * REGENERAR (REGENALL) además vuelve a pedir el dibujo entero al motor: es el
 * martillo grande, para cuando algo se ve mal y no se sabe por qué. */
Comandos.registrar({
  nombre: "REGEN", alias: ["RE", "REDIBUJAR"],
  ayuda: "Redibuja el plano fino y rehace el índice (como REGEN de AutoCAD)",
  correr: async () => {
    const t = performance.now();
    Regen.forzar();
    Comandos.eco(`Regenerado en ${(performance.now() - t).toFixed(0)} ms.`);
  },
});

Comandos.registrar({
  nombre: "REGENERAR", alias: ["REGENALL", "REA"],
  ayuda: "Vuelve a pedir el dibujo entero al motor y lo redibuja",
  correr: async () => { await recargarTrazos(); Regen.forzar(); Comandos.eco("Regenerado desde el motor."); },
});

/* RENDIMIENTO: medir en **esta** máquina lo que cuesta pintar y navegar.
 *
 * Lo que va lento en la laptop de Mike no se ve desde el servidor de pruebas:
 * ahí un cuadro cuesta 14 ms y aquí puede costar 90. Este comando mide en la
 * máquina donde duele y escribe un informe en la consola, para pegarlo tal
 * cual en el reporte. Sin adivinar. */
Comandos.registrar({
  nombre: "RENDIMIENTO", alias: ["PERF", "MEDIR"],
  ayuda: "Mide cuánto cuesta pintar y navegar en esta máquina, para diagnosticar",
  correr: async () => {
    const r = [];
    const dpr = window.devicePixelRatio || 1;
    let gpu = "?";
    try {
      const g = document.createElement("canvas").getContext("webgl");
      const inf = g && g.getExtension("WEBGL_debug_renderer_info");
      if (inf) gpu = g.getParameter(inf.UNMASKED_RENDERER_WEBGL);
    } catch (_) { /* sin WebGL: da igual */ }
    let verts = 0, dentro = 0, manchas = 0, textos = 0;
    const esc = estado.vista.escala, vx = estado.vista.x, vy = estado.vista.y;
    const w = lienzo.clientWidth / esc, h = lienzo.clientHeight / esc;
    for (const t of estado.trazos) {
      const bb = cajaTrazo(t);
      if (bb[2] < vx || bb[0] > vx + w || bb[3] < vy - h || bb[1] > vy) continue;
      dentro++;
      if (t.clase === "texto") { textos++; continue; }
      if ((bb[2] - bb[0]) * esc < 1.2 && (bb[3] - bb[1]) * esc < 1.2) manchas++;
      else verts += (t.puntos || []).length;
    }
    r.push(`shape101 ${(estado.version || {}).version || ""} · ${navigator.platform} · ${navigator.hardwareConcurrency || "?"} núcleos`);
    r.push(`gráfica: ${gpu}`);
    r.push(`lienzo: ${lienzo.clientWidth}×${lienzo.clientHeight} css · ×${dpr} = ${lienzo.width}×${lienzo.height} px`);
    r.push(`plano: ${estado.trazos.length} trazos · ${estado.geometria.length} primitivas · en pantalla ${dentro} (${manchas} manchas, ${textos} textos, ${verts} vértices) · zoom ${Math.round(esc * 100)}%`);
    const medir = (veces, f) => {
      const ts = [];
      for (let i = 0; i < veces; i++) { const t0 = performance.now(); f(); ts.push(performance.now() - t0); }
      ts.sort((a, b) => a - b);
      return `${ts[Math.floor(ts.length / 2)].toFixed(1)} ms (mín ${ts[0].toFixed(1)}, máx ${ts[ts.length - 1].toFixed(1)})`;
    };
    r.push(`pintar el plano completo: ${medir(5, () => { invalidarPlano(); pintarYa(); })}`);
    r.push(`sólo lo de encima (selección, mira): ${medir(5, () => pintarYa())}`);
    {
      Regen.gesto();
      const v0 = { ...estado.vista };
      r.push(`navegar sobre la foto (pan): ${medir(5, () => { estado.vista.x += 3 / esc; pintarYa(); })}`);
      estado.vista = v0;
      Regen.terminarGesto();
    }
    r.push(`índice: rehacer ${medir(1, () => Indice.rehacer())}`);
    r.push(`selección: candidatos bajo el cursor ${medir(5, () => Seleccion.candidatos([vx + w / 2, vy - h / 2]))}`);
    r.push(`regen: umbral ${Regen.UMBRAL_MS} ms · último pintado ${Regen.costo.toFixed(1)} ms · ${Regen.costo >= Regen.UMBRAL_MS ? "navegando sobre la foto" : "pintando directo"} · fotos ${Regen.contador.fotos}, regens ${Regen.contador.regens}`);
    // Los cuadros lentos que se anotaron solos desde que se abrió el plano
    // (ver Diag en vista.js): es la pista cuando «se puso lentísimo» pasó
    // hace un rato y aquí no se reproduce.
    // Y las llamadas al motor que tardaron o que obligaron a recargar todo
    // (ver DiagApi en base.js): es la otra mitad del «se puso lentísimo».
    if (typeof DiagApi !== "undefined" && DiagApi.llamadas.length) {
      const recargas = DiagApi.llamadas.filter((l) => l.recarga).length;
      r.push(`llamadas al motor lentas (> ${DiagApi.umbral} ms) o con recarga completa: ${DiagApi.llamadas.length} (recargas completas: ${recargas})`);
      for (const l of DiagApi.llamadas.slice(-12)) {
        r.push(`   · ${new Date(l.t).toLocaleTimeString()} ${l.ruta} ${l.ms.toFixed(0)} ms · ${l.kb} KB${l.recarga ? " · RECARGA COMPLETA" : ""}`);
      }
    }
    if (typeof Diag !== "undefined" && Diag.cuadros.length) {
      r.push(`cuadros lentos anotados (> ${Diag.umbral} ms): ${Diag.cuadros.length}`);
      for (const c of Diag.cuadros.slice(-12)) {
        const hora = new Date(c.t).toLocaleTimeString();
        r.push("   · " + hora + " " + Object.entries(c).filter(([k]) => k !== "t")
          .map(([k, v]) => `${k} ${typeof v === "number" ? v.toFixed(1) : v}`).join(" · "));
      }
    } else r.push("cuadros lentos anotados: ninguno");
    for (const l of r) Comandos.eco(l);
    try { await navigator.clipboard.writeText(r.join("\n")); Comandos.eco("(copiado al portapapeles: pégalo en el reporte)", "bien"); } catch (_) {}
    invalidarPlano(); pintar();
  },
});

Comandos.registrar({
  nombre: "DIAG", alias: ["DIAGNOSTICO"],
  ayuda: "DIAG [ON · OFF] — anuncia en la consola cada cuadro o movimiento del ratón que tarde de más",
  correr: async (args) => {
    const a = (args[0] || "").toUpperCase();
    Diag.activo = a === "ON" ? true : a === "OFF" ? false : !Diag.activo;
    Comandos.eco(`Diagnóstico ${Diag.activo ? "encendido: se avisará cada cuadro lento" : "apagado"}. PERF enseña los últimos anotados.`);
  },
});

Comandos.registrar({
  nombre: "REJILLA", alias: ["GRID", "F7"],
  ayuda: "REJILLA [ON · OFF · paso en mm]",
  correr: async (args) => {
    const n = parseFloat(args[0]);
    if (isFinite(n) && n > 0) {
      await guardarPrefs({ rejilla_paso: n, rejilla: true });
      return Comandos.eco(`Rejilla de ${mm(n)} mm.`);
    }
    interruptor("rejilla", args, "Rejilla");
  },
});

Comandos.registrar({
  nombre: "BORRADOR", alias: ["DRAFT", "BORR"],
  ayuda: "BORRADOR [ON · OFF] — modo borrador: líneas de 1 px, sin patrones, textos como cajas (más ligero)",
  correr: async (args) => {
    interruptor("borrador", args, "Modo borrador");
    Regen.olvidar(); invalidarPlano(); pintar();
  },
});

Comandos.registrar({
  nombre: "SNAP", alias: ["F9"],
  ayuda: "SNAP [ON · OFF · paso en mm] — forzar el cursor a la rejilla",
  correr: async (args) => {
    const n = parseFloat(args[0]);
    if (isFinite(n) && n > 0) {
      await guardarPrefs({ snap_paso: n, snap_rejilla: true });
      return Comandos.eco(`Snap de ${mm(n)} mm.`);
    }
    interruptor("snap_rejilla", args, "Snap de rejilla");
  },
});

Comandos.registrar({
  nombre: "ORTHO", alias: ["OR", "F8"],
  ayuda: "ORTHO [ON · OFF] — obliga a horizontal o vertical",
  correr: async (args) => interruptor("ortho", args, "Ortho"),
});

Comandos.registrar({
  nombre: "REFERENCIAS", alias: ["REF", "OSNAP", "F3"],
  ayuda: "REF [ON · OFF · modo] — referencias a objetos",
  correr: async (args) => {
    const m = (args[0] || "").toLowerCase();
    if (m && estado.modosOsnap[m]) {
      const modos = { ...estado.prefs.osnap_modos, [m]: !estado.prefs.osnap_modos[m] };
      await guardarPrefs({ osnap_modos: modos, osnap: true });
      return Comandos.eco(`${estado.modosOsnap[m]}: ${sion(modos[m])}`);
    }
    if (m) {
      return Comandos.eco("Modos: " + Object.keys(estado.modosOsnap).join(", "), "malo");
    }
    interruptor("osnap", args, "Referencias a objetos");
  },
});

Comandos.registrar({
  nombre: "DINAMICA", alias: ["DIN"],
  ayuda: "DIN [ON · OFF] — entrada dinámica junto al cursor",
  correr: async (args) => interruptor("dinamica", args, "Entrada dinámica"),
});

Comandos.registrar({
  nombre: "TEMA",
  ayuda: "Cambia entre claro y oscuro",
  correr: async () => cambiarTema(),
});

/* MEDIR es la feature 75, adelantada de F9 a propósito: es el consumidor más
 * simple del selector de punto, y sin un consumidor no hay forma de probar que
 * el osnap, el ortho y la entrada dinámica funcionan de verdad. Vale más
 * adelantarla que escribir una herramienta de mentiras sólo para la prueba. */
Comandos.registrar({
  nombre: "MEDIR", alias: ["MD", "DIST", "DI"],
  ayuda: "Mide la distancia entre dos puntos",
  correr: async () => {
    const a = await Entrada.pedirPunto({ mensaje: "Primer punto" });
    const b = await Entrada.pedirPunto({
      mensaje: "Segundo punto", base: a,
      hule: (p) => ({ tipo: "linea", a, b: p }),
    });
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const d = Math.hypot(dx, dy);
    const ang = Math.atan2(dy, dx) * 180 / Math.PI;
    const texto = `Distancia ${mm(d)} ${U()} · ΔX ${mm(dx)} · ΔY ${mm(dy)} · ángulo ${grados(ang)}°`;
    Comandos.eco(texto, "bien");
    avisar(texto, false, 8000);
    return d;
  },
});

Comandos.registrar({
  nombre: "AYUDA", alias: ["?", "H"],
  ayuda: "Lista los comandos",
  correr: async () => {
    for (const c of Comandos.lista) {
      // En inglés, el nombre inglés primero y el español entre los alias.
      const en = Idioma.nombreComando(c.nombre);
      const alias = [...(en !== c.nombre ? [c.nombre] : []), ...(c.alias || [])];
      const sufijo = alias.length ? `  (${alias.join(", ")})` : "";
      Comandos.eco(`${en}${sufijo} — ${Tr(c.ayuda || "")}`);
    }
  },
});

Comandos.registrar({
  nombre: "VERSION", alias: ["VER", "ACERCADE"],
  ayuda: "Qué versión es ésta y qué trajo",
  correr: async () => {
    const r = estado.version || await fetch("/api/version").then((x) => x.json());
    estado.version = r;
    Comandos.eco(`shape101 ${r.version} · ${r.fecha} · Taller 101`, "bien");
    for (const e of (r.bitacora || []).slice(0, 2)) {
      if (e.version !== r.version) Comandos.eco(`— antes, ${e.version} (${e.fecha}):`);
      for (const c of e.cambios) Comandos.eco("   · " + c);
    }
  },
});

/* --- Teclas de función -------------------------------------------------- */
window.addEventListener("keydown", (e) => {
  const teclas = { F3: "REFERENCIAS", F7: "REJILLA", F8: "ORTHO", F9: "SNAP" };
  if (e.key === "F2") { e.preventDefault(); Comandos.consolaAbierta(); return; }
  if (teclas[e.key]) {
    e.preventDefault();
    Comandos.correr(teclas[e.key]);
  }
});
