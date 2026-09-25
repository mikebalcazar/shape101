/* Toma de puntos: entrada dinámica y coordenadas  ·  features 14, 15 y 16.
 *
 * Éste es el corazón de todo lo que viene. Cada herramienta de F2 y F3 —línea,
 * círculo, mover, copiar, recortar— se reduce a «pídeme un punto, y otro». Si
 * el selector de punto está bien hecho, esas herramientas son diez líneas cada
 * una; si está mal hecho, cada una reimplementa el osnap y el ortho a su modo y
 * ninguna se comporta igual que la de al lado.
 *
 * Un punto se puede dar de cuatro maneras, y las cuatro tienen que funcionar
 * siempre:
 *
 *   1. clic en el lienzo (con referencia a objeto, ortho y snap de rejilla)
 *   2. coordenadas tecleadas: `100,50` · `@100,50` · `100<45` · `@100<45`
 *   3. distancia directa: apuntar con el cursor y teclear `500`
 *   4. entrada dinámica: teclear la medida, Tab, teclear el ángulo, Enter
 */

const Entrada = (() => {
  let pendiente = null;      // {resolver, rechazar, base, mensaje, hule}
  let bloqueo = null;        // {campo:'longitud'|'angulo', valor:Number}
  let pendienteTexto = null; // {resolver, rechazar, opciones}
  let planoComando = null;   // el plano que fijó el primer punto de la herramienta
  let _medidaDinamica = null; // {ancho, alto} de la cajita, medidos al aparecer
  let _coordsTxt = "";

  /* --- Coordenadas tecleadas  ·  feature 16 ---------------------------- */
  function parsearCoordenadas(texto, base) {
    const t = String(texto || "").trim().replace(/\s+/g, "");
    if (!t) return null;
    const relativo = t.startsWith("@");
    const cuerpo = relativo ? t.slice(1) : t;
    const origen = relativo ? (base || [0, 0]) : [0, 0];

    // polar: distancia<ángulo
    if (cuerpo.includes("<")) {
      const [d, a] = cuerpo.split("<");
      const dist = parseFloat(d), ang = parseFloat(a);
      if (!isFinite(dist) || !isFinite(ang)) return null;
      return [origen[0] + dist * Math.cos(ang * Math.PI / 180),
              origen[1] + dist * Math.sin(ang * Math.PI / 180)];
    }
    // cartesianas: x,y
    if (cuerpo.includes(",")) {
      const [x, y] = cuerpo.split(",");
      const px = parseFloat(x), py = parseFloat(y);
      if (!isFinite(px) || !isFinite(py)) return null;
      return [origen[0] + px, origen[1] + py];
    }
    // Un solo número con punto base: distancia directa en la dirección del
    // cursor. Si el cursor está justo encima del punto base no hay dirección
    // que seguir —pasa siempre al dibujar un círculo: se pica el centro y se
    // teclea el radio sin mover el ratón— y entonces se toma la horizontal.
    // El resultado es el que el usuario quería: un radio de esa medida.
    const solo = parseFloat(cuerpo);
    if (isFinite(solo) && base) {
      const dx = estado.cursor.x - base[0], dy = estado.cursor.y - base[1];
      const largo = Math.hypot(dx, dy);
      if (largo < 1e-9) return [base[0] + solo, base[1]];
      return [base[0] + dx / largo * solo, base[1] + dy / largo * solo];
    }
    return null;
  }

  /* --- El punto que corresponde al cursor ahora mismo ------------------- */
  function puntoDelCursor() {
    const prefs = estado.prefs || {};
    const base = pendiente && pendiente.base;
    let p = [estado.cursor.x, estado.cursor.y];

    // 1. La referencia a objeto manda sobre todo lo demás: si el usuario ve el
    //    marcador verde, ahí quiere el punto, sin que la rejilla se lo mueva.
    //
    //    Sólo se busca cuando **hay un punto que tomar**. Antes se buscaba en
    //    cada movimiento del ratón aunque no hubiera comando, y se tiraba el
    //    resultado: era trabajo de cuadro entero para nada.
    const ref = pendiente ? Osnap.buscar(p, base, null, { cotas: !!pendiente.osnapCotas }) : null;
    estado.ref = ref;
    // Mike (12-sep-2026): «el valor tecleado es el valor final, no importa
    // ángulo, dirección o snaps». Antes el snap se devolvía aquí mismo y se
    // saltaba el bloqueo (paso 4): una línea de 200 se iba al endpoint que
    // hubiera a 150 en el camino, y una X tecleada se perdía al agarrar un
    // snap. Con algo tecleado, el snap sólo aporta dirección (o la otra
    // coordenada) y sigue el camino normal hasta el bloqueo.
    const blPrevio = bloqueo || bloqueoTecleado();
    if (ref && !blPrevio) return ref.p;
    if (ref) p = ref.p;

    // 2. Ortho  ·  feature 14  (y Shift lo invierte mientras dure: ver base.js)
    if (orthoActivo() && base) {
      const dx = p[0] - base[0], dy = p[1] - base[1];
      p = Math.abs(dx) >= Math.abs(dy) ? [p[0], base[1]] : [base[0], p[1]];
    }

    // 3. Snap de rejilla  ·  feature 12
    if (prefs.snap_rejilla) {
      const s = (prefs.snap_paso || 10) / mmPorUnidad();
      p = [Math.round(p[0] / s) * s, Math.round(p[1] / s) * s];
    }

    // 4. Bloqueo de la entrada dinámica  ·  feature 15
    //    Y lo que se está **tecleando** ahora mismo cuenta igual que lo ya
    //    fijado: Mike escribía «600» en la cajita y daba clic, y la línea
    //    salía hasta donde estaba el ratón, no de 600. El número tecleado
    //    manda; el clic sólo pone la dirección.
    const bl = blPrevio;
    if (bl && base && (bl.campo === "ancho" || bl.campo === "alto")) {
      // Rectángulo: lo tecleado es ancho (X) o alto (Y); el otro lado sigue al
      // cursor, y el signo lo pone hacia dónde está el cursor.
      const dx = p[0] - base[0], dy = p[1] - base[1];
      const v = Math.abs(bl.valor);
      return bl.campo === "ancho"
        ? [base[0] + signoMedida(bl.valor, dx) * v, p[1]]
        : [p[0], base[1] + signoMedida(bl.valor, dy) * v];
    }
    if (bl && base) {
      const dx = p[0] - base[0], dy = p[1] - base[1];
      let largo = Math.hypot(dx, dy);
      let ang = Math.atan2(dy, dx) * 180 / Math.PI;
      // Longitud negativa: la misma medida, hacia el lado contrario del cursor.
      if (bl.campo === "longitud") { largo = Math.abs(bl.valor); if (bl.valor < 0) ang += 180; }
      else ang = bl.valor;
      p = [base[0] + largo * Math.cos(ang * Math.PI / 180),
           base[1] + largo * Math.sin(ang * Math.PI / 180)];
    }
    return p;
  }

  /* Lo que hay tecleado, sin Enter todavía, en la entrada dinámica o en la
   * línea de comando: una longitud (o un ángulo, si el foco está en el
   * segundo campo). Vale sólo mientras la herramienta pide un punto con
   * dirección y hay punto base. */
  /* Signo de una medida tecleada (Mike, 12-sep-2026): «-4» quiere decir hacia
   * la izquierda (o hacia abajo), aunque el ratón esté a la derecha. Sin signo,
   * la medida es un tamaño y la dirección la pone el cursor, como antes.
   * `dCursor` es cursor − base en ese eje. */
  function signoMedida(valor, dCursor) {
    if (valor < 0) return -1;
    return dCursor < 0 ? -1 : 1;
  }

  function bloqueoTecleado() {
    if (!pendiente || !pendiente.base || !(pendiente.direccion || pendiente.dinamica === "xy")) return null;
    const xy = pendiente.dinamica === "xy";
    const act = document.activeElement;
    let campo = null, texto = "";
    if (act === $("#din-v1")) { campo = xy ? "ancho" : "longitud"; texto = act.value; }
    else if (act === $("#din-v2")) { campo = xy ? "alto" : "angulo"; texto = act.value; }
    else if (act === $("#cmd")) { campo = xy ? "ancho" : "longitud"; texto = act.value; }
    else return null;
    const t = String(texto).trim();
    if (!/^-?\d+(\.\d+)?$/.test(t)) return null;
    const n = parseFloat(t);
    if (!isFinite(n) || (campo !== "angulo" && n === 0)) return null;
    // Si el campo trae lo que la propia caja escribió (la medida del cursor),
    // no es un tecleo: sólo cuenta lo que la persona cambió.
    if (act.dataset.propio === t) return null;
    return { campo, valor: n };
  }

  /* --- Entrada dinámica  ·  feature 15 ---------------------------------- */
  function pintarDinamica(p) {
    const caja = $("#dinamica");
    // Pidiendo un dato suelto (ver pedirTexto) la cajita es de ese dato y se
    // queda donde apareció: no sigue al ratón ni se cierra al moverlo.
    if (pendienteTexto && pendienteTexto.cajita) return;
    if (!pendiente || !(estado.prefs || {}).dinamica) {
      caja.classList.remove("si");
      caja.classList.remove("uno");
      return;
    }
    const base = pendiente.base;
    if (caja.classList.contains("uno")) { caja.classList.remove("uno"); _medidaDinamica = null; $("#dinamica .pista").textContent = Tr("Tab fija · Espacio o Enter aceptan · Esc cancela"); }
    if (!caja.classList.contains("si")) { caja.classList.add("si"); _medidaDinamica = null; }
    // Junto al cursor, pero volteándose contra el borde: pegada abajo a la
    // derecha se metía debajo del panel y de la consola, y los campos
    // quedaban donde no se pueden teclear.
    //
    // El tamaño de la caja se mide **una vez** al aparecer, no en cada
    // movimiento: leer `offsetWidth` después de haber tocado el DOM obliga a
    // recalcular el diseño de toda la ventana por cada movimiento del ratón,
    // y con un panel de capas largo eso es el cuadro entero. Y se coloca con
    // `transform`, que no toca el diseño.
    if (!_medidaDinamica) _medidaDinamica = { ancho: caja.offsetWidth || 150, alto: caja.offsetHeight || 70 };
    const { ancho, alto } = _medidaDinamica;
    const dispX = lienzo.clientWidth, dispY = lienzo.clientHeight;
    const x = estado.cursor.px + 18 + ancho > dispX
      ? estado.cursor.px - 18 - ancho : estado.cursor.px + 18;
    const y = estado.cursor.py + 18 + alto > dispY
      ? estado.cursor.py - 18 - alto : estado.cursor.py + 18;
    caja.style.transform = `translate(${Math.max(4, x)}px, ${Math.max(4, y)}px)`;

    if (base && pendiente.dinamica === "xy") {
      // Rectángulo (Mike, 7-sep): el primer valor es lo que mide en X y el
      // segundo lo que mide en Y, no una longitud y un ángulo.
      const dx = p[0] - base[0], dy = p[1] - base[1];
      $("#din-e1").textContent = "X";
      $("#din-e2").textContent = "Y";
      const v1 = $("#din-v1"), v2 = $("#din-v2");
      // El campo ya fijado muestra lo tecleado, con su signo («-300»): así se
      // ve que va a la izquierda y no se pierde el signo al rematar.
      const tx = (bloqueo && bloqueo.campo === "ancho") ? mm(bloqueo.valor) : mm(Math.abs(dx));
      const ty = (bloqueo && bloqueo.campo === "alto") ? mm(bloqueo.valor) : mm(Math.abs(dy));
      if (document.activeElement !== v1 && v1.value !== tx) { v1.value = tx; v1.dataset.propio = tx; }
      if (document.activeElement !== v2 && v2.value !== ty) { v2.value = ty; v2.dataset.propio = ty; }
    } else if (base) {
      const dx = p[0] - base[0], dy = p[1] - base[1];
      $("#din-e1").textContent = "Long";
      $("#din-e2").textContent = "Áng";
      const v1 = $("#din-v1"), v2 = $("#din-v2");
      if (document.activeElement !== v1) { const t = mm(Math.hypot(dx, dy)); if (v1.value !== t) { v1.value = t; v1.dataset.propio = t; } }
      if (document.activeElement !== v2) { const t = grados(Math.atan2(dy, dx) * 180 / Math.PI); if (v2.value !== t) { v2.value = t; v2.dataset.propio = t; } }
    } else {
      $("#din-e1").textContent = "X";
      $("#din-e2").textContent = "Y";
      const v1 = $("#din-v1"), v2 = $("#din-v2");
      if (document.activeElement !== v1) { const t = mm(p[0]); if (v1.value !== t) { v1.value = t; v1.dataset.propio = t; } }
      if (document.activeElement !== v2) { const t = mm(p[1]); if (v2.value !== t) { v2.value = t; v2.dataset.propio = t; } }
    }
    const bl = bloqueo || bloqueoTecleado();
    $("#din-c1").classList.toggle("fijo", !!(bl && (bl.campo === "longitud" || bl.campo === "ancho")));
    $("#din-c2").classList.toggle("fijo", !!(bl && (bl.campo === "angulo" || bl.campo === "alto")));
  }

  function valorDinamico() {
    const base = pendiente && pendiente.base;
    const v1 = parseFloat($("#din-v1").value);
    const v2 = parseFloat($("#din-v2").value);
    if (!isFinite(v1) || !isFinite(v2)) return null;
    if (!base) return [v1, v2];
    if (pendiente.dinamica === "xy") {
      // Lo fijado con Enter manda sobre lo que muestre la caja.
      const ancho = (bloqueo && bloqueo.campo === "ancho") ? bloqueo.valor : v1;
      const alto = (bloqueo && bloqueo.campo === "alto") ? bloqueo.valor : v2;
      const sx = signoMedida(ancho, estado.cursor.x - base[0]), sy = signoMedida(alto, estado.cursor.y - base[1]);
      return [base[0] + sx * Math.abs(ancho), base[1] + sy * Math.abs(alto)];
    }
    return [base[0] + v1 * Math.cos(v2 * Math.PI / 180),
            base[1] + v1 * Math.sin(v2 * Math.PI / 180)];
  }

  /* --- Ciclo de vida de una toma de punto ------------------------------- */
  /* Una herramienta puede ofrecer atajos además del punto: la polilínea acepta
   * «C» para cerrarse, el arreglo acepta «F» para filas. Se resuelven con
   * {opcion:"C"} en vez de un punto, y quien llamó decide qué hacer. Por eso
   * toda herramienta comprueba `Array.isArray(p)` antes de usarlo. */
  function pedirPunto({ mensaje = "Indica un punto", base = null, hule = null,
                        opciones = [], direccion = false, dinamica = null,
                        numero = false, osnapCotas = false } = {}) {
    // `dinamica: "xy"`: la cajita dinámica ofrece X y Y (ancho y alto desde la
    // base) en vez de longitud y ángulo. Es lo que pide un rectángulo.
    // `numero`: un número a secas no es una distancia en la dirección del
    // cursor sino una respuesta ({numero: n}); lo usa ESCALAR para el factor.
    // `osnapCotas`: se admiten las líneas de cota de otras cotas como
    // referencia (al colocar una cota). Ver ui/osnap.js.
    cancelar("");
    // El plano en el que trabaja la herramienta se fija con su **primer**
    // punto —el que se pide sin base— y dura hasta que acabe. Una línea no
    // puede tener un extremo en el suelo y el otro en la pared: mientras el
    // comando sigue, la ventana bajo el cursor sólo manda si dibuja en ese
    // mismo plano. Ver el mousemove de vista.js.
    if (!base) planoComando = null;
    return new Promise((resolver, rechazar) => {
      pendiente = { resolver, rechazar, base, mensaje, hule, direccion, dinamica, numero, osnapCotas,
                    opciones: opciones.map((o) => o.toUpperCase()) };
      estado.captura = pendiente;
      bloqueo = null;
      lienzo.style.cursor = "none";
      Comandos.pedir(mensaje);
      alMoverse();
    });
  }

  function entregar(p) {
    const q = pendiente;
    if (Array.isArray(p) && !planoComando && estado.vista && estado.vista.plano) {
      planoComando = estado.vista.plano;
    }
    limpiar();
    if (q) q.resolver(p);
  }

  /* --- Teclear una medida y **después** apuntar -------------------------
   *
   * Al trazar una línea, teclear «600» dibujaba los 600 mm ahí mismo, hacia
   * donde estuviera el ratón en ese instante — que es hacia donde uno estaba
   * mirando la medida, no hacia donde quiere la raya. Lo reportó Mike así:
   * «quiero hacer click en la dirección que quiera, pero la línea sólo se
   * traza en la dirección donde tengo el mouse».
   *
   * Ahora la medida **se fija** y la herramienta sigue esperando: el hule
   * enseña una raya de exactamente esa longitud girando con el cursor, y el
   * clic elige la dirección. Enter también sirve, con la dirección de ese
   * momento, para quien ya tenía el ratón puesto.
   *
   * Sólo pasa donde la dirección significa algo (`direccion: true`). El radio
   * de un círculo o el lado de un rectángulo se contestan con el número solo,
   * y ahí seguir pidiendo un clic sería estorbar.
   */
  function fijarLargo(texto) {
    if (!pendiente || !pendiente.base) return false;
    // **La coma no se convierte en punto aquí.** En este programa la coma
    // separa X de Y (`300,100` es un punto), así que aceptarla como decimal
    // convertía una coordenada en una longitud de 300.1 mm y la línea se iba a
    // otro lado. Sólo un número pelado, con punto decimal si acaso.
    const t = String(texto).trim();
    if (!/^-?\d+(\.\d+)?$/.test(t)) return false;    // «100,50» y «@100<45» no
    const n = parseFloat(t);
    if (!isFinite(n) || n === 0) return false;
    if (pendiente.dinamica === "xy") {
      // Rectángulo por la línea de comandos (Mike, 9-sep-2026): «clic origen
      // → teclear ancho Enter → teclear alto Enter → se crea». Sin cajita
      // dinámica, el primer número es el ancho y el segundo el alto; crece
      // hacia donde esté el cursor.
      if (!bloqueo || bloqueo.campo !== "ancho") {
        bloqueo = { campo: "ancho", valor: n };
        Comandos.pedir(`${Tr("Alto")} (${mm(Math.abs(n))} ${U()} × ?)`);
        alMoverse();
        return true;
      }
      const base = pendiente.base;
      const sx = signoMedida(bloqueo.valor, estado.cursor.x - base[0]), sy = signoMedida(n, estado.cursor.y - base[1]);
      entregar([base[0] + sx * Math.abs(bloqueo.valor), base[1] + sy * Math.abs(n)]);
      return true;
    }
    if (!pendiente.direccion) return false;
    bloqueo = { campo: "longitud", valor: n };
    Comandos.pedir(`${pendiente.mensaje} · ${mm(Math.abs(n))} ${U()} fijos — apunta y haz clic`);
    alMoverse();
    return true;
  }

  /** Con `numero: true`, un número a secas es la respuesta, no un punto. */
  function numeroTecleado(texto) {
    if (!pendiente || !pendiente.numero) return false;
    // La coma separa coordenadas («400,100» es un punto, no 400.1); el
    // decimal va con punto, como en la línea de comando. Hasta la 0.21.7 la
    // coma se leía como decimal y ROTAR/ESCALAR tomaban un punto por un número.
    const t = String(texto).trim();
    if (!/^-?\d+(\.\d+)?$/.test(t)) return false;
    const n = parseFloat(t);
    if (!isFinite(n)) return false;
    entregar({ numero: n });
    return true;
  }

  function cancelar(motivo = "cancelado") {
    const q = pendiente;
    limpiar();
    // El mensaje es siempre «cancelado» (así lo distinguen las herramientas
    // de un error de verdad); el motivo dice si fue Escape o Enter en vacío,
    // que para algunas herramientas no es lo mismo (CENTRAR).
    const e = new Error("cancelado");
    e.motivo = motivo;
    if (q) q.rechazar(e);
  }

  function limpiar() {
    pendiente = null;
    bloqueo = null;
    estado.captura = null;
    estado.ref = null;
    estado.hule = null;
    lienzo.style.cursor = "";
    $("#dinamica").classList.remove("si");
    pintar();
  }

  function alMoverse() {
    const t0 = performance.now();
    const p = puntoDelCursor();
    const tRef = performance.now() - t0;
    const txt = `${mm(p[0])}, ${mm(p[1])} ${U()}` +
      (estado.ref ? `  ·  ${estado.modosOsnap[estado.ref.modo] || estado.ref.modo}` : "");
    if (txt !== _coordsTxt) { _coordsTxt = txt; $("#coords").textContent = txt; }
    let tHule = 0;
    if (pendiente) {
      const t1 = performance.now();
      // El hule nace con **su** plano. Sin esto lo pintaba cada ventana con el
      // plano de ella misma, así que una línea trazada sobre el suelo se veía
      // parada en la Frontal y en la Lateral. Lo reportó Mike: «se dibuja como
      // si estuviera en una vista frontal». Medido el 24-sep: el mismo punto
      // salía en [76.2, -62.3, 0] en la Superior y en [76.2, 0, -62.3] en la
      // Frontal.
      if (pendiente.hule) {
        const h = pendiente.hule(p);
        const plano = planoComando || (estado.vista && estado.vista.plano);
        if (h && plano) {
          if (!h.plano) h.plano = plano;
          if (h.partes) for (const parte of h.partes) if (parte && !parte.plano) parte.plano = plano;
        }
        estado.hule = h;
      }
      tHule = performance.now() - t1;
      pintarDinamica(p);
    }
    pintar();
    const total = performance.now() - t0;
    if (total > 25 && typeof Diag !== "undefined") {
      Diag.cuadros.push({ t: Date.now(), raton: total, referencia: tRef, hule: tHule, dinamica: total - tRef - tHule });
      if (Diag.cuadros.length > 30) Diag.cuadros.shift();
      if (Diag.activo) Comandos.eco(`ratón lento: ${total.toFixed(1)} ms (referencia ${tRef.toFixed(1)}, hule ${tHule.toFixed(1)})`, "malo");
    }
  }

  function clicEnLienzo() {
    if (!pendiente) return;
    // Con una medida tecleada y sin Enter, el clic la acepta: la medida
    // tecleada, la dirección del clic.
    const bl = bloqueoTecleado();
    if (bl) bloqueo = bl;
    entregar(puntoDelCursor());
  }

  /* Para el lienzo: la previa de una medida fijada o tecleada. Devuelve
   * {base, p, cursor, valor} o null. `p` es el punto exacto a esa medida en
   * la dirección del cursor; `cursor` a dónde apunta el ratón. */
  function previaLargo() {
    const bl = bloqueo || bloqueoTecleado();
    if (!bl || !pendiente || !pendiente.base || bl.campo !== "longitud") return null;
    const base = pendiente.base;
    return { base, p: puntoDelCursor(), cursor: [estado.cursor.x, estado.cursor.y], valor: bl.valor };
  }

  /** ¿Lo que tecleó el usuario es uno de los atajos que ofrece la herramienta? */
  function opcionTecleada(texto) {
    if (!pendiente || !pendiente.opciones || !pendiente.opciones.length) return false;
    const t = String(texto).trim().toUpperCase();
    if (!pendiente.opciones.includes(t)) return false;
    entregar({ opcion: t });
    return true;
  }

  /* --- Pedir texto y opciones ------------------------------------------- */
  /* Las herramientas también preguntan cosas que no son puntos: el texto de un
   * rótulo, la altura de las letras, si la polilínea se cierra. Va por la misma
   * línea de comando —una sola caja donde teclear— en vez de por ventanitas
   * que tapan justo la parte del dibujo que uno está mirando. */
  function pedirTexto({ mensaje = "Texto", valor = "", opciones = null, libre = null } = {}) {
    // `libre`: texto de verdad (un rótulo, un nombre), donde el espacio es un
    // espacio. Con opciones (S/N) o números, el espacio confirma como Enter.
    if (libre === null) libre = !opciones;
    return new Promise((resolver, rechazar) => {
      pendienteTexto = { resolver, rechazar, opciones, libre, cajita: false };
      Comandos.pedir(mensaje + (valor !== "" ? ` <${valor}>` : ""));
      const campo = $("#cmd");
      campo.dataset.omision = String(valor);
      // La cajita junto al cursor, con el nombre del dato (Mike, 9-sep-2026:
      // «cuando una herramienta pide un valor —distancia, radio, factor,
      // número de lados— abrir la cajita junto al cursor con el nombre del
      // dato y ahí ver lo que se teclea, no sólo en la línea de comando»).
      // Sale si la entrada dinámica está encendida y el ratón anda sobre el
      // lienzo; si no, se contesta en la línea de comandos como siempre.
      if ((estado.prefs || {}).dinamica && estado.cursor && !(typeof Dialogo !== "undefined" && Dialogo.activo())) {
        pendienteTexto.cajita = true;
        abrirCajita(mensaje, valor, libre);
      } else {
        campo.focus();
      }
    });
  }

  /* La cajita de un solo dato: reutiliza la de la entrada dinámica con el
   * segundo campo escondido. Se queda quieta donde apareció. */
  function abrirCajita(mensaje, valor, libre) {
    const caja = $("#dinamica");
    caja.classList.add("si", "uno");
    _medidaDinamica = null;
    const et = $("#din-e1"), v1 = $("#din-v1"), c1 = $("#din-c1");
    et.textContent = mensaje.replace(/\s*\(.*\)\s*$/, "");   // sin el paréntesis de ayuda
    et.title = mensaje;
    v1.value = String(valor ?? "");
    v1.dataset.propio = "";
    c1.classList.remove("fijo");
    $("#dinamica .pista").textContent = libre ? Tr("Enter acepta · Esc cancela") : Tr("Espacio o Enter aceptan · Esc cancela");
    // Junto al cursor, volteándose contra el borde (como la cajita de puntos).
    const ancho = caja.offsetWidth || 180, alto = caja.offsetHeight || 50;
    const dispX = lienzo.clientWidth, dispY = lienzo.clientHeight;
    const px = estado.cursor.px, py = estado.cursor.py;
    const x = px + 18 + ancho > dispX ? px - 18 - ancho : px + 18;
    const y = py + 18 + alto > dispY ? py - 18 - alto : py + 18;
    caja.style.transform = `translate(${Math.max(4, x)}px, ${Math.max(4, y)}px)`;
    v1.focus();
    v1.select();
  }

  function cerrarCajita() {
    const caja = $("#dinamica");
    if (!caja.classList.contains("uno")) return;
    caja.classList.remove("si", "uno");
    $("#dinamica .pista").textContent = Tr("Tab fija · Espacio o Enter aceptan · Esc cancela");
    $("#din-v1").value = "";
    _medidaDinamica = null;
  }

  /* --- Memoria de valores  ·  0.19.3 --------------------------------------
   * Mike (7-sep): «el trim (y supongo que otras funciones) deben quedarse con
   * memoria de cuál fue y el valor: el último offset era a 60, entonces si
   * pongo offset de nuevo, en auto está a 60, al menos que escriba otro».
   * Cada pregunta numérica recuerda su última respuesta —por el texto de la
   * pregunta— y la ofrece por omisión. Vive en preferencias
   * (`ultimos_valores`), así que sobrevive a cerrar el programa. */
  function ultimoValor(clave, defecto = null) {
    const u = (estado.prefs && estado.prefs.ultimos_valores) || {};
    const v = u[clave];
    return (typeof v === "number" && isFinite(v)) ? v : defecto;
  }

  let guardandoUltimos = null;
  function recordarValor(clave, v) {
    if (!(typeof v === "number" && isFinite(v))) return;
    estado.prefs = estado.prefs || {};
    const u = Object.assign({}, estado.prefs.ultimos_valores || {});
    if (u[clave] === v) return;
    u[clave] = v;
    estado.prefs.ultimos_valores = u;
    clearTimeout(guardandoUltimos);
    guardandoUltimos = setTimeout(() => {
      post("/api/preferencias", { cambios: { ultimos_valores: u } }).catch(() => {});
    }, 300);
  }

  async function pedirNumero({ mensaje = "Valor", valor = null, minimo = null, clave = null, recordar = true } = {}) {
    clave = clave || mensaje;
    const omision = recordar ? ultimoValor(clave, valor) : valor;
    while (true) {
      const t = await pedirTexto({ mensaje, valor: omision === null ? "" : mm(omision), libre: false });
      if (t === "" && omision !== null) { if (recordar) recordarValor(clave, omision); return omision; }
      const n = parseFloat(String(t).replace(",", "."));
      if (isFinite(n) && (minimo === null || n >= minimo)) { if (recordar) recordarValor(clave, n); return n; }
      Comandos.eco(`«${t}» no es un número válido.`, "malo");
    }
  }

  function textoRecibido(texto) {
    const q = pendienteTexto;
    if (!q) return false;
    pendienteTexto = null;
    cerrarCajita();
    const omision = $("#cmd").dataset.omision || "";
    q.resolver(texto === "" ? omision : texto);
    return true;
  }

  function cancelarTexto() {
    const q = pendienteTexto;
    pendienteTexto = null;
    cerrarCajita();
    if (q) q.rechazar(new Error("cancelado"));
  }

  /* --- Teclado ---------------------------------------------------------- */
  function alTeclear(e) {
    // La cajita de un dato (ver pedirTexto): Enter —o espacio, si es un
    // número— acepta lo tecleado ahí; Esc cancela. Lo demás se teclea normal.
    if (pendienteTexto && pendienteTexto.cajita) {
      const v1 = $("#din-v1");
      if (e.key === "Escape") { e.preventDefault(); cancelarTexto(); return true; }
      if (document.activeElement === v1 &&
          (e.key === "Enter" || (e.key === " " && !pendienteTexto.libre))) {
        e.preventDefault();
        const t = v1.value.trim();
        Comandos.eco("› " + (t || "(por omisión)"));
        textoRecibido(t);
        return true;
      }
      // Teclear con el foco en el lienzo: que caiga en la cajita, y lo
      // tecleado sustituye la omisión (como en cualquier campo seleccionado).
      if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey &&
          !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        v1.focus();
        v1.select();
        return true;
      }
      return false;
    }
    if (!pendiente) return false;

    if (e.key === "Escape") { cancelar(); return true; }

    // Tab fija el campo que se está tecleando y salta al otro. Es lo que
    // convierte la entrada dinámica en «longitud 600, ángulo 0, Enter».
    if (e.key === "Tab" && (estado.prefs || {}).dinamica && pendiente.base) {
      e.preventDefault();
      const enV1 = document.activeElement === $("#din-v1");
      const xy = pendiente.dinamica === "xy";
      const campo = enV1 ? (xy ? "ancho" : "longitud") : (xy ? "alto" : "angulo");
      const valor = parseFloat((enV1 ? $("#din-v1") : $("#din-v2")).value);
      if (isFinite(valor)) bloqueo = { campo, valor };
      (enV1 ? $("#din-v2") : $("#din-v1")).select();
      alMoverse();
      return true;
    }

    // Enter **o espacio** en la entrada dinámica: en un número el espacio no
    // sirve de nada, así que confirma (Mike, 7-sep).
    if ((e.key === "Enter" || e.key === " ") &&
        (document.activeElement === $("#din-v1") || document.activeElement === $("#din-v2"))) {
      e.preventDefault();
      // Rectángulo (Mike, 8-sep): Enter en X pasa a Y, igual que Tab; el
      // segundo Enter remata. Un solo valor tecleado en X y Enter no puede
      // querer decir «el alto es el del ratón».
      if (pendiente.dinamica === "xy" && pendiente.base && document.activeElement === $("#din-v1")) {
        const valor = parseFloat($("#din-v1").value);
        if (isFinite(valor) && valor !== 0) bloqueo = { campo: "ancho", valor };
        $("#din-v2").select();
        alMoverse();
        return true;
      }
      const p = valorDinamico();
      if (p) entregar(p);
      return true;
    }

    // Empezar a teclear un número manda el foco a la entrada dinámica.
    if (/^[0-9.\-]$/.test(e.key) && (estado.prefs || {}).dinamica &&
        !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      $("#din-v1").value = e.key;
      $("#din-v1").focus();
      e.preventDefault();
      return true;
    }
    return false;
  }

  for (const id of ["#din-v1", "#din-v2", "#cmd"]) {
    const el = $(id);
    if (el) el.addEventListener("input", () => { if (pendiente) alMoverse(); });
  }

  return {
    pedirPunto, pedirTexto, pedirNumero, textoRecibido, cancelarTexto,
    ultimoValor, recordarValor,
    cancelar, clicEnLienzo, alMoverse, alTeclear, opcionTecleada,
    parsearCoordenadas, puntoDelCursor, entregar, fijarLargo, previaLargo, numeroTecleado, signoMedida,
    get largoFijo() { return !!bloqueo; },
    get activa() { return !!pendiente; },
    get esperandoTexto() { return !!pendienteTexto; },
    // Sólo cuando lo que se espera es texto libre el espacio es un espacio.
    get esperandoTextoLibre() { return !!(pendienteTexto && pendienteTexto.libre); },
    get base() { return pendiente && pendiente.base; },
    // El plano en el que ya está trabajando la herramienta, o null si todavía
    // no ha tomado su primer punto.
    planoComando: () => planoComando,
  };
})();
