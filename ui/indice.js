/* Índice del dibujo: por entidad y por dónde cae en el plano.
 *
 * Nace de lo que reportó Mike el 2-sep: *«cuando selecciono algo se tarda en
 * reaccionar»*. El pintado ya iba rápido (0.12.0), pero **seleccionar** seguía
 * pesando, y la razón estaba a la vista en cuanto se busca:
 *
 *   · `pintarSeleccion` recorría **los 120 000 trazos** para encontrar los tres
 *     que están seleccionados — y desde la 0.12.0 eso pasa en cada movimiento
 *     del ratón, porque el resaltado vive en el lienzo de encima.
 *   · `gripsDe(id)` hacía `estado.geometria.filter(pr => pr.id === id)`: medio
 *     millón de comparaciones **por cada entidad seleccionada y por cuadro**.
 *     Con diez entidades agarradas son cinco millones de operaciones para
 *     mover el ratón un píxel.
 *   · `bajoElCursor` recorría todas las primitivas del plano, dos veces, en
 *     cada clic.
 *
 * Los tres son el mismo error: buscar recorriendo. Aquí se construye el índice
 * **una vez** y se consulta.
 *
 * **Cuándo se rehace.** Al cambiar el arreglo de trazos o el de geometría — y
 * se compara por identidad, no por contenido, porque `recargarTrazos` y
 * `aplicarParche` siempre crean arreglos nuevos (ver app.js). Es la misma regla
 * que usa el lienzo guardado en vista.js, y por el mismo motivo: es exacta y no
 * cuesta nada. Si alguien empuja dentro del arreglo en vez de reemplazarlo, el
 * índice se queda viejo — por eso está dicho aquí y por eso `t020` lo vigila.
 */

const Indice = (() => {
  let _trazos = null;        // el arreglo con el que se armó
  let _geom = null;
  let _porIdTrazos = null;   // id → trazos
  let _porIdGeom = null;     // id → primitivas
  let _cajas = null;         // id → caja en mm
  let _grips = null;         // id → puntos que se pueden jalar
  let _rejilla = null;       // celda → primitivas que la tocan
  let _grandes = null;       // primitivas que cruzan medio plano
  let _paso = 0;

  function agrupar(lista) {
    const m = new Map();
    for (const x of lista) {
      let a = m.get(x.id);
      if (!a) { a = []; m.set(x.id, a); }
      a.push(x);
    }
    return m;
  }

  /* --- La rejilla de búsqueda --------------------------------------------
   *
   * Una rejilla uniforme y no un árbol: un plano de obra reparte sus entidades
   * de forma bastante pareja, la rejilla se arma de una pasada y se consulta
   * con dos divisiones. Un R-tree sería mejor con entidades muy desiguales y
   * bastante más código que mantener.
   *
   * Lo que sí hay que cuidar: una línea de fachada de veinte metros toca
   * cientos de celdas, y meterla en todas cuesta más que buscarla. Las que
   * cruzan más de `MAX_CELDAS` se apartan en una lista que se mira siempre.
   * Son pocas por definición. */
  const OBJETIVO_POR_CELDA = 3;
  const MAX_CELDAS = 40;

  function cajaPrim(pr) {
    return Osnap.caja(pr);
  }

  function armarRejilla(geom) {
    _rejilla = new Map();
    _grandes = [];
    if (!geom.length) { _paso = 1; return; }

    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const pr of geom) {
      const c = cajaPrim(pr);
      if (c[0] < x0) x0 = c[0];
      if (c[1] < y0) y0 = c[1];
      if (c[2] > x1) x1 = c[2];
      if (c[3] > y1) y1 = c[3];
    }
    const ancho = Math.max(x1 - x0, 1e-6), alto = Math.max(y1 - y0, 1e-6);
    // Celdas para que caigan unas pocas primitivas en cada una.
    const celdas = Math.max(1, Math.round(geom.length / OBJETIVO_POR_CELDA));
    // Con un plano «plano» (una sola línea horizontal: alto ≈ 0) el paso salía
    // microscópico y una búsqueda con tolerancia recorría millones de celdas:
    // la página se congelaba al pedir el segundo punto (0.20.0). El paso no
    // baja de una milésima del lado mayor.
    _paso = Math.max(Math.sqrt((ancho * alto) / celdas), Math.max(ancho, alto) / 1000, 1e-6);
    _rejilla.x0 = x0;
    _rejilla.y0 = y0;

    for (const pr of geom) {
      const c = cajaPrim(pr);
      const i0 = Math.floor((c[0] - x0) / _paso), i1 = Math.floor((c[2] - x0) / _paso);
      const j0 = Math.floor((c[1] - y0) / _paso), j1 = Math.floor((c[3] - y0) / _paso);
      if ((i1 - i0 + 1) * (j1 - j0 + 1) > MAX_CELDAS) { _grandes.push(pr); continue; }
      for (let i = i0; i <= i1; i++) {
        for (let j = j0; j <= j1; j++) {
          const k = i + "," + j;
          let a = _rejilla.get(k);
          if (!a) { a = []; _rejilla.set(k, a); }
          a.push(pr);
        }
      }
    }
  }

  let _grupos = new Map();          // nombre del grupo → ids
  let _grupoDe = new Map();         // id → nombre del grupo

  function alDia() {
    if (_trazos === estado.trazos && _geom === estado.geometria) return;
    _trazos = estado.trazos;
    _geom = estado.geometria;
    _porIdTrazos = agrupar(_trazos || []);
    _porIdGeom = agrupar(_geom || []);
    // Los grupos vienen marcados en los trazos (`t.grupo`): con eso, picar un
    // miembro se vuelve picar el grupo sin preguntarle nada al motor.
    _grupos = new Map();
    _grupoDe = new Map();
    for (const t of _trazos || []) {
      if (!t.grupo || _grupoDe.has(t.id)) continue;
      _grupoDe.set(t.id, t.grupo);
      let a = _grupos.get(t.grupo);
      if (!a) { a = []; _grupos.set(t.grupo, a); }
      a.push(t.id);
    }
    _cajas = new Map();
    _grips = new Map();
    armarRejilla(_geom || []);
  }

  /** Las primitivas de una entidad. Antes era un filtro sobre todo el plano. */
  function primitivas(id) {
    alDia();
    return _porIdGeom.get(id) || [];
  }

  /** Los trazos de una entidad. */
  function trazos(id) {
    alDia();
    return _porIdTrazos.get(id) || [];
  }

  /** Todas las primitivas, tal cual vienen del motor (cada una con su
   *  `plano`). Para picar desde una ventana de otro plano, ver seleccion.js. */
  function todas() {
    alDia();
    return _geom || [];
  }

  /** Todos los ids que tienen geometría, sin repetir. */
  function ids() {
    alDia();
    return _porIdGeom.keys();
  }

  /** La caja de una entidad, en milímetros. */
  function caja(id) {
    alDia();
    let c = _cajas.get(id);
    if (c !== undefined) return c;
    const prims = _porIdGeom.get(id);
    if (!prims || !prims.length) { _cajas.set(id, null); return null; }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const pr of prims) {
      const [a, b, cc, d] = cajaPrim(pr);
      if (a < x0) x0 = a;
      if (b < y0) y0 = b;
      if (cc > x1) x1 = cc;
      if (d > y1) y1 = d;
    }
    c = [x0, y0, x1, y1];
    _cajas.set(id, c);
    return c;
  }

  /** Guarda los grips ya calculados de una entidad. Los calcula quien sabe
   *  cómo —ui/seleccion.js—; aquí sólo se recuerdan. */
  function gripsGuardados(id, calcular) {
    alDia();
    let g = _grips.get(id);
    if (g === undefined) {
      g = calcular(id);
      _grips.set(id, g);
    }
    return g;
  }

  /** Las primitivas que pueden estar a menos de `tol` del punto.
   *
   *  Devuelve candidatas, no respuestas: quien llama mide la distancia de
   *  verdad. Lo que se ahorra es mirar el plano entero. */
  function cerca(p, tol) {
    alDia();
    if (!_rejilla) return [];
    const x0 = _rejilla.x0, y0 = _rejilla.y0;
    const i0 = Math.floor((p[0] - tol - x0) / _paso);
    const i1 = Math.floor((p[0] + tol - x0) / _paso);
    const j0 = Math.floor((p[1] - tol - y0) / _paso);
    const j1 = Math.floor((p[1] + tol - y0) / _paso);
    // Una tolerancia que abarca miles de celdas (zoom muy alejado, o un plano
    // chico con tolerancia grande) sale más barata recorriendo la lista.
    if ((i1 - i0 + 1) * (j1 - j0 + 1) > 4096) return (_geom || []).slice();
    const vistas = new Set();
    const salida = [];
    for (let i = i0; i <= i1; i++) {
      for (let j = j0; j <= j1; j++) {
        const a = _rejilla.get(i + "," + j);
        if (!a) continue;
        for (const pr of a) {
          if (vistas.has(pr)) continue;
          vistas.add(pr);
          salida.push(pr);
        }
      }
    }
    for (const pr of _grandes) salida.push(pr);
    return salida;
  }

  /** Para las pruebas y para poder medir: cuántas celdas y cuántas grandes. */
  function estadisticas() {
    alDia();
    return { celdas: _rejilla ? _rejilla.size : 0, grandes: _grandes.length,
             paso: _paso, entidades: _porIdGeom.size };
  }

  /** El grupo de una entidad, o null. */
  function grupoDe(id) { alDia(); return _grupoDe.get(id) || null; }

  /** Los ids de un grupo. */
  function delGrupo(nombre) { alDia(); return _grupos.get(nombre) || []; }

  /** Rehacer el índice desde cero (REGEN). */
  function rehacer() { _trazos = null; _geom = null; alDia(); }

  /* --- Parchar el índice en vez de rehacerlo ---------------------------
   *
   * Cada operación reemplaza los arreglos de trazos y geometría (ver
   * `aplicarParche` en app.js), y hasta aquí eso obligaba a rearmar el índice
   * completo: 180 ms en la máquina de Mike con medio millón de primitivas,
   * **por cada línea que se movía**. Lo que cambió son unas cuantas entidades:
   * se quitan sus primitivas de las celdas donde estaban y se meten las
   * nuevas. La rejilla conserva su origen y su paso; una primitiva que cae
   * fuera del plano original simplemente usa celdas con índices nuevos.
   *
   * Si el parche es grande (más de una quinta parte del plano) se rehace
   * entero: parchar sería más lento que rearmar. */
  function _quitarDeCeldas(pr) {
    const c = cajaPrim(pr);
    const x0 = _rejilla.x0, y0 = _rejilla.y0;
    const i0 = Math.floor((c[0] - x0) / _paso), i1 = Math.floor((c[2] - x0) / _paso);
    const j0 = Math.floor((c[1] - y0) / _paso), j1 = Math.floor((c[3] - y0) / _paso);
    if ((i1 - i0 + 1) * (j1 - j0 + 1) > MAX_CELDAS) return false;   // estaba en «grandes»
    for (let i = i0; i <= i1; i++) {
      for (let j = j0; j <= j1; j++) {
        const a = _rejilla.get(i + "," + j);
        if (!a) continue;
        const k = a.indexOf(pr);
        if (k >= 0) a.splice(k, 1);
      }
    }
    return true;
  }

  function _meterEnCeldas(pr) {
    const c = cajaPrim(pr);
    const x0 = _rejilla.x0, y0 = _rejilla.y0;
    const i0 = Math.floor((c[0] - x0) / _paso), i1 = Math.floor((c[2] - x0) / _paso);
    const j0 = Math.floor((c[1] - y0) / _paso), j1 = Math.floor((c[3] - y0) / _paso);
    if ((i1 - i0 + 1) * (j1 - j0 + 1) > MAX_CELDAS) { _grandes.push(pr); return; }
    for (let i = i0; i <= i1; i++) {
      for (let j = j0; j <= j1; j++) {
        const k = i + "," + j;
        let a = _rejilla.get(k);
        if (!a) { a = []; _rejilla.set(k, a); }
        a.push(pr);
      }
    }
  }

  /** Actualizar el índice con un parche {quitar, trazos, geometria}, dados
   *  los arreglos nuevos ya puestos en `estado`. Devuelve true si parchó,
   *  false si tuvo que rehacer. */
  function parchar(p, trazosNuevos, geomNueva) {
    const quitar = new Set(p.quitar || []);
    const nuevaGeom = p.geometria || [];
    // Si el plano cambió entero desde la última vez que alguien preguntó (una
    // recarga completa sin ningún clic ni pintado en medio), la rejilla que
    // tenemos es de OTRO plano: parchar encima dejaba entidades borradas
    // «vivas» y las nuevas invisibles al clic. Se cazó el 13-sep-2026 con
    // t019: tras limpiar el dibujo y volver a cargar, el primer parche
    // seguía viendo las entidades viejas. alDia() rearma si hace falta.
    const cambioEntero = _trazos !== estado.trazos || _geom !== estado.geometria;
    // Sin rejilla armada de verdad (plano vacío: sin origen ni paso), o con un
    // parche grande, se rearma: parchar sería incorrecto o más lento.
    const grande = cambioEntero || !_rejilla || !_geom || _rejilla.x0 === undefined ||
      (quitar.size + nuevaGeom.length) > Math.max(2000, _geom.length / 5);
    if (grande) { _trazos = null; _geom = null; estado.trazos = trazosNuevos; estado.geometria = geomNueva; alDia(); return false; }

    // 1. Fuera lo viejo de los ids tocados.
    let hayGrandes = false;
    for (const id of quitar) {
      const prims = _porIdGeom.get(id);
      if (prims) for (const pr of prims) { if (!_quitarDeCeldas(pr)) hayGrandes = true; }
      _porIdGeom.delete(id);
      _porIdTrazos.delete(id);
      _cajas.delete(id);
      _grips.delete(id);
      const g = _grupoDe.get(id);
      if (g) {
        _grupoDe.delete(id);
        const lista = _grupos.get(g);
        if (lista) { const k = lista.indexOf(id); if (k >= 0) lista.splice(k, 1); if (!lista.length) _grupos.delete(g); }
      }
    }
    if (hayGrandes) _grandes = _grandes.filter((pr) => !quitar.has(pr.id));

    // 2. Dentro lo nuevo.
    for (const pr of nuevaGeom) {
      let a = _porIdGeom.get(pr.id);
      if (!a) { a = []; _porIdGeom.set(pr.id, a); }
      a.push(pr);
      _meterEnCeldas(pr);
    }
    for (const t of p.trazos || []) {
      let a = _porIdTrazos.get(t.id);
      if (!a) { a = []; _porIdTrazos.set(t.id, a); }
      a.push(t);
      if (t.grupo && !_grupoDe.has(t.id)) {
        _grupoDe.set(t.id, t.grupo);
        let g = _grupos.get(t.grupo);
        if (!g) { g = []; _grupos.set(t.grupo, g); }
        g.push(t.id);
      }
    }
    // 3. El índice ya corresponde a los arreglos nuevos.
    estado.trazos = trazosNuevos;
    estado.geometria = geomNueva;
    _trazos = trazosNuevos;
    _geom = geomNueva;
    return true;
  }

  return { primitivas, trazos, ids, todas, caja, gripsGuardados, cerca, estadisticas,
           grupoDe, delGrupo, rehacer, parchar };
})();
