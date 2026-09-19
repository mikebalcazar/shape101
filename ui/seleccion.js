/* Selección y grips  ·  features 31 y 42.
 *
 * Todo lo que edita empieza aquí: primero se dice **qué**, luego **qué se le
 * hace**. Se respetan las dos formas de AutoCAD, y la diferencia entre ellas no
 * es un detalle — es la que más usa quien dibuja:
 *
 *   · **Ventana** (arrastrar de izquierda a derecha): agarra sólo lo que queda
 *     **entero** dentro. Sirve para llevarse un mueble completo sin arrastrar
 *     los muros que lo tocan.
 *   · **Cruce** (de derecha a izquierda): agarra todo lo que la caja **toque**.
 *     Sirve para recortar media docena de líneas de un tirón.
 *
 * El sentido del arrastre decide cuál es. Por eso la caja se pinta distinta:
 * continua para ventana, punteada para cruce.
 */

const Seleccion = (() => {
  let pendiente = null;          // {resolver, rechazar, filtro, queja, una}
  let cajaSel = null;            // {a:[x,y], b:[x,y]} en mm
  let gripArrastrado = null;

  /* Cuánto se puede fallar el tiro y aun así agarrar algo  ·  punto 8.
   *
   * Mike: *«me cuesta mucho trabajo seleccionar una cota… hasta que no hago
   * zoom y le doy justo encima de la línea»*. Con 8 píxeles había que atinarle
   * a una raya de un píxel, y en una cota la raya es lo único que hay: el
   * número y las flechas ocupan sitio pero no eran zona de clic.
   *
   * Dos aperturas en vez de una más grande: la primera pasada es fina, así que
   * en un nudo de líneas sigue ganando la que está de verdad debajo del cursor.
   * Sólo si no hay **nada** cerca se vuelve a mirar con la manga ancha, que es
   * cuando el usuario claramente quería lo único que hay por ahí. */
  /* 6-sep, Mike: *«que donde des clic sea sobre el mero píxel, o si acaso un
   * par de píxeles al lado… ahorita selecciona varias cosas muy lejos del
   * clic, e incluso en un espacio vacío te dice que seleccionaste algo»*. Con
   * 11 y 26 píxeles, alejado del plano el tiro abarcaba medio cuarto. Ahora es
   * la caja de AutoCAD (PICKBOX 3): 3 px, y una segunda pasada de 6 sólo si
   * no hubo nada. Los números de cota siguen entrando por su caja. */
  const APERTURA = 3;            // píxeles: el tiro normal (PICKBOX de AutoCAD)
  const APERTURA_LEJOS = 6;      // segunda pasada, sólo si no hubo nada

  /* --- Geometría del cliente --------------------------------------------
   * Todo esto pasa por `ui/indice.js`. Antes se resolvía recorriendo:
   * `primitivasDe` filtraba el plano entero por cada entidad y por cuadro, y
   * con diez cosas seleccionadas eso eran millones de comparaciones para mover
   * el ratón un píxel. Era la causa de *«cuando selecciono algo se tarda en
   * reaccionar»*. */
  const primitivasDe = (id) => Indice.primitivas(id);
  const cajaDe = (id) => Indice.caja(id);
  const idsVisibles = () => Indice.ids();

  /** Todo lo que cae dentro de la tolerancia, del más cercano al más lejano.
   *
   *  Devuelve la lista entera y no sólo el mejor porque con eso se arma el
   *  menú de «cuál de éstos» cuando hay varias cosas encimadas. */
  function _candidatos(p, tol) {
    const cercanas = new Map();       // id → distancia mínima
    for (const pr of Indice.cerca(p, tol)) {
      const q = Osnap.sobre(pr, p);
      const d = Math.hypot(q[0] - p[0], q[1] - p[1]);
      if (d > tol) continue;
      const antes = cercanas.get(pr.id);
      if (antes === undefined || d < antes) cercanas.set(pr.id, d);
    }
    // Los textos no tienen geometría de línea: se atrapan por su caja. Aquí
    // entra el número de una cota, que es lo más grande que tiene y lo que
    // cualquiera intenta picar primero.
    for (const t of estado.trazos) {
      if (t.clase !== "texto") continue;
      const alto = t.altura;
      const renglones = String(t.texto).split("\n");
      const ancho = t.ancho || 0.6 * t.altura * Math.max(...renglones.map((r) => r.length), 1);
      // Los renglones de abajo (texto de párrafo) cuelgan bajo la base.
      const y0 = t.p[1] - 1.25 * alto * (renglones.length - 1);
      // La alineación mueve la caja: un número centrado —como el de una cota—
      // arranca media palabra a la izquierda de su punto.
      const a = t.alineacion === "CENTRO" ? t.p[0] - ancho / 2
              : t.alineacion === "DER" ? t.p[0] - ancho : t.p[0];
      if (p[0] >= a - tol && p[0] <= a + ancho + tol &&
          p[1] >= y0 - tol && p[1] <= t.p[1] + alto + tol) {
        const d = Math.hypot(Math.max(a - p[0], 0, p[0] - a - ancho),
                             Math.max(y0 - p[1], 0, p[1] - t.p[1] - alto));
        const antes = cercanas.get(t.id);
        if (antes === undefined || d < antes) cercanas.set(t.id, d);
      }
    }
    return [...cercanas.entries()]
      .sort((a, b) => a[1] - b[1])
      .map(([id, d]) => ({ id, d }));
  }

  /** Todo lo que hay bajo el cursor, lo más cercano primero. */
  function candidatos(p) {
    const e = estado.vista.escala;
    const cerca = _candidatos(p, APERTURA / e);
    return cerca.length ? cerca : _candidatos(p, APERTURA_LEJOS / e);
  }

  /** ¿Qué entidad está bajo este punto? La más cercana dentro de la apertura. */
  function bajoElCursor(p) {
    const lista = candidatos(p);
    return lista.length ? lista[0].id : null;
  }

  /* ¿La primitiva toca de verdad el rectángulo?  ·  0.20.0
   *
   * Mike (9-sep-2026), sobre la selección por cruce: «GEOMETRÍA REAL, LO QUE
   * MI OJO VE». Hasta aquí se comparaba la **caja envolvente** de la entidad
   * con la ventana, y una diagonal larga o un círculo grande entraban en la
   * selección sin que la ventana tocara ni una de sus rayas. Ahora se prueba
   * cada raya y cada arco contra el rectángulo. */
  function segTocaCaja(a, b, caja) {
    const [x0, y0, x1, y1] = caja;
    const dentro = (p) => p[0] >= x0 && p[0] <= x1 && p[1] >= y0 && p[1] <= y1;
    if (dentro(a) || dentro(b)) return true;
    // Liang–Barsky: ¿queda algún trozo del segmento dentro?
    const dx = b[0] - a[0], dy = b[1] - a[1];
    let t0 = 0, t1 = 1;
    for (const [p, q] of [[-dx, a[0] - x0], [dx, x1 - a[0]], [-dy, a[1] - y0], [dy, y1 - a[1]]]) {
      if (Math.abs(p) < 1e-12) { if (q < 0) return false; continue; }
      const r = q / p;
      if (p < 0) { if (r > t1) return false; if (r > t0) t0 = r; }
      else { if (r < t0) return false; if (r < t1) t1 = r; }
    }
    return t0 <= t1;
  }

  function primTocaCaja(pr, caja) {
    const [x0, y0, x1, y1] = caja;
    if (pr.tipo === "seg") return segTocaCaja(pr.a, pr.b, caja);
    if (pr.tipo === "punto") return pr.p[0] >= x0 && pr.p[0] <= x1 && pr.p[1] >= y0 && pr.p[1] <= y1;
    if (pr.tipo === "arco") {
      // Un arco toca la caja si algún lado de la caja lo cruza, o si algún
      // punto suyo cae dentro (el arco entero dentro de la caja).
      const lados = [[[x0, y0], [x1, y0]], [[x1, y0], [x1, y1]], [[x1, y1], [x0, y1]], [[x0, y1], [x0, y0]]];
      for (const [a, b] of lados) {
        if (Osnap.interseccion({ tipo: "seg", a, b }, pr).length) return true;
      }
      const rad = (g) => g * Math.PI / 180;
      const completo = Math.abs((pr.a1 - pr.a0 + 360) % 360) < 1e-9 || pr.a1 === 360;
      const p0 = [pr.c[0] + pr.r * Math.cos(rad(pr.a0)), pr.c[1] + pr.r * Math.sin(rad(pr.a0))];
      const pm = completo ? [pr.c[0] + pr.r, pr.c[1]]
        : [pr.c[0] + pr.r * Math.cos(rad(pr.a0 + (((pr.a1 - pr.a0) % 360 + 360) % 360) / 2)),
           pr.c[1] + pr.r * Math.sin(rad(pr.a0 + (((pr.a1 - pr.a0) % 360 + 360) % 360) / 2))];
      return [p0, pm].some((p) => p[0] >= x0 && p[0] <= x1 && p[1] >= y0 && p[1] <= y1);
    }
    return false;
  }

  function dentroDeCaja(id, caja, cruce) {
    const c = cajaDe(id);
    if (!c) return false;
    const [x0, y0, x1, y1] = caja;
    if (cruce) {
      if (c[2] < x0 || c[0] > x1 || c[3] < y0 || c[1] > y1) return false;
      // La caja envolvente sólo descarta; lo que decide es la geometría.
      const prims = primitivasDe(id);
      if (!prims.length) return true;
      for (const pr of prims) if (primTocaCaja(pr, caja)) return true;
      // Un texto no tiene rayas: cuenta por la caja de sus letras, que es lo
      // que se ve. (Si su punto de inserción cayó dentro ya entró arriba.)
      if (prims.every((pr) => pr.tipo === "punto")) {
        for (const t of Indice.trazos(id)) {
          if (t.clase !== "texto" || typeof cajaTrazo !== "function") continue;
          const b = cajaTrazo(t);
          if (!(b[2] < x0 || b[0] > x1 || b[3] < y0 || b[1] > y1)) return true;
        }
      }
      return false;
    }
    return c[0] >= x0 && c[1] >= y0 && c[2] <= x1 && c[3] <= y1;
  }

  /* --- El conjunto seleccionado ----------------------------------------- */
  function limpiar() {
    estado.sel.clear();
    refrescarPie();
    pintar();
  }

  /* Picar un miembro de un grupo es picar el grupo entero  ·  GRUPO.
   * Con Alt se pica sólo ése, para poder sacar uno sin desagrupar. */
  function conGrupo(id, e) {
    const g = id && Indice.grupoDe(id);
    if (!g || (e && e.altKey)) return [id];
    return Indice.delGrupo(g);
  }

  function alternar(id, sumar, e = null) {
    if (!sumar) estado.sel.clear();
    const ids = conGrupo(id, e);
    if (estado.sel.has(id) && sumar) { for (const i of ids) estado.sel.delete(i); }
    else if (id) { for (const i of ids) estado.sel.add(i); }
    refrescarPie();
    if (pendiente && pendiente.una && estado.sel.size) terminarPeticion();
    pintar();
  }

  function refrescarPie() {
    const n = estado.sel.size;
    $("#f-sel").textContent = n ? `${n} seleccionada${n > 1 ? "s" : ""}` : "";
    if (typeof pintarPropsObjeto === "function") pintarPropsObjeto();
  }

  /* --- Pedir una selección a nombre de una herramienta ------------------- */
  /* Una herramienta de edición dice «dame las entidades» y se espera. Si ya
   * había algo seleccionado, se lo lleva de inmediato: quien selecciona primero
   * y luego teclea el comando no debería tener que volver a seleccionar. */
  function pedir({ mensaje = "Selecciona las entidades", filtro = null,
                   queja = "Esa entidad no sirve para esto." } = {}) {
    if (estado.sel.size && !filtro) return Promise.resolve([...estado.sel]);
    estado.sel.clear();
    return new Promise((resolver, rechazar) => {
      pendiente = { resolver, rechazar, filtro, queja, una: false };
      Comandos.pedir(mensaje + " (Enter termina)");
      pintar();
    });
  }

  async function pedirUna({ mensaje = "Elige una entidad", filtro = null,
                            queja = "Esa entidad no sirve para esto.", icono = null } = {}) {
    // Selección previa (Mike, 9-sep-2026): «si hay un elemento seleccionado y
    // se entra un comando, en automático el comando aplica para el elemento
    // seleccionado». Con **una** cosa seleccionada que pase el filtro, es
    // ésa, sin volver a pedirla. Se consume: la siguiente vuelta de la
    // herramienta vuelve a preguntar.
    if (estado.sel.size === 1) {
      const id = [...estado.sel][0];
      estado.sel.clear();
      refrescarPie();
      let sirve = true;
      if (filtro) {
        try { sirve = !!filtro(await api(`/api/entidad/${id}`)); } catch (_) { sirve = false; }
      }
      if (sirve) { if (icono) estado.cursorIcono = icono; return id; }
    }
    estado.sel.clear();
    // `icono`: la herramienta se dibuja junto al cursor (tijera en RECORTAR)
    // con la caja de selección bien marcada. Mike, 7-sep-2026. Lo pinta
    // vista.js → pintarMira; se quita al terminar o cancelar.
    if (icono) estado.cursorIcono = icono;
    return new Promise((resolver, rechazar) => {
      pendiente = { resolver, rechazar, filtro, queja, una: true };
      Comandos.pedir(mensaje);
      pintar();
    });
  }

  async function aceptable(id) {
    if (!pendiente || !pendiente.filtro) return true;
    try {
      const ent = await api(`/api/entidad/${id}`);
      if (pendiente.filtro(ent)) return true;
    } catch (_) {}
    Comandos.eco(pendiente.queja, "malo");
    return false;
  }

  function terminarPeticion() {
    const q = pendiente;
    pendiente = null;
    Comandos.terminar();
    if (!q) return;
    const ids = [...estado.sel];
    // Lo picado para «una» se consume: si se quedara seleccionado, la
    // siguiente pregunta lo tomaría como selección previa (EMPALME: «son la
    // misma línea»).
    if (q.una) { estado.sel.clear(); refrescarPie(); }
    q.resolver(q.una ? ids[0] : ids);
  }

  function cancelarPeticion() {
    const q = pendiente;
    pendiente = null;
    estado.sel.clear();
    pintar();
    if (q) q.rechazar(new Error("cancelado"));
  }

  /* --- «¿Cuál de éstos?»  ·  lo pidió Mike el 2-sep ----------------------
   *
   * *«si al seleccionar algo hay varios elementos posibles, que saliera un
   * dropdown para escoger»*. En un plano de obra un clic cae encima de cuatro
   * cosas —el muro, su relleno, la cota y el texto— y la que gana por medio
   * milímetro casi nunca es la que uno quería. Sin esto, el remedio es hacer
   * zoom hasta separarlas.
   *
   * Cuándo sale y cuándo no, que es lo que decide si ayuda o estorba:
   *
   *   · Sale con un clic normal sobre **dos o más** cosas.
   *   · **No** sale al sumar a la selección (Shift o Ctrl) ni cuando un comando
   *     está pidiendo varias entidades: ahí se está barriendo, y un menú por
   *     clic sería insufrible.
   *   · Se apaga entero en las preferencias (`menu_seleccion`).
   *
   * Al pasar por encima de cada renglón se resalta esa entidad en el plano.
   * Es la mitad de la función: leer «Polilínea · 12 vértices» no dice cuál es;
   * verla encenderse, sí.
   */
  let menuAbierto = null;

  function cerrarMenu() {
    if (!menuAbierto) return;
    menuAbierto.caja.remove();
    document.removeEventListener("keydown", menuTecla, true);
    // El de «clic fuera» se quitaba solo al dispararse, pero al elegir una
    // opción se quedaba colgado del documento. Uno por menú abierto no se
    // nota; cien a lo largo de una tarde, sí.
    if (menuAbierto.fuera) {
      document.removeEventListener("mousedown", menuAbierto.fuera, true);
    }
    menuAbierto = null;
    estado.resaltado = null;
    pintar();
  }

  function menuTecla(e) {
    if (!menuAbierto) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cerrarMenu(); }
  }

  const NOMBRES = {
    linea: "Línea", polilinea: "Polilínea", circulo: "Círculo", arco: "Arco",
    elipse: "Elipse", spline: "Spline", punto: "Punto", texto: "Texto",
    textom: "Texto de párrafo", cota: "Cota", rayado: "Rayado",
    insercion: "Bloque", solido: "Sólido", imagen: "Imagen", cruda: "Del archivo",
  };

  let _vezMenu = 0;

  async function elegirEntre(lista, px, py) {
    cerrarMenu();
    /* **Un solo menú a la vez, aunque el usuario pique tres veces seguidas.**
     * Reportado por Mike: picó donde había seis cosas encimadas, salieron tres
     * menús y sólo se quitó el último. Lo que pasaba: aquí abajo se espera al
     * motor (`/api/entidades/resumen`), y si durante esa espera llega otro
     * clic, se arman dos menús — pero `menuAbierto` sólo recuerda el último,
     * y los anteriores se quedan huérfanos en la página. Ahora cada llamada
     * lleva su turno: si al volver del motor ya hubo otro clic, ésta se
     * retira sin armar nada; y antes de armar se cierra lo que hubiera. */
    const miVez = ++_vezMenu;

    /* La lista la manda el cliente; el motor sólo la **enriquece** con el tipo
     * y la medida. Se arma en este orden a propósito: si el motor no contesta,
     * o no reconoce un id, el menú sale igual con lo que ya se sabe. Al revés
     * —confiando en lo que devuelva el motor— un id que no reconociera
     * desaparecía del menú, y el clic no seleccionaba nada sin decir por qué. */
    const datos = lista.map((c) => {
      const tr = Indice.trazos(c.id)[0] || {};
      return { id: c.id, tipo: "", capa: tr.capa || "", detalle: "" };
    });
    try {
      const r = await post("/api/entidades/resumen", { ids: lista.map((c) => c.id) });
      const porId = new Map(r.entidades.map((d) => [d.id, d]));
      for (const d of datos) {
        const extra = porId.get(d.id);
        if (extra) Object.assign(d, extra);
      }
    } catch (_) { /* con lo del cliente alcanza para elegir */ }

    if (miVez !== _vezMenu) return null;        // ya hubo otro clic: me retiro
    if (datos.length < 2) return datos.length ? datos[0].id : null;

    return new Promise((resolver) => {
      cerrarMenu();                              // por si algo se coló mientras
      const caja = document.createElement("div");
      caja.className = "menu-sel";
      const hd = document.createElement("div");
      hd.className = "hd";
      hd.textContent = `${datos.length} elementos aquí`;
      caja.appendChild(hd);

      for (const d of datos) {
        const b = document.createElement("button");
        b.className = "op";
        const n = document.createElement("span");
        n.className = "n";
        n.textContent = NOMBRES[d.tipo] || d.tipo || "Entidad";
        const det = document.createElement("span");
        det.className = "det";
        det.textContent = d.detalle || "";
        const cp = document.createElement("span");
        cp.className = "cp";
        cp.textContent = d.capa || "";
        b.append(n, det, cp);
        b.onmouseenter = () => { estado.resaltado = d.id; pintar(); };
        b.onclick = () => { cerrarMenu(); resolver(d.id); };
        caja.appendChild(b);
      }

      // Junto al cursor, pero sin salirse de la ventana.
      caja.style.visibility = "hidden";
      document.body.appendChild(caja);
      const r = caja.getBoundingClientRect();
      const x = Math.min(px + 8, window.innerWidth - r.width - 8);
      const y = Math.min(py + 8, window.innerHeight - r.height - 8);
      caja.style.left = Math.max(8, x) + "px";
      caja.style.top = Math.max(8, y) + "px";
      caja.style.visibility = "";

      // Un clic fuera cancela, como cualquier menú. Se engancha en el turno
      // siguiente para que no lo cierre el mismo clic que lo abrió.
      setTimeout(() => {
        const fuera = (ev) => {
          if (caja.contains(ev.target)) return;
          document.removeEventListener("mousedown", fuera, true);
          if (menuAbierto && menuAbierto.caja === caja) cerrarMenu();
          else caja.remove();                    // era de otro turno: se va solo
          resolver(null);
        };
        document.addEventListener("mousedown", fuera, true);
        if (menuAbierto && menuAbierto.caja === caja) menuAbierto.fuera = fuera;
      }, 0);
      document.addEventListener("keydown", menuTecla, true);
      menuAbierto = { caja };
    });
  }

  /* --- Ratón -------------------------------------------------------------- */
  async function clicAbajo(e, p) {
    // ¿Agarró un grip de algo ya seleccionado?  ·  feature 42
    const g = gripBajoCursor(p);
    if (g) { gripArrastrado = g; return true; }
    cajaSel = { a: p, b: p, arrastrando: false };
    return false;
  }

  async function clicArriba(e, p) {
    if (gripArrastrado) {
      // El punto bueno es el que se calculó al mover —con referencia a objeto,
      // ortho y rejilla—, no el crudo del ratón. Si se usara el crudo, el
      // marcador verde diría una cosa y el extremo caería en otra.
      await soltarGrip(gripArrastrado.destino || puntoDeGrip(p));
      gripArrastrado = null;
      estado.ref = null;
      return;
    }
    if (!cajaSel) return;
    const arrastro = Math.hypot(p[0] - cajaSel.a[0], p[1] - cajaSel.a[1]) >
                     6 / estado.vista.escala;
    /* Sumar a la selección es con **Shift**, como pidió Mike el 4-sep, y
     * Ctrl queda libre para otras cosas. No choca con el ortho momentáneo:
     * Shift invierte el ortho sólo **mientras se toma un punto**, y sumar a la
     * selección pasa fuera de cualquier comando. Son dos momentos distintos.
     * (Antes fue Ctrl porque Shift+arrastrar era el pan; ya no lo es.) */
    const sumar = e.shiftKey;

    if (!arrastro) {
      cajaSel = null;
      estado.hule = null;
      const lista = candidatos(p);
      if (!lista.length) { if (!sumar) limpiar(); return; }

      let id = lista[0].id;
      const conMenu = lista.length > 1 && !sumar &&
                      !(pendiente && !pendiente.una) &&
                      (estado.prefs || {}).menu_seleccion !== false;
      if (conMenu) {
        id = await elegirEntre(lista, e.clientX, e.clientY);
        if (!id) return;                    // se cerró sin elegir
      }
      if (pendiente && !(await aceptable(id))) { pintar(); return; }
      alternar(id, sumar, e);
      return;
    }

    const cruce = p[0] < cajaSel.a[0];      // de derecha a izquierda = cruce
    const caja = [Math.min(cajaSel.a[0], p[0]), Math.min(cajaSel.a[1], p[1]),
                  Math.max(cajaSel.a[0], p[0]), Math.max(cajaSel.a[1], p[1])];
    if (!sumar) estado.sel.clear();
    for (const id of idsVisibles()) {
      if (dentroDeCaja(id, caja, cruce)) estado.sel.add(id);
    }
    // Una ventana que atrapa a un miembro se lleva su grupo entero.
    for (const id of [...estado.sel]) {
      for (const i of conGrupo(id)) estado.sel.add(i);
    }
    cajaSel = null;
    estado.hule = null;
    refrescarPie();
    Comandos.eco(`${estado.sel.size} entidad(es) por ${cruce ? "cruce" : "ventana"}.`);
    if (pendiente && pendiente.una && estado.sel.size) terminarPeticion();
    pintar();
  }

  function alMover(p) {
    if (gripArrastrado) {
      gripArrastrado.destino = puntoDeGrip(p);
      estado.hule = vistaPreviaGrip(gripArrastrado.destino);
      pintar();
      return true;
    }
    if (!cajaSel) return false;
    cajaSel.b = p;
    const cruce = p[0] < cajaSel.a[0];
    estado.hule = { tipo: "caja", a: cajaSel.a, b: p, punteado: cruce };
    pintar();
    return true;
  }

  /* --- Grips  ·  feature 42 ---------------------------------------------- */
  /* Los puntos que se pueden jalar de cada entidad. Sin esto, mover un extremo
   * de una línea obliga a borrarla y volverla a dibujar. */
  const gripsDe = (id) => Indice.gripsGuardados(id, _gripsDe);

  function _gripsDe(id) {
    const prims = primitivasDe(id);
    const pts = [];
    // Grips en los puntos medios de cada tramo recto (Mike, 9-sep-2026):
    // jalarlo traslada el tramo tal cual, y en una polilínea se llevan los
    // extremos de los dos tramos vecinos. Van aparte de los vértices para que
    // se pinten distinto y para saber qué tramo es. Sólo en líneas y
    // polilíneas: un tramo con bulge no se traslada sin deformarse.
    const medios = [];
    const esLineal = prims.length && prims.every((pr) => pr.tipo === "seg") &&
      !prims.some((pr) => pr.aprox || pr.cota);
    for (const pr of prims) {
      if (pr.tipo === "seg") {
        pts.push(pr.a, pr.b);
        if (esLineal) medios.push({ p: [(pr.a[0] + pr.b[0]) / 2, (pr.a[1] + pr.b[1]) / 2], a: pr.a, b: pr.b });
      }
      else if (pr.tipo === "arco") {
        pts.push(pr.c);
        if (Math.abs(pr.a1 - pr.a0) % 360 > 1e-9) {
          const rad = (g) => g * Math.PI / 180;
          pts.push([pr.c[0] + pr.r * Math.cos(rad(pr.a0)), pr.c[1] + pr.r * Math.sin(rad(pr.a0))]);
          pts.push([pr.c[0] + pr.r * Math.cos(rad(pr.a1)), pr.c[1] + pr.r * Math.sin(rad(pr.a1))]);
        } else {
          pts.push([pr.c[0] + pr.r, pr.c[1]], [pr.c[0], pr.c[1] + pr.r]);
        }
      } else if (pr.tipo === "punto") pts.push(pr.p);
    }
    // sin repetidos: los vértices de una polilínea salen dos veces
    const vistos = new Set();
    const salida = pts.filter((q) => {
      const k = `${q[0].toFixed(6)},${q[1].toFixed(6)}`;
      if (vistos.has(k)) return false;
      vistos.add(k);
      return true;
    });
    salida.medios = medios;
    return salida;
  }

  const gripsMedios = (id) => gripsDe(id).medios || [];

  function gripBajoCursor(p) {
    if (!estado.sel.size) return null;
    const tol = 7 / estado.vista.escala;
    for (const id of estado.sel) {
      for (const q of gripsDe(id)) {
        if (Math.hypot(q[0] - p[0], q[1] - p[1]) <= tol) return { id, punto: q };
      }
    }
    // Los del medio van después: en un tramo cortito el vértice gana.
    for (const id of estado.sel) {
      for (const m of gripsMedios(id)) {
        if (Math.hypot(m.b[0] - m.a[0], m.b[1] - m.a[1]) * estado.vista.escala < 26) continue;
        if (Math.hypot(m.p[0] - p[0], m.p[1] - p[1]) <= tol) return { id, punto: m.p, medio: m };
      }
    }
    return null;
  }

  /* Jalar un grip es tomar un punto como cualquier otro: tiene que engancharse
   * al extremo de la línea de al lado, respetar ortho y caer en la rejilla. Sin
   * esto —que era el caso— mover un extremo para unirlo a otro sólo funcionaba
   * de vista, y dos líneas que parecen tocarse pero no se tocan no cierran un
   * contorno, no se unen con UNIR y no se cortan bien en la CNC.
   *
   * La propia entidad se excluye de la búsqueda: su extremo está debajo del
   * cursor y ganaría siempre, dejando el grip clavado en su sitio. */
  function puntoDeGrip(p) {
    const g = gripArrastrado;
    const prefs = estado.prefs || {};
    const ref = Osnap.buscar(p, g.punto, new Set([g.id]));
    estado.ref = ref;
    if (ref) return ref.p;
    let q = p;
    if (orthoActivo()) {
      const dx = q[0] - g.punto[0], dy = q[1] - g.punto[1];
      q = Math.abs(dx) >= Math.abs(dy) ? [q[0], g.punto[1]] : [g.punto[0], q[1]];
    }
    if (prefs.snap_rejilla) {
      const s = (prefs.snap_paso || 10) / mmPorUnidad();   // el paso se guarda en mm
      q = [Math.round(q[0] / s) * s, Math.round(q[1] / s) * s];
    }
    return q;
  }

  function vistaPreviaGrip(p) {
    const g = gripArrastrado;
    if (g.medio) {
      // El tramo entero, corrido tal cual, para ver dónde va a quedar.
      const dx = p[0] - g.punto[0], dy = p[1] - g.punto[1];
      return { partes: [{ tipo: "linea", a: [g.medio.a[0] + dx, g.medio.a[1] + dy], b: [g.medio.b[0] + dx, g.medio.b[1] + dy] },
                        { tipo: "linea", a: g.punto, b: p },
                        { tipo: "marca", p }] };
    }
    return { partes: [{ tipo: "linea", a: g.punto, b: p },
                      { tipo: "marca", p }] };
  }

  /* Al soltar, se le pide al servidor la entidad, se ve qué parte suya era ese
   * grip, y se cambia sólo eso. Preguntar en vez de adivinar evita el error
   * clásico: mover el centro de un círculo creyendo que era su radio. */
  async function soltarGrip(p) {
    const { id, punto, medio } = gripArrastrado;
    estado.hule = null;
    let ent;
    try { ent = await api(`/api/entidad/${id}`); } catch (_) { return; }
    const igual = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6;
    const cambios = {};

    if (medio) {
      // El grip del medio traslada el tramo tal cual: sus dos extremos se
      // corren lo mismo. En una polilínea esos dos extremos son también los
      // de los tramos vecinos, que así siguen conectados (Mike, 9-sep-2026).
      const dx = p[0] - punto[0], dy = p[1] - punto[1];
      if (Math.hypot(dx, dy) < 1e-9) return;
      if (ent.tipo === "linea") {
        cambios.p1 = [ent.p1[0] + dx, ent.p1[1] + dy];
        cambios.p2 = [ent.p2[0] + dx, ent.p2[1] + dy];
      } else if (ent.tipo === "polilinea") {
        const puntos = ent.puntos.map((v) => v.slice());
        const n = puntos.length;
        let toco = false;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n;
          if (j === 0 && !ent.cerrada) break;
          const a = [puntos[i][0], puntos[i][1]], b = [puntos[j][0], puntos[j][1]];
          if ((igual(a, medio.a) && igual(b, medio.b)) || (igual(a, medio.b) && igual(b, medio.a))) {
            puntos[i][0] += dx; puntos[i][1] += dy;
            puntos[j][0] += dx; puntos[j][1] += dy;
            toco = true;
            break;
          }
        }
        if (toco) cambios.puntos = puntos;
      } else return;
    } else if (ent.tipo === "linea") {
      if (igual(ent.p1, punto)) cambios.p1 = p;
      else if (igual(ent.p2, punto)) cambios.p2 = p;
    } else if (ent.tipo === "polilinea") {
      const puntos = ent.puntos.map((v) => v.slice());
      const i = puntos.findIndex((v) => igual([v[0], v[1]], punto));
      if (i >= 0) { puntos[i][0] = p[0]; puntos[i][1] = p[1]; cambios.puntos = puntos; }
    } else if (ent.tipo === "circulo") {
      if (igual(ent.centro, punto)) cambios.centro = p;
      else cambios.radio = Math.hypot(p[0] - ent.centro[0], p[1] - ent.centro[1]);
    } else if (ent.tipo === "arco") {
      if (igual(ent.centro, punto)) cambios.centro = p;
      else {
        const ang = (Math.atan2(p[1] - ent.centro[1], p[0] - ent.centro[0]) * 180 / Math.PI + 360) % 360;
        const rad = (g) => g * Math.PI / 180;
        const pIni = [ent.centro[0] + ent.radio * Math.cos(rad(ent.ang_ini)),
                      ent.centro[1] + ent.radio * Math.sin(rad(ent.ang_ini))];
        if (igual(pIni, punto)) cambios.ang_ini = ang; else cambios.ang_fin = ang;
      }
    } else if (ent.tipo === "cota") {
      // Jalar un punto de definición: el de la línea de cota la acerca o la
      // aleja; uno medido se despega de la pieza (la liga se suelta) y mide
      // desde donde se dejó.
      const puntos = ent.puntos.map((v) => v.slice());
      const i = puntos.findIndex((v) => igual([v[0], v[1]], punto));
      if (i >= 0) {
        puntos[i] = [p[0], p[1]];
        cambios.puntos = puntos;
        const liga = (ent.liga || []).slice();
        if (liga[i]) { liga[i] = null; cambios.liga = liga; }
      }
    } else if (ent.tipo === "punto") {
      cambios.p = p;
    } else if (ent.tipo === "spline") {
      const pts = (ent.puntos_ajuste || []).map((v) => v.slice());
      const i = pts.findIndex((v) => igual(v, punto));
      if (i >= 0) { pts[i] = p; cambios.puntos_ajuste = pts; }
    }
    if (!Object.keys(cambios).length) return;
    const r = await patch(`/api/entidad/${id}`, { cambios });
    aplicar(r);
    if (!aplicarParche(r)) await recargarTrazos();
  }

  /* --- Pintado ------------------------------------------------------------ */
  /* Cuántas entidades seleccionadas enseñan grips. Es el GRIPOBJLIMIT de
   * AutoCAD, y su valor por omisión es justamente 100: con más, no hay grips.
   * Con 5 000 seleccionadas eran 20 000 cuadritos por cuadro —1.5 segundos
   * por cada movimiento del ratón—, y nadie va a jalar un grip entre cinco
   * mil. Autodesk documenta exactamente esta caída de rendimiento. */
  const TOPE_GRIPS = 100;

  /* --- La selección como imagen ------------------------------------------
   *
   * Mike, 6-sep, con un grupo de 1 200 partes seleccionado: *«ya con algo
   * seleccionado regresa la lentitud; al parecer la selección se sigue
   * dibujando con cada movimiento del mouse»*. Exacto: el resaltado se
   * re-trazaba en cada cuadro de la capa de encima —cada movimiento del
   * ratón—, y con mil entidades son decenas de miles de vértices por cuadro.
   *
   * Ahora el resaltado (y los grips) se pintan **una vez** en un lienzo
   * aparte y de ahí se copian mientras no cambie ni la selección ni la vista.
   * Y en medio de un pan o una rueda se corre esa imagen igual que la foto
   * del plano (ver Regen en vista.js): cuesta lo mismo con una entidad que
   * con diez mil. Sólo se rehace al soltar. */
  let fotoSel = null;        // canvas con el resaltado
  let fotoSelLlave = "";     // con qué selección y vista se pintó
  let fotoSelVista = null;   // {x, y, escala, w, h, dpr}
  const UMBRAL_FOTO_SEL = 12; // con menos seleccionadas se pinta directo

  function pintarSeleccion(ctx) {
    if (estado.resaltado) pintarResaltado(ctx, estado.resaltado);
    if (!estado.sel.size) return;
    if (!(estado.sel instanceof SelSet)) estado.sel = new SelSet(estado.sel);
    // Con cuatro ventanas nunca se usa la foto: se pinta directo en cada una.
    if (estado.sel.size < UMBRAL_FOTO_SEL || typeof Ventanas !== "undefined") { _pintarSeleccionDirecto(ctx); return; }

    const v = estado.vista, dpr = window.devicePixelRatio || 1;
    const w = lienzo.width, h = lienzo.height;
    const llave = `${estado.sel.v}|${estado.sel.size}|${v.x}|${v.y}|${v.escala}|${w}|${h}|${tema().cual}|${estado.trazos.length}`;
    const enGesto = typeof Regen !== "undefined" && Regen.enGesto;
    const mismaSel = fotoSelVista && fotoSelLlave.split("|", 2).join("|") === `${estado.sel.v}|${estado.sel.size}` &&
                     fotoSelVista.w === w && fotoSelVista.h === h && fotoSelVista.trazos === estado.trazos;

    if (llave !== fotoSelLlave && !(enGesto && mismaSel)) {
      // Rehacer la imagen de la selección.
      if (!fotoSel) fotoSel = document.createElement("canvas");
      if (fotoSel.width !== w || fotoSel.height !== h) { fotoSel.width = w; fotoSel.height = h; }
      const fc = fotoSel.getContext("2d");
      fc.setTransform(1, 0, 0, 1, 0, 0);
      fc.clearRect(0, 0, w, h);
      fc.setTransform(dpr, 0, 0, dpr, 0, 0);
      _pintarSeleccionDirecto(fc);
      fotoSelLlave = llave;
      fotoSelVista = { x: v.x, y: v.y, escala: v.escala, w, h, dpr, trazos: estado.trazos };
    }
    // Copiar la imagen, corrida y escalada si la vista ya no es la de la foto.
    const f = fotoSelVista;
    const k = v.escala / f.escala;
    const dx = (f.x - v.x) * v.escala, dy = (v.y - f.y) * v.escala;
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(fotoSel, dx, dy, (f.w / f.dpr) * k, (f.h / f.dpr) * k);
    ctx.restore();
  }

  function _pintarSeleccionDirecto(ctx) {
    const T = tema();
    const esc = estado.vista.escala, vx = estado.vista.x, vy = estado.vista.y;
    // Lo que cabe en pantalla, con holgura: lo seleccionado fuera de la vista
    // no se pinta, igual que en el pintor del plano.
    const anchoPX = lienzo.clientWidth, altoPX = lienzo.clientHeight;
    const mx0 = vx - 20 / esc, mx1 = vx + anchoPX / esc + 20 / esc;
    const my1 = vy + 20 / esc, my0 = vy - altoPX / esc - 20 / esc;
    // Girada, o en un plano que no es el suelo, la ventana en planta no dice
    // qué se ve: se pinta todo. Y cada entidad va por su plano, con la cámara.
    const girada = !!(estado.vista.rx || estado.vista.rz) || (estado.vista.plano && estado.vista.plano !== "XY");
    const planoDe = (id) => { const tt = estado.trazos.find((x) => x.id === id); return (tt && tt.plano) || "XY"; };
    const seVe = (c) => girada || (c && !(c[2] < mx0 || c[0] > mx1 || c[3] < my0 || c[1] > my1));

    ctx.save();
    // resaltado: se repinta encima lo seleccionado, con línea gruesa y clara.
    //
    // Se recorren **los ids seleccionados**, no los trazos del plano, y de
    // ésos sólo los que caen en pantalla. La transformación va escrita a mano,
    // sin `aPX`: crear un arreglo por vértice sesenta veces por segundo es lo
    // que se sentía como arrastre con muchas cosas seleccionadas.
    ctx.strokeStyle = T.acc2;
    ctx.lineWidth = 3;
    ctx.globalAlpha = 0.45;
    ctx.beginPath();
    for (const id of estado.sel) {
      if (!seVe(Indice.caja(id))) continue;
      for (const t of Indice.trazos(id)) {
        if (t.clase === "insercion" && t.caja) {
          // Un bloque pesado se resalta por su caja: sus 50 000 vértices no
          // están aquí, están en la definición (ver Bloques en vista.js).
          const b = t.caja;
          ctx.rect((b[0] - vx) * esc, (vy - b[3]) * esc, (b[2] - b[0]) * esc, (b[3] - b[1]) * esc);
          continue;
        }
        if (t.clase !== "linea") continue;
        const pts = t.puntos;
        for (let i = 0; i < pts.length; i++) {
          const mp = Planos.aMundo(t.plano || "XY", pts[i][0], pts[i][1], 0);
          const qp = aPX(mp[0], mp[1], mp[2]);
          const px = qp[0], py = qp[1];
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
      }
    }
    ctx.stroke();
    ctx.globalAlpha = 1;

    // grips, sólo con pocas seleccionadas
    if (estado.sel.size <= TOPE_GRIPS) {
      ctx.fillStyle = T.acc2;
      ctx.strokeStyle = T.panel;
      ctx.lineWidth = 1;
      for (const id of estado.sel) {
        if (!seVe(Indice.caja(id))) continue;
        for (const q of gripsDe(id)) {
          const mg = Planos.aMundo(planoDe(id), q[0], q[1], 0);
          const qg = aPX(mg[0], mg[1], mg[2]);
          const px = qg[0], py = qg[1];
          ctx.fillRect(px - 3.5, py - 3.5, 7, 7);
          ctx.strokeRect(px - 3.5, py - 3.5, 7, 7);
        }
      }
      // Los del medio: más chicos y huecos, para distinguirlos del vértice.
      // Sólo en tramos que en pantalla dan para ponerlo sin encimarse.
      ctx.fillStyle = T.panel;
      ctx.strokeStyle = T.acc2;
      for (const id of estado.sel) {
        if (!seVe(Indice.caja(id))) continue;
        for (const m of gripsMedios(id)) {
          if (Math.hypot(m.b[0] - m.a[0], m.b[1] - m.a[1]) * esc < 26) continue;
          const px = (m.p[0] - vx) * esc, py = (vy - m.p[1]) * esc;
          ctx.fillRect(px - 2.5, py - 2.5, 5, 5);
          ctx.strokeRect(px - 2.5, py - 2.5, 5, 5);
        }
      }
    }
    ctx.restore();
  }

  function pintarResaltado(ctx, id) {
    ctx.save();
    ctx.strokeStyle = tema().canto;
    ctx.lineWidth = 5;
    ctx.globalAlpha = 0.55;
    ctx.beginPath();
    for (const t of Indice.trazos(id)) {
      if (t.clase !== "linea") continue;
      for (let i = 0; i < t.puntos.length; i++) {
        const [px, py] = aPX(t.puntos[i][0], t.puntos[i][1]);
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
    }
    ctx.stroke();
    // Un texto no tiene línea que resaltar: se le marca la caja.
    const c = cajaDe(id);
    if (c) {
      const [x0, y1] = aPX(c[0], c[3]);
      const [x1, y0] = aPX(c[2], c[1]);
      ctx.globalAlpha = 0.9;
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 4]);
      ctx.strokeRect(x0 - 3, y1 - 3, x1 - x0 + 6, y0 - y1 + 6);
      ctx.setLineDash([]);
    }
    ctx.restore();
  }

  /* --- Teclado ------------------------------------------------------------ */
  function alTeclear(e) {
    if (e.key === "Enter" && pendiente) { terminarPeticion(); return true; }
    if (e.key === "Escape") {
      if (pendiente) { cancelarPeticion(); return true; }
      if (estado.sel.size) { limpiar(); return true; }
    }
    if ((e.key === "Delete" || e.key === "Supr") && estado.sel.size && !pendiente) {
      // Dentro de una caja de texto (el panel de propiedades, el cuadro
      // flotante) Supr borra letras, no entidades.
      const et = document.activeElement && document.activeElement.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(et)) return false;
      Comandos.correr("BORRAR");
      return true;
    }
    return false;
  }

  /** Repinta pie, panel y lienzo tras cambiar `estado.sel` desde fuera. */
  function refrescar() { refrescarPie(); pintar(); }

  return { pedir, pedirUna, limpiar, alternar, refrescar, clicAbajo, clicArriba, alMover,
           alTeclear, pintarSeleccion, cajaDe, bajoElCursor, gripsDe, gripsMedios, candidatos,
           primTocaCaja,
           get pidiendo() { return !!pendiente; } };
})();
