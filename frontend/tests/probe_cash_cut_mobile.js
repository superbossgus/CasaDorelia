/**
 * El corte de caja en viewport de telefono (BOS-153, paso 9 de BOS-150).
 *
 * El paso 9 del plan de BOS-150 era el unico que no se podia correr sin un
 * navegador. Esto es ese paso, hecho probe re-corrible, como se hizo con
 * `backend/tests/probe_cash_cut_api.py`.
 *
 * Hay cinco cosas que **ninguna** prueba del modulo ni ninguna busqueda en el
 * bundle puede demostrar, y las cinco tocan la pantalla donde se captura
 * dinero de pie y con prisa:
 *
 * 1. Que `inputMode` llegue al **DOM renderizado**. En el bundle es texto; en
 *    el DOM es lo que decide si el telefono abre el teclado numerico.
 * 2. Que el numero derivado se lea a 390 px sin hacer zoom.
 * 3. Que el selector de turno se pueda **tocar** (no clicar) con el pulgar.
 * 4. Que al cambiar de turno el formulario aparezca: el defecto 1 de BOS-150
 *    dejaba la tarde sin capturar con el dia rotulado como completo.
 * 5. Que el total del dia no se corte ni desborde a ese ancho.
 *
 * ### Correrlo
 *
 * Necesita tres cosas vivas: un mongod desechable, el backend apuntado a el, y
 * el build de produccion servido en el origen que el backend acepta en
 * `CORS_ORIGINS`. Elige puertos propios: si otra corrida del mismo equipo usa
 * los mismos, los dos backends escriben cortes en la misma base y los montos
 * del caso 5 dejan de cuadrar.
 *
 *     # 1. mongod desechable
 *     mongod --port 27018 --dbpath <tmp> --bind_ip 127.0.0.1
 *
 *     # 2. backend (ver el docstring de probe_cash_cut_api.py: el stub de
 *     #    `emergentintegrations` va en PYTHONPATH, y `EmailStr` rechaza `.test`)
 *     MONGO_URL=mongodb://127.0.0.1:27018 DB_NAME=cash_cut_bos153 \
 *       JWT_SECRET=... CORS_ORIGINS=http://localhost:3757 \
 *       python -m uvicorn server:app --port 8757
 *
 *     # 3. el fixture. `probe_cash_cut_api.py` no se corre entero aqui: al
 *     #    terminar hace `drop_database` y se lleva lo que el navegador
 *     #    necesita vivo. Se le reusa `seed()` y se captura el turno
 *     #    `completo`, que es el fixture del caso 4:
 *     #
 *     #      import probe_cash_cut_api as probe, business_day
 *     #      probe.seed(db, business_day.today())
 *     #      httpx.post(f"{probe.BASE}/cash-cuts", headers=probe.login(...),
 *     #                 json={"cafeteria_id": "c-sji", "fondo_inicial": 500,
 *     #                       "efectivo_contado": 2300, "retiros": 0})
 *
 *     # 4. el build servido con fallback de SPA, y este probe
 *     REACT_APP_BACKEND_URL=http://127.0.0.1:8757 yarn build
 *     BOS153_BASE=http://localhost:3757 BOS153_API=http://127.0.0.1:8757/api \
 *       node frontend/tests/probe_cash_cut_mobile.js ./shots
 *
 * Se corre con el **build de produccion**, no con el dev server: lo que se
 * quiere ver es lo que la sucursal va a abrir.
 *
 * Necesita `puppeteer-core` y un Chrome instalado (`BOS153_CHROME` lo apunta).
 * No se agrega a las dependencias del frontend a proposito: es una herramienta
 * de verificacion, no algo que la app necesite para correr. Se instala aparte
 * y se le dice por donde:
 *
 *     npm install puppeteer-core@23 --prefix <tmp>
 *     NODE_PATH=<tmp>/node_modules node frontend/tests/probe_cash_cut_mobile.js ./shots
 */
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const CHROME = process.env.BOS153_CHROME || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.BOS153_BASE || "http://localhost:3757";
const API = process.env.BOS153_API || "http://127.0.0.1:8757/api";
const SHOTS = process.argv[2] || "./shots";
const EMAIL = process.env.BOS153_EMAIL || "cajero.sji@probe-cash-cut.com";
const PASSWORD = process.env.BOS153_PASSWORD || "probe-local-no-produccion";

// 390x844 es el iPhone 14/15/16. El alto importa tanto como el ancho: lo que
// cae abajo del pliegue es lo que la cajera no ve sin hacer scroll.
const VIEWPORT = { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true };
const UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " +
  "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";

const TOUCH_MIN = 44; // Apple HIG y WCAG 2.5.5 (AAA): 44 px de lado minimo
const FONT_MIN = 28; // el minimo que pide BOS-153 para el numero derivado

const results = [];
function check(step, name, ok, detail) {
  results.push({ step, name, ok: Boolean(ok), detail });
  console.log(`  [${ok ? "PASS" : "FALLA"}] ${name}: ${detail}`);
}

async function shot(page, name, note) {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
  console.log(`  [shot] ${name}.png -- ${note}`);
}

const settle = (ms) => new Promise((r) => setTimeout(r, ms));

async function metrics(page, selector) {
  return page.$eval(selector, (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    // El numero grande es un hijo del contenedor: interesa el mayor font-size
    // de la rama, que es el que se lee de lejos.
    let maxFont = parseFloat(cs.fontSize);
    for (const d of el.querySelectorAll("*")) {
      const f = parseFloat(getComputedStyle(d).fontSize);
      if (f > maxFont && d.textContent.trim()) maxFont = f;
    }
    return {
      x: Math.round(r.x), y: Math.round(r.y),
      width: Math.round(r.width), height: Math.round(r.height),
      maxFont,
      scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
      scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
      text: el.textContent.trim().replace(/\s+/g, " ").slice(0, 200),
    };
  });
}

async function scrollIntoView(page, selector) {
  await page.$eval(selector, (el) => el.scrollIntoView({ block: "center" }));
  // Medir el rect antes de que termine el scroll da coordenadas viejas y el
  // tap cae fuera del elemento.
  await settle(400);
}

/** Tap real, no click de raton: el Select de Radix mira el tipo de puntero. */
async function tap(page, selector) {
  const c = await page.$eval(selector, (el) => {
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  await page.touchscreen.tap(c.x, c.y);
  await settle(500);
}

async function pickTurno(page, value) {
  await scrollIntoView(page, "[data-testid=cash-cut-turno]");
  await tap(page, "[data-testid=cash-cut-turno]");
  await page.waitForSelector("[role=option]", { timeout: 8000 });
  // El popover se posiciona con animacion; sin este respiro se mide donde no es.
  await settle(600);
  for (const o of await page.$$("[role=option]")) {
    const txt = await o.evaluate((el) => el.textContent.trim());
    if (txt.toLowerCase().startsWith(value)) {
      const c = await o.evaluate((el) => {
        const b = el.getBoundingClientRect();
        return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
      });
      await page.touchscreen.tap(c.x, c.y);
      await settle(1200);
      return txt;
    }
  }
  throw new Error(`no aparecio la opcion de turno ${value}`);
}

async function typeInto(page, selector, value) {
  await scrollIntoView(page, selector);
  await page.click(selector, { clickCount: 3 }).catch(() => {});
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  await page.keyboard.type(String(value), { delay: 20 });
  await settle(300);
}

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: VIEWPORT,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setUserAgent(UA);
  await page.setViewport(VIEWPORT);

  try {
    // El token es el del login real del backend; AuthContext lo lee de localStorage.
    await page.goto(`${BASE}/admin`, { waitUntil: "networkidle2", timeout: 60000 });
    const auth = await page.evaluate(
      async (api, email, password) => {
        const r = await fetch(`${api}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!r.ok) return { ok: false, status: r.status, body: (await r.text()).slice(0, 200) };
        const d = await r.json();
        localStorage.setItem("token", d.token);
        return { ok: true, role: d.user.role, cafeteria_id: d.user.cafeteria_id };
      },
      API, EMAIL, PASSWORD
    );
    if (!auth.ok) throw new Error(`login fallo: HTTP ${auth.status} ${auth.body}`);
    check(0, "login real de cajero de SJI", auth.role === "cajero" && auth.cafeteria_id === "c-sji",
      `role=${auth.role} cafeteria=${auth.cafeteria_id}`);

    await page.goto(`${BASE}/corte-caja`, { waitUntil: "networkidle2", timeout: 60000 });
    await page.waitForSelector("[data-testid=cash-cut-turno]", { timeout: 30000 });
    await settle(1200);

    // ===== Caso 4a: el turno ya capturado no ofrece capturar otra vez =====
    const existingBefore = await page.$("[data-testid=cash-cut-existing]");
    const formBefore = await page.$("[data-testid=cash-cut-fondo]");
    check(4, "con `completo` capturado sale el corte, no el formulario",
      Boolean(existingBefore) && !formBefore,
      `existing=${Boolean(existingBefore)} formulario=${Boolean(formBefore)}`);
    await shot(page, "caso4a-turno-completo-ya-capturado", "turno `completo`: corte existente");

    const captured = await metrics(page, "[data-testid=cash-cut-turnos-captured]");
    check(4, "el renglon dice cuantos turnos van",
      /1 turno\(s\) contado\(s\)/.test(captured.text), JSON.stringify(captured.text));

    // ===== Caso 3: el selector de turno con el pulgar =====================
    const turno = await metrics(page, "[data-testid=cash-cut-turno]");
    check(3, `el selector de turno tiene area de toque >= ${TOUCH_MIN}px`,
      turno.height >= TOUCH_MIN, `alto=${turno.height}px ancho=${turno.width}px`);
    check(3, "el selector cae dentro del ancho del telefono",
      turno.x >= 0 && turno.x + turno.width <= VIEWPORT.width,
      `x=${turno.x} ancho=${turno.width}`);
    await scrollIntoView(page, "[data-testid=cash-cut-turno]");
    await shot(page, "caso3-selector-turno-area-de-toque", `${turno.width}x${turno.height} px`);
    await tap(page, "[data-testid=cash-cut-turno]");
    const options = await page.$$eval("[role=option]", (els) =>
      els.map((e) => ({ text: e.textContent.trim(), height: Math.round(e.getBoundingClientRect().height) }))
    );
    check(3, "se abre con un tap y ofrece los cuatro turnos", options.length === 4,
      options.map((o) => `${o.text}(${o.height}px)`).join(" | "));
    await shot(page, "caso3b-selector-turno-abierto", "el selector abierto de un tap");
    await page.keyboard.press("Escape");
    await settle(500);

    // ===== Caso 4b: cambiar de turno abre el formulario ===================
    const picked = await pickTurno(page, "vespertino");
    await page.waitForSelector("[data-testid=cash-cut-fondo]", { timeout: 15000 });
    check(4, "al cambiar a `vespertino` el formulario SI aparece (defecto de BOS-150)",
      Boolean(await page.$("[data-testid=cash-cut-fondo]")) &&
        !(await page.$("[data-testid=cash-cut-existing]")),
      `opcion tocada=${JSON.stringify(picked)}`);
    await shot(page, "caso4b-vespertino-formulario-abierto", "el formulario aparece");

    // ===== Caso 1: teclado numerico en el DOM renderizado =================
    const FIELDS = [
      ["cash-cut-fondo", "Fondo inicial"],
      ["cash-cut-contado", "Efectivo contado"],
      ["cash-cut-retiros", "Retiros"],
      ["cash-cut-tickets", "Cobros en efectivo"],
    ];
    const dom = [];
    for (const [testid, label] of FIELDS) {
      const a = await page.$eval(`[data-testid=${testid}]`, (el) => ({
        // getAttribute, no la propiedad: es lo que el DOM renderizado trae.
        type: el.getAttribute("type"),
        inputmode: el.getAttribute("inputmode"),
        height: Math.round(el.getBoundingClientRect().height),
        fontSize: parseFloat(getComputedStyle(el).fontSize),
      }));
      dom.push({ label, ...a });
      check(1, `${label}: type=number + inputmode en el DOM`,
        a.type === "number" && Boolean(a.inputmode),
        `type=${a.type} inputmode=${a.inputmode}`);
    }
    const short = dom.filter((f) => f.height < TOUCH_MIN);
    check(1, `los cuatro campos tienen alto de toque >= ${TOUCH_MIN}px`, short.length === 0,
      short.length ? short.map((f) => `${f.label}=${f.height}px`).join(", ")
        : `altos ${dom.map((f) => f.height).join("/")}px`);
    // iOS hace zoom solo si el campo baja de 16px, y eso descoloca la pantalla.
    const zoomy = dom.filter((f) => f.fontSize < 16);
    check(1, "ningun campo baja de 16px (iOS haria zoom al enfocarlo)", zoomy.length === 0,
      `font-size ${dom.map((f) => f.fontSize).join("/")}px`);
    await scrollIntoView(page, "[data-testid=cash-cut-fondo]");
    await shot(page, "caso1-campos-teclado-numerico", "los cuatro campos de captura");

    // ===== Caso 2: el numero derivado =====================================
    await typeInto(page, "[data-testid=cash-cut-fondo]", 500);
    await typeInto(page, "[data-testid=cash-cut-contado]", 2300);
    await typeInto(page, "[data-testid=cash-cut-retiros]", 0);
    await scrollIntoView(page, "[data-testid=cash-cut-derived]");
    const derived = await metrics(page, "[data-testid=cash-cut-derived]");
    check(2, "el derivado muestra la resta", /1,800\.00/.test(derived.text), JSON.stringify(derived.text));
    check(2, `el derivado se lee: font-size >= ${FONT_MIN}px`, derived.maxFont >= FONT_MIN,
      `font-size del monto=${derived.maxFont}px`);
    check(2, "el derivado cabe en el ancho del telefono",
      derived.x >= 0 && derived.x + derived.width <= VIEWPORT.width,
      `x=${derived.x} ancho=${derived.width}`);
    const scroll = await page.evaluate(() => ({
      doc: document.documentElement.scrollWidth, win: window.innerWidth,
    }));
    check(2, "la pantalla no pide scroll horizontal", scroll.doc <= scroll.win,
      `documento=${scroll.doc}px viewport=${scroll.win}px`);
    await shot(page, "caso2-derivado-numero-grande", `derivado a ${derived.maxFont}px`);

    // ===== Caso 5: el total del dia =======================================
    await scrollIntoView(page, "[data-testid=cash-cut-day-total]");
    const total = await metrics(page, "[data-testid=cash-cut-day-total]");
    check(5, "el total del dia no se corta",
      total.scrollWidth <= total.clientWidth + 1 && total.scrollHeight <= total.clientHeight + 1,
      `scroll=${total.scrollWidth}x${total.scrollHeight} client=${total.clientWidth}x${total.clientHeight} texto=${JSON.stringify(total.text)}`);
    // 550 de tarjeta + 1800 del turno guardado + 1800 sin guardar.
    check(5, "el total es tarjeta + turnos contados + el que se captura",
      /4,150\.00/.test(total.text), JSON.stringify(total.text));
    await shot(page, "caso5-total-del-dia", `total ${total.text}`);

    // Un numero largo es el que desborda, no el normal.
    await typeInto(page, "[data-testid=cash-cut-contado]", 99999);
    await scrollIntoView(page, "[data-testid=cash-cut-day-total]");
    const big = await metrics(page, "[data-testid=cash-cut-day-total]");
    const bigScroll = await page.evaluate(() => ({
      doc: document.documentElement.scrollWidth, win: window.innerWidth,
    }));
    check(5, "con seis cifras el total sigue cabiendo",
      big.scrollWidth <= big.clientWidth + 1 && big.x + big.width <= VIEWPORT.width &&
        bigScroll.doc <= bigScroll.win,
      `texto=${JSON.stringify(big.text)} documento=${bigScroll.doc}px`);
    await shot(page, "caso5b-total-del-dia-numero-largo", `total ${big.text}`);

    // ===== El texto de la pantalla, tal como se lee =======================
    // Mojibake: si el fuente guarda UTF-8 re-codificado, el navegador dibuja
    // "cajÃ³n" donde dice "cajon" con acento. No lo ve ninguna prueba del
    // modulo, y es lo primero que ve la cajera.
    const mojibake = await page.evaluate(() => {
      const out = [];
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const t = n.textContent;
        if (/[ÃÂâ]/.test(t) && t.trim()) out.push(t.trim().slice(0, 80));
      }
      return out;
    });
    check(6, "el texto de la pantalla no trae mojibake", mojibake.length === 0,
      mojibake.length ? `${mojibake.length} textos: ${JSON.stringify(mojibake.slice(0, 3))}` : "limpio");

    await page.evaluate(() => window.scrollTo(0, 0));
    await settle(400);
    await shot(page, "caso6-pantalla-completa", "la pantalla a 390px");
    await page.screenshot({ path: path.join(SHOTS, "caso6-pantalla-completa-scroll.png"), fullPage: true });
  } catch (err) {
    check(99, "la corrida termino sin excepciones", false, String(err).slice(0, 400));
  } finally {
    const failed = results.filter((r) => !r.ok);
    console.log("\n" + "=".repeat(70));
    console.log(`${results.length - failed.length} de ${results.length} comprobaciones PASS`);
    for (const f of failed) console.log(`  FALLA caso ${f.step}: ${f.name} -> ${f.detail}`);
    fs.writeFileSync(path.join(SHOTS, "resultados.json"),
      JSON.stringify({ viewport: VIEWPORT, results }, null, 2));
    await browser.close();
    process.exit(failed.length ? 1 : 0);
  }
})();
