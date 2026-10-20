/**
 * El selector de sucursal, medido en el DOM renderizado (BOS-154).
 *
 * `backend/tests/probe_cash_cut_api.py` (paso 10) demuestra que el API devuelve
 * **una sola** sucursal a `gerente`/`cajero`. Eso no demuestra lo que pide el
 * criterio de exito de BOS-154, que es sobre lo que la pantalla *ofrece*: que no
 * haya en ninguna pantalla un combo con la sucursal que el API va a negar.
 *
 * Son cuatro cosas que ni el bundle ni una prueba del backend pueden ver:
 *
 * 1. Que con una sola sucursal **no se dibuje combo**. Un `<Select>` de Radix
 *    sale al DOM con `role="combobox"`; el rotulo de solo lectura es un `div`.
 *    La diferencia solo existe renderizada.
 * 2. Que el nombre de la otra marca no aparezca en la pantalla. Es la medicion
 *    que no depende de que yo haya listado bien los `data-testid`: si quedara un
 *    septimo combo sin convertir, el nombre de la otra sucursal saldria igual.
 * 3. Que el `admin` **si** conserve el selector completo con las dos. Acotar de
 *    mas se ve igual que acotar bien si solo se mide al cajero: es el unico rol
 *    que lee las dos marcas juntas (ver `brands.py`).
 * 4. Que el boton "Corregir con motivo" no se le dibuje al cajero. Estaba tras
 *    `{canManage && ...}` — `canManage` es la **funcion**, asi que la guarda era
 *    siempre cierta. Mismo dedazo que el `disabled={!isAdmin}` del selector de
 *    sucursal del corte. Los dos ofrecian un 403.
 *
 * Lo que este probe **no** afirma: que la otra marca no se nombre en `/reports`.
 * Ahi sale en un renglon porque `GET /api/reports/sales-comparison` no recibe
 * `cafeteria_id` y recorre las dos sucursales (ver la nota en `SCREENS`). Es una
 * fuga de datos, no un camino muerto, y pide una decision de producto; queda
 * medida e impresa como nota, no tapada.
 *
 * ### Correrlo
 *
 * Igual que `probe_cash_cut_mobile.js`: mongod desechable, backend apuntado a
 * el, y el build de produccion servido en el origen que el backend acepta en
 * `CORS_ORIGINS`. Elige puertos propios.
 *
 *     # 1. backend (el stub de `emergentintegrations` va en PYTHONPATH)
 *     MONGO_URL=mongodb://127.0.0.1:27017 DB_NAME=bos154_probe \
 *       JWT_SECRET=... CORS_ORIGINS=http://localhost:3000 \
 *       python -m uvicorn server:app --port 8097
 *
 *     # 2. el fixture. No se corre `probe_cash_cut_api.py` entero: al terminar
 *     #    hace `drop_database` y se lleva lo que el navegador necesita vivo.
 *     #    Se le reusa `seed()`, y se captura un corte para que el caso 4 tenga
 *     #    un `existing` sobre el que mirar el boton de corregir:
 *     #
 *     #      import probe_cash_cut_api as probe, business_day, httpx
 *     #      probe.seed(db, business_day.today())
 *     #      httpx.post(f"{probe.BASE}/cash-cuts", headers=probe.login(
 *     #                     "cajero.tecno@probe-cash-cut.com"),
 *     #                 json={"cafeteria_id": "c-tecno", "fondo_inicial": 300,
 *     #                       "efectivo_contado": 1300, "retiros": 0})
 *
 *     # 3. el build servido con fallback de SPA, y este probe
 *     REACT_APP_BACKEND_URL=http://127.0.0.1:8097 yarn build
 *     BOS154_BASE=http://localhost:3000 BOS154_API=http://127.0.0.1:8097/api \
 *       node frontend/tests/probe_branch_selector.js
 *
 * Necesita `puppeteer-core` y un Chrome instalado (`BOS154_CHROME` lo apunta).
 * No se agrega a las dependencias del frontend a proposito: es herramienta de
 * verificacion, no algo que la app necesite para correr.
 *
 *     npm install puppeteer-core@23 --prefix <tmp>
 *     NODE_PATH=<tmp>/node_modules node frontend/tests/probe_branch_selector.js
 */
const puppeteer = require("puppeteer-core");

const CHROME = process.env.BOS154_CHROME || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = (process.env.BOS154_BASE || "http://localhost:3000").replace(/\/$/, "");
const API = (process.env.BOS154_API || "http://127.0.0.1:8097/api").replace(/\/$/, "");
const PASSWORD = process.env.BOS154_PASSWORD || "probe-local-no-produccion";

// Los cuatro roles que siembra `probe_cash_cut_api.py`. El cajero es el de
// Tecnoparque y el gerente el de SJI a proposito: asi la sucursal "ajena" de
// cada uno es la de la **otra marca**, que es el cruce que importa.
const ADMIN = "admin@probe-cash-cut.com";
const CAJERO = { email: "cajero.tecno@probe-cash-cut.com", own: "c-tecno" };
const GERENTE = { email: "gerente.sji@probe-cash-cut.com", own: "c-sji" };

// Las pantallas con filtro de sucursal en el encabezado, con el `data-testid`
// del combo y los roles que las tienen en el menu (ver `Layout.js`).
const SCREENS = [
  { path: "/dashboard", filter: "cafeteria-filter", ready: "dashboard-container", scoped: ["cajero", "gerente"] },
  { path: "/sales", filter: "sales-cafeteria-filter", ready: "sales-container", scoped: ["cajero", "gerente"] },
  { path: "/inventory", filter: "inventory-cafeteria-filter", ready: "inventory-container", scoped: ["cajero", "gerente"] },
  { path: "/ingredient-inventory", filter: "ingredient-inventory-cafeteria-filter", ready: "ingredient-inventory-container", scoped: ["cajero", "gerente"] },
  { path: "/purchases", filter: "purchases-cafeteria-filter", ready: "purchases-container", scoped: ["gerente"] },
  // `/reports` nombra la otra marca en un **renglon**, no en un combo: la ruta
  // `GET /api/reports/sales-comparison` (`server.py:4013`) no recibe
  // `cafeteria_id`, asi que BOS-152 no la toco, y recorre `db.cafeterias`
  // completo para `admin` y `gerente` por igual. Es una fuga de datos, distinta
  // del camino muerto que cierra BOS-154, y necesita una decision que no es del
  // patch: si un gerente debe comparar sucursales. Queda medida abajo (caso 2b)
  // en vez de tapada: lo que aqui se afirma es que la fuga sigue siendo solo de
  // renglon y no volvio a ser un combo.
  { path: "/reports", filter: "reports-cafeteria-filter", ready: "reports-container", scoped: ["gerente"], rowLeak: true },
];

const results = [];
function check(step, name, ok, detail) {
  results.push({ step, name, ok: Boolean(ok), detail });
  console.log(`  [${ok ? "PASS" : "FALLA"}] ${name}: ${detail}`);
}

const settle = (ms) => new Promise((r) => setTimeout(r, ms));

/** Entra con el login real del backend: `AuthContext` lee el token de localStorage. */
async function loginAs(page, email) {
  await page.goto(`${BASE}/admin`, { waitUntil: "networkidle2", timeout: 60000 });
  const auth = await page.evaluate(
    async (api, mail, password) => {
      localStorage.removeItem("token");
      const r = await fetch(`${api}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: mail, password }),
      });
      if (!r.ok) return { ok: false, status: r.status, body: (await r.text()).slice(0, 200) };
      const d = await r.json();
      localStorage.setItem("token", d.token);
      return { ok: true, role: d.user.role, cafeteria_id: d.user.cafeteria_id };
    },
    API, email, PASSWORD
  );
  if (!auth.ok) throw new Error(`login fallo para ${email}: HTTP ${auth.status} ${auth.body}`);
  return auth;
}

/**
 * Lo que la pantalla dice de la sucursal, leido del DOM.
 *
 * `role` separa las dos formas del mismo sitio: `combobox` es el `<Select>` de
 * Radix (hay que elegir), cualquier otra cosa es el rotulo de solo lectura.
 */
async function readBranchUi(page, testId, otherName) {
  return page.evaluate((id, other) => {
    const el = id ? document.querySelector(`[data-testid="${id}"]`) : null;
    const comboTexts = [...document.querySelectorAll('[role="combobox"]')]
      .map((c) => c.textContent.trim().replace(/\s+/g, " "));
    return {
      present: Boolean(el),
      role: el ? el.getAttribute("role") : null,
      text: el ? el.textContent.trim().replace(/\s+/g, " ") : null,
      // La medicion que no depende de los testids: si quedara un combo sin
      // convertir, el nombre de la otra sucursal saldria en el texto igual.
      mentionsOther: document.body.innerText.includes(other),
      comboTexts,
    };
  }, testId, otherName);
}

/** Abre un `<Select>` y devuelve el texto de sus opciones. */
async function openOptions(page, testId) {
  await page.click(`[data-testid="${testId}"]`);
  await page.waitForSelector("[role=option]", { timeout: 8000 });
  await settle(400);
  const options = await page.$$eval("[role=option]", (els) =>
    els.map((e) => e.textContent.trim().replace(/\s+/g, " "))
  );
  await page.keyboard.press("Escape");
  await settle(300);
  return options;
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: 1280, height: 900 },
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();

  try {
    // Los nombres salen del API, no escritos a mano: si el fixture cambia de
    // nombre, el probe sigue midiendo la sucursal correcta.
    const admin = await loginAs(page, ADMIN);
    check(0, "login real de admin", admin.role === "admin", `role=${admin.role}`);
    const branches = await page.evaluate(async (api) => {
      const r = await fetch(`${api}/cafeterias`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      return r.json();
    }, API);
    const nameOf = Object.fromEntries(branches.map((b) => [b.id, b.name]));
    check(0, "el admin recibe las dos sucursales del fixture", branches.length === 2,
      branches.map((b) => `${b.id}=${b.name}`).join(" | "));

    // ===== Casos 1 y 2: el rol con sucursal propia no ve la ajena ==========
    for (const who of [{ ...CAJERO, role: "cajero" }, { ...GERENTE, role: "gerente" }]) {
      const auth = await loginAs(page, who.email);
      check(1, `login real de ${who.role}`,
        auth.role === who.role && auth.cafeteria_id === who.own,
        `role=${auth.role} cafeteria=${auth.cafeteria_id}`);
      const other = Object.keys(nameOf).find((id) => id !== who.own);

      for (const screen of SCREENS) {
        if (!screen.scoped.includes(who.role)) continue;
        await page.goto(`${BASE}${screen.path}`, { waitUntil: "networkidle2", timeout: 60000 });
        await page.waitForSelector(`[data-testid="${screen.ready}"]`, { timeout: 30000 });
        await settle(900);
        const ui = await readBranchUi(page, screen.filter, nameOf[other]);
        check(1, `${who.role} en ${screen.path}: no hay combo de sucursal`, !ui.present,
          `combo=${ui.present} otros combos=${JSON.stringify(ui.comboTexts)}`);
        // El criterio de BOS-154, dicho exacto: ningun combo de la pantalla
        // ofrece la sucursal que el API va a negar. Vale en las seis, incluida
        // la que todavia la nombra en un renglon.
        const offeredInCombo = ui.comboTexts.some((t) => t.includes(nameOf[other]));
        check(2, `${who.role} en ${screen.path}: ningun combo ofrece ${nameOf[other]}`,
          !offeredInCombo, `combos=${JSON.stringify(ui.comboTexts)}`);
        if (screen.rowLeak) {
          // Medida, no afirmada: hoy sale `true` y es la fuga que falta decidir.
          // Si algun dia sale `false`, sobra la excepcion de `SCREENS`.
          console.log(`  [nota] ${who.role} en ${screen.path}: la otra marca se nombra en un renglon ` +
            `(= ${ui.mentionsOther}); es la fuga de \`reports/sales-comparison\`, no un combo`);
        } else {
          check(2, `${who.role} en ${screen.path}: no se nombra ${nameOf[other]}`,
            !ui.mentionsOther, `menciona la otra marca=${ui.mentionsOther}`);
        }
      }

      // El corte es el caso que origino todo: ahi el combo nunca se desactivaba
      // (`disabled={!isAdmin}` con `isAdmin` sin invocar).
      await page.goto(`${BASE}/corte-caja`, { waitUntil: "networkidle2", timeout: 60000 });
      await page.waitForSelector("[data-testid=cash-cut-container]", { timeout: 30000 });
      await settle(1200);
      const cut = await readBranchUi(page, "cash-cut-branch-select", nameOf[other]);
      check(1, `${who.role} en /corte-caja: la sucursal es rotulo, no combo`,
        cut.present && cut.role !== "combobox",
        `presente=${cut.present} role=${cut.role} texto=${JSON.stringify(cut.text)}`);
      check(1, `${who.role} en /corte-caja: el rotulo dice su sucursal`,
        cut.text === nameOf[who.own], `texto=${JSON.stringify(cut.text)}`);
      check(2, `${who.role} en /corte-caja: no se nombra ${nameOf[other]}`,
        !cut.mentionsOther, `menciona la otra marca=${cut.mentionsOther}`);

      // ===== Caso 4: el boton de corregir =================================
      const edit = await page.$("[data-testid=cash-cut-edit-button]");
      const existing = await page.$("[data-testid=cash-cut-existing]");
      if (who.role === "cajero") {
        check(4, "el cajero NO ve el boton de corregir (el PUT le da 403)",
          Boolean(existing) && !edit,
          `corte existente=${Boolean(existing)} boton=${Boolean(edit)}`);
      } else {
        check(4, "el gerente SI ve el boton de corregir",
          !existing || Boolean(edit),
          `corte existente=${Boolean(existing)} boton=${Boolean(edit)}`);
      }

      // ===== Caso 5: el combo de un formulario, no de un filtro ===========
      // El de "Nueva Venta" no estaba ni tras `isAdmin()`: ofrecia las dos a
      // cualquiera. Esconderlo obliga a fijar el valor, porque viaja en el POST.
      if (who.role === "cajero") {
        await page.goto(`${BASE}/sales`, { waitUntil: "networkidle2", timeout: 60000 });
        await page.waitForSelector("[data-testid=new-sale-button]", { timeout: 30000 });
        await page.click("[data-testid=new-sale-button]");
        await page.waitForSelector("[data-testid=sale-cafeteria-select]", { timeout: 15000 });
        await settle(600);
        const field = await readBranchUi(page, "sale-cafeteria-select", nameOf[other]);
        check(5, "en Nueva Venta la sucursal es rotulo, no combo",
          field.present && field.role !== "combobox",
          `role=${field.role} texto=${JSON.stringify(field.text)}`);
        check(5, "y el rotulo dice su sucursal (es la que viaja en el POST)",
          field.text === nameOf[who.own], `texto=${JSON.stringify(field.text)}`);
      }
    }

    // ===== Caso 3: el admin conserva el selector completo ==================
    await loginAs(page, ADMIN);
    for (const screen of SCREENS) {
      await page.goto(`${BASE}${screen.path}`, { waitUntil: "networkidle2", timeout: 60000 });
      await page.waitForSelector(`[data-testid="${screen.ready}"]`, { timeout: 30000 });
      await settle(900);
      const ui = await readBranchUi(page, screen.filter, "");
      check(3, `admin en ${screen.path}: el combo de sucursal sigue ahi`,
        ui.present && ui.role === "combobox", `presente=${ui.present} role=${ui.role}`);
      if (!ui.present) continue;
      const options = await openOptions(page, screen.filter);
      // "todas" + las dos sucursales. Si acotar de mas rompiera al admin, aqui
      // saldria una sola opcion y el reporte por marca se quedaria sin fuente.
      const hasBoth = Object.values(nameOf).every((n) => options.some((o) => o.includes(n)));
      check(3, `admin en ${screen.path}: ofrece las dos marcas y "todas"`,
        options.length === 3 && hasBoth, JSON.stringify(options));
    }

    await page.goto(`${BASE}/corte-caja`, { waitUntil: "networkidle2", timeout: 60000 });
    await page.waitForSelector("[data-testid=cash-cut-container]", { timeout: 30000 });
    await settle(1200);
    const adminCut = await readBranchUi(page, "cash-cut-branch-select", "");
    check(3, "admin en /corte-caja: si puede elegir sucursal",
      adminCut.present && adminCut.role === "combobox",
      `role=${adminCut.role} texto=${JSON.stringify(adminCut.text)}`);
    if (adminCut.role === "combobox") {
      const options = await openOptions(page, "cash-cut-branch-select");
      check(3, "y el combo del corte trae las dos sucursales (sin 'todas')",
        options.length === 2, JSON.stringify(options));
    }
  } catch (err) {
    check(99, "la corrida termino sin excepciones", false, String(err).slice(0, 400));
  } finally {
    const failed = results.filter((r) => !r.ok);
    console.log("\n" + "=".repeat(70));
    console.log(`${results.length - failed.length} de ${results.length} comprobaciones PASS`);
    for (const f of failed) console.log(`  FALLA caso ${f.step}: ${f.name} -> ${f.detail}`);
    await browser.close();
    process.exit(failed.length ? 1 : 0);
  }
})();
