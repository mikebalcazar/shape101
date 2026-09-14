/* Actualizaciones y avisos de Taller 101  ·  0.19.2
 *
 * Mike (7-sep-2026): un checador de versiones, y «alguna forma de mandar
 * comunicación a los usuarios… que el software siempre revise un registro».
 *
 * Los dos leen el sitio fijo de Taller 101 (core/actualizar.py, core/avisos.py):
 * al arrancar, unos segundos después de que la interfaz ya está lista, y luego
 * cada 24 h (versiones) / 6 h (avisos) mientras la app siga abierta. Nada de
 * esto estorba: si el sitio no contesta en 5 s, no pasa nada y no se dice nada.
 *
 * Bajar e instalar siempre lo decide el usuario. La descarga la hace el motor
 * en un hilo; aquí sólo se enseña el avance y, al final, se pregunta si
 * instala ahora (shape101 se cierra y el instalador toma el relevo).
 */

/* Tr traduce cadenas ya armadas (el diccionario tiene las plantillas con
 * «{0}»): primero se rellena, luego se traduce. */
const F = (texto, ...args) => Tr(String(texto).replace(/\{(\d)\}/g, (_, i) => args[+i] ?? ""));

const Actualizar = (() => {
  let vigilando = null;
  let ofrecidaEnSesion = "";

  function notas(ult) {
    const n = (ult && ult.notas) || [];
    return n.length ? n.map((x) => "· " + x).join("\n") : "";
  }

  function vigilar(alTerminar) {
    if (vigilando) return;
    vigilando = setInterval(async () => {
      let e;
      try { e = await api("/api/actualizacion/estado"); } catch (_) { return; }
      if (e.fase === "descargando" || e.fase === "comprobando") {
        avisar(e.mensaje, false, 0);
        return;
      }
      clearInterval(vigilando); vigilando = null;
      if (e.fase === "listo") {
        avisar(e.mensaje, false, 6000);
        if (alTerminar) alTerminar(e);
      } else if (e.fase === "error") {
        avisar(e.mensaje, true, 12000);
        Comandos.eco(e.mensaje, "mal");
      }
    }, 600);
  }

  async function instalarBajada(e) {
    const v = await Dialogo.abrir({
      titulo: F("Instalar shape101 {0}", e.version),
      pista: Tr("El instalador ya está bajado y comprobado. Para instalarlo shape101 se cierra; guarda tus cambios antes. El instalador quita la versión anterior solo.") +
             (e.ruta ? "\n" + e.ruta : ""),
      campos: [],
      aceptar: Tr("Instalar ahora"), cancelar: Tr("Después"),
    });
    if (!v) return;
    const sucios = typeof cuantosSucios === "function" ? cuantosSucios() : (estado.sucio ? 1 : 0);
    if (sucios) {
      const s = await Dialogo.abrir({
        titulo: Tr("Hay cambios sin guardar"),
        pista: Tr("Guarda primero (GUARDAR) y vuelve a pedir la instalación con ACTUALIZAR, o instala de todos modos y pierde los cambios."),
        campos: [], aceptar: Tr("Instalar y perder los cambios"), cancelar: Tr("Guardar primero"),
      });
      if (!s) return;
    }
    let r;
    try { r = await post("/api/actualizacion/instalar", {}); }
    catch (err) { avisar(err.message, true, 8000); return; }
    if (!r.lanzado) {
      avisar(F("El instalador quedó en {0}. Ábrelo a mano.", r.ruta), false, 12000);
      return;
    }
    Comandos.eco(F("Instalando shape101 {0}. La aplicación se cierra…", e.version), "bien");
    setTimeout(() => {
      if (enElectron() && window.t101.cerrar) window.t101.cerrar(0);
    }, 600);
  }

  async function bajar(ult) {
    let e;
    try { e = await post("/api/actualizacion/bajar", {}); }
    catch (err) { avisar(err.message, true, 8000); return; }
    if (e.abrir) { window.open(e.abrir, "_blank"); return; }
    if (e.fase === "listo") { instalarBajada(e); return; }
    avisar(F("Bajando shape101 {0}…", ult.version), false, 0);
    vigilar(instalarBajada);
  }

  /** Enseña el cuadro. `silencio`: sólo si hay versión nueva y no está ignorada. */
  async function revisar({ silencio = false, forzar = false } = {}) {
    let r;
    try { r = await api(`/api/actualizacion?red=1&forzar=${forzar ? 1 : 0}`); }
    catch (err) { if (!silencio) avisar(err.message, true); return null; }
    const ult = r.ultimo;
    if (silencio) {
      if (!r.hay_nueva || r.ignorada || ofrecidaEnSesion === ult.version) return r;
      ofrecidaEnSesion = ult.version;
      Comandos.eco(F("Hay una versión nueva de shape101: {0} (tienes la {1}). Teclea ACTUALIZAR.", ult.version, r.actual), "bien");
      // Y un letrero que sí se ve (Mike, 9-sep-2026: «muchas veces ni me
      // avisa»): una línea en la consola no es un aviso. Se queda hasta que
      // se conteste; no tapa el dibujo ni pide nada mientras tanto.
      letrero(r);
      return r;
    }
    if (r.estado && (r.estado.fase === "descargando" || r.estado.fase === "comprobando")) {
      avisar(r.estado.mensaje, false, 0); vigilar(instalarBajada); return r;
    }
    if (r.estado && r.estado.fase === "listo" && r.hay_nueva && r.estado.version === ult.version) {
      instalarBajada(r.estado); return r;
    }
    const lineas = [F("Tienes shape101 {0}.", r.actual)];
    if (!r.consulto) lineas.push(Tr("No se pudo consultar el sitio de Taller 101 (¿sin internet?)."));
    else if (!r.hay_nueva) lineas.push(Tr("Es la última versión."));
    else {
      lineas.push(F("Hay una versión nueva: {0} ({1}).", ult.version, ult.fecha || ""));
      const n = notas(ult);
      if (n) lineas.push(n);
      if (ult.bytes) lineas.push(F("Descarga de {0} MB; se comprueba con su huella antes de instalar.", Math.round(ult.bytes / 1e6)));
    }
    if (!r.se_puede_instalar && r.hay_nueva) lineas.push(Tr("Desde aquí no se instala en este sistema; se abre la página de descarga."));
    const campos = [];
    if (r.hay_nueva) campos.push({ clave: "ignorar", etiqueta: F("No volver a avisar de la {0}", ult.version), tipo: "casilla", valor: false });
    campos.push({ clave: "auto", etiqueta: Tr("Buscar actualizaciones al arrancar"), tipo: "casilla", valor: r.auto !== false });
    const v = await Dialogo.abrir({
      titulo: Tr("Actualizaciones de shape101"),
      pista: lineas.join("\n"),
      campos,
      aceptar: r.hay_nueva ? (r.se_puede_instalar ? F("Bajar {0}", ult.version) : Tr("Abrir la descarga")) : Tr("Cerrar"),
      cancelar: r.hay_nueva ? Tr("Ahora no") : null,
    });
    if (!v) return r;
    if (v.auto !== (r.auto !== false)) await guardarPrefs({ actualizaciones_auto: !!v.auto });
    if (r.hay_nueva && v.ignorar) { await post("/api/actualizacion/ignorar", { version: ult.version }); return r; }
    if (!r.hay_nueva) return r;
    if (!r.se_puede_instalar) { window.open(ult.pagina || (ult.partes && ult.partes[0]) || ult.url || "", "_blank"); return r; }
    await bajar(ult);
    return r;
  }

  /* El letrero de versión nueva: arriba del lienzo, con sus dos botones. */
  function letrero(r) {
    const ult = r.ultimo;
    let el = document.getElementById("letrero-version");
    if (el) el.remove();
    el = document.createElement("div");
    el.id = "letrero-version";
    const txt = document.createElement("span");
    txt.textContent = F("Hay una versión nueva de shape101: {0} (tienes la {1}).", ult.version, r.actual);
    const b1 = document.createElement("button");
    b1.className = "pri";
    b1.textContent = r.se_puede_instalar ? F("Actualizar a {0}", ult.version) : Tr("Ver la descarga");
    b1.onclick = () => { el.remove(); revisar({ forzar: false }); };
    const b2 = document.createElement("button");
    b2.className = "gh";
    b2.textContent = Tr("Después");
    b2.onclick = () => el.remove();
    el.append(txt, b1, b2);
    const caja = document.getElementById("lienzo-caja") || document.body;
    caja.appendChild(el);
  }

  /* La revisión al arrancar: el motor ya consulta el sitio en su hilo desde
   * que arranca (core/actualizar.py); aquí sólo se lee lo que trajo. Se
   * pregunta a los 3 s y, si todavía no había contestado, cada 20 s durante
   * los primeros 10 minutos; luego cada 6 h. */
  function programar() {
    const H = 3600 * 1000;
    let intentos = 0;
    const tick = async () => {
      const prefs = estado.prefs || {};
      let r = null;
      if (prefs.actualizaciones_auto !== false) r = await revisar({ silencio: true });
      if (r && r.consulto) {
        await Avisos.revisar();
        return;
      }
      if (++intentos < 30) Actualizar.temporizadores.push(setTimeout(tick, 20000));
    };
    Actualizar.temporizadores = [
      setTimeout(tick, 3000),
      setInterval(() => { const p = estado.prefs || {}; if (p.actualizaciones_auto !== false) revisar({ silencio: true }); }, 6 * H),
      setInterval(() => Avisos.revisar(), 6 * H),
    ];
  }

  return { revisar, vigilar, letrero, programar };
})();

/* --- Avisos de Taller 101 ----------------------------------------------- */
const Avisos = (() => {
  let ultimoResumen = null;

  function marcarMenu(n) {
    const b = $("#b-ayuda");
    if (!b) return;
    b.classList.toggle("con-avisos", n > 0);
    b.title = n > 0 ? F("{0} aviso(s) nuevo(s) de Taller 101", n) : Tr("Ayuda y configuración");
  }

  function texto(a) {
    const en = Idioma.actual === "en" && a.en ? a.en : null;
    return { titulo: (en && en.titulo) || a.titulo, texto: (en && en.texto) || a.texto };
  }

  function html(avisos) {
    const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    if (!avisos.length) return `<div class="vacio">${esc(Tr("No hay avisos."))}</div>`;
    return avisos.map((a) => {
      const t = texto(a);
      return `<div class="aviso-t101${a.leido ? "" : " nuevo"}${a.nivel === "importante" ? " importante" : ""}">` +
        `<div class="cab"><b>${esc(t.titulo)}</b><span class="fecha">${esc(a.fecha)}</span></div>` +
        `<div class="cuerpo">${esc(t.texto)}</div>` +
        (a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(Tr("Leer más"))}</a>` : "") +
        `</div>`;
    }).join("");
  }

  async function abrir({ solo = null } = {}) {
    let r;
    try { r = await api("/api/avisos?red=1"); }
    catch (err) { avisar(err.message, true); return; }
    ultimoResumen = r;
    const lista = solo ? r.avisos.filter((a) => solo.includes(a.id)) : r.avisos;
    await Dialogo.abrir({
      titulo: Tr("Avisos de Taller 101"),
      pista: r.consulto ? "" : Tr("No se pudo consultar el sitio de Taller 101 (¿sin internet?)."),
      ancho: "560px",
      campos: [{ tipo: "nota", clave: "avisos", etiqueta: "", html: html(lista) }],
      aceptar: Tr("Cerrar"), cancelar: null,
    });
    if (lista.some((a) => !a.leido)) {
      try { await post("/api/avisos/leidos", { ids: lista.map((a) => a.id) }); } catch (_) { /* nada */ }
      marcarMenu(r.avisos.filter((a) => !a.leido && !lista.includes(a)).length);
    }
  }

  /** Al arrancar y cada 6 h: marca el menú; los importantes salen solos. */
  async function revisar() {
    let r;
    try { r = await api("/api/avisos?red=1"); } catch (_) { return; }
    ultimoResumen = r;
    marcarMenu(r.nuevos);
    if (r.nuevos) Comandos.eco(F("{0} aviso(s) nuevo(s) de Taller 101. Teclea AVISOS o abre Ayuda ▾.", r.nuevos));
    if (r.importantes_nuevos && r.importantes_nuevos.length) {
      await abrir({ solo: r.importantes_nuevos.map((a) => a.id) });
    }
  }

  return { abrir, revisar, get resumen() { return ultimoResumen; } };
})();

Comandos.registrar({
  nombre: "ACTUALIZAR", alias: ["UPDATE", "ACTUALIZACIONES", "UPDATES"],
  ayuda: "Busca si hay una versión nueva de shape101 y la baja e instala",
  correr: () => Actualizar.revisar({ forzar: true }),
});
Comandos.registrar({
  nombre: "AVISOS", alias: ["NOTICIAS", "NEWS", "NOTICES"],
  ayuda: "Avisos de Taller 101 para quien usa shape101",
  correr: () => Avisos.abrir(),
});

/* Con `actualizaciones_auto: false` sólo quedan los avisos y la revisión
 * manual. Las pruebas apagan los temporizadores:
 * `Actualizar.temporizadores.forEach(clearTimeout)`. */
window.addEventListener("load", () => Actualizar.programar());
window.Actualizar = Actualizar;
window.Avisos = Avisos;
