"""Los nueve pasos del corte de caja contra el app levantada (BOS-150).

No corre con las pruebas unitarias (no empieza con `test_`) porque necesita el
backend corriendo y un mongod. Esta aqui porque hay cuatro cosas que una prueba
del modulo **no** puede demostrar, y las cuatro tocan dinero:

1. Los permisos por rol y por sucursal (`require_roles`, `_cash_cut_branch`):
   que un cajero no corrija, y que no lea ni escriba el efectivo de otra marca.
2. El 409 del turno ya capturado, y que el prefill ofrezca **corregir** en vez
   de capturar otro.
3. Que el prefill mire el turno. Si no lo mira, una sucursal de dos turnos
   captura la mañana y la tarde no entra nunca — con el dia rotulado como
   completo. Ese fue el defecto 1 de BOS-150.
4. Que el dia de operacion que elige el servidor sea el del negocio (UTC-6) y
   no el dia UTC.

### Correrlo

Levanta el backend apuntado a una base **desechable** y corre el probe contra
ella. La base la siembra el propio probe (sucursales, cuatro usuarios y una
venta con tarjeta) y la borra al terminar:

    # terminal 1
    MONGO_URL=mongodb://127.0.0.1:27017 DB_NAME=cash_cut_api_probe \\
      JWT_SECRET=... CORS_ORIGINS=http://localhost:3000 \\
      python -m uvicorn server:app --port 8099

    # terminal 2
    CASH_CUT_PROBE_BASE=http://127.0.0.1:8099 \\
      python backend/tests/probe_cash_cut_api.py

Se niega a correr si la base no es la del probe: sembrar usuarios y borrar
colecciones en `casa_dorelia` seria tirar dinero real.

Nota de entorno: `server.py` importa `emergentintegrations`, que es un paquete
privado y no esta en PyPI. Sin el no se puede ni importar el modulo; en el
sandbox se levanto con un stub local fuera del arbol del repo. Si algun dia se
quiere esto en CI, ese import es el que hay que quitar primero (ver BOS-69).
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bcrypt  # noqa: E402
import httpx  # noqa: E402
from pymongo import MongoClient  # noqa: E402

import branches_init  # noqa: E402
import business_day  # noqa: E402
import cash_cut  # noqa: E402

# La base que el probe siembra y borra. Tiene que ser la misma a la que apunta
# el backend (`DB_NAME`), y **nunca** la base real.
PROBE_DB = os.environ.get("CASH_CUT_PROBE_DB", "cash_cut_api_probe")
BASE = os.environ.get("CASH_CUT_PROBE_BASE", "http://127.0.0.1:8099").rstrip("/") + "/api"
PASSWORD = os.environ.get("CASH_CUT_PROBE_PASSWORD", "probe-local-no-produccion")

# Dominio normal a proposito: `EmailStr` rechaza `.test` y `.example` por ser
# dominios de uso especial, y el login contesta 422 en vez de 401.
USERS = [
    ("admin@probe-cash-cut.com", "Admin probe", "admin", None),
    ("gerente.sji@probe-cash-cut.com", "Gerente SJI", "gerente", "c-sji"),
    ("cajero.sji@probe-cash-cut.com", "Cajero SJI", "cajero", "c-sji"),
    ("cajero.tecno@probe-cash-cut.com", "Cajero Tecnoparque", "cajero", "c-tecno"),
]

BUSINESS_TZ = business_day.BUSINESS_TZ
results = []


def check(step, name, ok, detail):
    results.append((step, name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FALLA'}] {name}: {detail}")


def seed(db, today):
    if PROBE_DB in ("casa_dorelia", "casa_dorelia_prod"):
        raise SystemExit(f"ERROR: {PROBE_DB} es la base real. El probe siembra "
                         "usuarios y borra colecciones; usa una base desechable.")
    for name in ("cafeterias", "users", "sales", cash_cut.COLLECTION):
        db[name].delete_many({})
    branches_init.ensure_branches(db.cafeterias, branches_init.GROUP_BRANCHES, commit=True)

    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()
    for email, name, role, cafeteria_id in USERS:
        db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "name": name,
                             "role": role, "cafeteria_id": cafeteria_id, "tenant_id": None,
                             "password": hashed, "is_active": True, "created_at": now})
    # Venta con tarjeta del dia: sin ella no se puede ver que el total del dia
    # es tarjeta + efectivo, que es el numero que lee la sucursal.
    for total in (120.0, 340.5, 89.5):
        db.sales.insert_one({"id": str(uuid.uuid4()), "tenant_id": None,
                             "cafeteria_id": "c-sji", "brand": "casa-dorelia",
                             "business_date": today, "created_at": f"{today}T18:00:00+00:00",
                             "total": total, "profit": 0.0, "payment_method": "tarjeta",
                             "source": "clip_api"})


def login(email):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"ERROR: no se pudo entrar como {email}: HTTP {r.status_code} {r.text[:200]}\n"
                         f"Revisa que el backend este en {BASE} y apuntado a la base {PROBE_DB}.")
    return {"Authorization": f"Bearer {r.json()['token']}"}


def main() -> int:
    url = os.environ.get("MONGO_URL") or cash_cut.DEFAULT_MONGO_URL
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[PROBE_DB]

    today = business_day.today()
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    seed(db, today)

    admin = login(USERS[0][0])
    gerente = login(USERS[1][0])
    cajero = login(USERS[2][0])
    cajero_tecno = login(USERS[3][0])
    print(f"login real de los 4 roles OK. dia de operacion = {today}\n")

    # El indice unico tiene que existir tras el arranque del app, no solo en la
    # sonda de `probe_cash_cut_index`: es lo unico que corta dos capturas
    # simultaneas del mismo turno.
    unique = {n: v for n, v in db[cash_cut.COLLECTION].index_information().items()
              if v.get("unique")}
    check(0, "el app creo el indice unico al arrancar", bool(unique), str(list(unique)))

    print("\n=== 1. Captura feliz (cajero de SJI: 500 / 2300 / 0 -> 1,800.00) ===")
    pre = httpx.get(f"{BASE}/cash-cuts/prefill", params={"cafeteria_id": "c-sji"},
                    headers=cajero, timeout=30).json()
    check(1, "el prefill no propone lo contado ni los retiros",
          pre["prefill"]["efectivo_contado"] is None and pre["prefill"]["retiros"] is None,
          f"contado={pre['prefill']['efectivo_contado']} retiros={pre['prefill']['retiros']}")
    check(1, "la tarjeta del dia se ve antes de capturar",
          pre["tarjeta"] == {"gross": 550.0, "charges": 3}, str(pre["tarjeta"]))

    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "fondo_inicial": 500, "efectivo_contado": 2300, "retiros": 0})
    cut = r.json()
    check(1, "guarda y deriva 1800.00",
          r.status_code == 200 and cut.get("ventas_efectivo") == 1800.0,
          f"HTTP {r.status_code} ventas_efectivo={cut.get('ventas_efectivo')}")
    check(1, "la marca la pone la sucursal, no el formulario",
          cut.get("brand") == "casa-dorelia", f"brand={cut.get('brand')}")
    check(1, "el dia es el de operacion", cut.get("business_date") == today,
          f"business_date={cut.get('business_date')}")
    check(1, "sin con que comparar, diferencia None y con motivo escrito",
          cut.get("comparable") is False and cut.get("diferencia") is None
          and bool(cut.get("diferencia_motivo")), f"motivo={cut.get('diferencia_motivo')!r}")
    cut_id = cut.get("id")

    print("\n=== 2. El turno no se captura dos veces (pero el segundo turno si) ===")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "fondo_inicial": 500, "efectivo_contado": 2300, "retiros": 0})
    check(2, "repetir el mismo turno contesta 409 y dice corregir",
          r.status_code == 409 and "orrigelo" in r.json().get("detail", ""),
          f"HTTP {r.status_code}")
    pre_v = httpx.get(f"{BASE}/cash-cuts/prefill",
                      params={"cafeteria_id": "c-sji", "turno": "vespertino"},
                      headers=cajero, timeout=30).json()
    # El defecto 1 de BOS-150: sin mirar el turno, aqui venia `existing` y la
    # pantalla escondia el formulario con la tarde sin contar.
    check(2, "un turno sin capturar deja el formulario abierto",
          pre_v.get("existing") is None and pre_v.get("turnos_capturados") == ["completo"],
          f"existing={pre_v.get('existing')} capturados={pre_v.get('turnos_capturados')}")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "turno": "vespertino",
        "fondo_inicial": 500, "efectivo_contado": 900, "retiros": 0})
    check(2, "el segundo turno del mismo dia se guarda", r.status_code == 200,
          f"HTTP {r.status_code} efectivo={r.json().get('ventas_efectivo')}")
    after = httpx.get(f"{BASE}/cash-cuts/prefill",
                      params={"cafeteria_id": "c-sji", "turno": "vespertino"},
                      headers=cajero, timeout=30).json()
    check(2, "el efectivo del dia es la SUMA de los turnos, no el ultimo",
          after["dia"] == {"cortes": 2, "efectivo": 2200.0}, str(after["dia"]))
    check(2, "y el turno ya capturado si marca `existing`",
          (after.get("existing") or {}).get("turno") == "vespertino",
          f"existing.turno={(after.get('existing') or {}).get('turno')!r}")
    r = httpx.get(f"{BASE}/cash-cuts/prefill",
                  params={"cafeteria_id": "c-sji", "turno": "inventado"},
                  headers=cajero, timeout=30)
    check(2, "un turno inexistente se rechaza, no se trata como `completo`",
          r.status_code == 400, f"HTTP {r.status_code}")

    print("\n=== 3. Efectivo negativo (fondo 2000, contado 500) ===")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "turno": "nocturno",
        "fondo_inicial": 2000, "efectivo_contado": 500, "retiros": 0})
    detail = r.json().get("detail", "")
    check(3, "400 con el aviso nombrando los tres montos",
          r.status_code == 400 and all(t in detail for t in ("contado", "retiros", "fondo"))
          and "-1,500.00" in detail, f"HTTP {r.status_code} {detail[:120]}")

    print("\n=== 4. Dedazo de ceros (contado 250000) ===")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "turno": "nocturno",
        "fondo_inicial": 500, "efectivo_contado": 250000, "retiros": 0})
    detail = r.json().get("detail", "")
    check(4, "400 con el mensaje del tope de cordura",
          r.status_code == 400 and "tope de cordura" in detail, f"HTTP {r.status_code} {detail[:120]}")

    print("\n=== 5. Corte en cero ===")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero, timeout=30, json={
        "cafeteria_id": "c-sji", "business_date": yesterday, "fondo_inicial": 500,
        "efectivo_contado": 500, "retiros": 0, "tickets_efectivo": 0})
    zero = r.json()
    check(5, "un cero medido si se guarda",
          r.status_code == 200 and zero.get("ventas_efectivo") == 0.0,
          f"HTTP {r.status_code} ventas_efectivo={zero.get('ventas_efectivo')}")
    cov = httpx.get(f"{BASE}/cash-cuts", params={"cafeteria_id": "c-sji"},
                    headers=cajero, timeout=30).json()
    check(5, "y por eso ese dia deja de ser piso", yesterday in cov["days_covered"],
          f"days_covered={cov['days_covered']}")

    print("\n=== 6. Correccion (gerente) ===")
    r = httpx.put(f"{BASE}/cash-cuts/{cut_id}", headers=gerente, timeout=30,
                  json={"reason": "faltaba contar el sobre del deposito",
                        "efectivo_contado": 2500})
    rev = r.json()
    check(6, "el monto anterior, quien y por que quedan en `revisions`",
          r.status_code == 200
          and rev["revisions"][0]["before"]["efectivo_contado"] == 2300.0
          and rev["revisions"][0]["by_name"] == USERS[1][0]
          and rev["revisions"][0]["reason"],
          f"HTTP {r.status_code} before={rev.get('revisions', [{}])[0].get('before')}")
    check(6, "el derivado se recalcula y el corte conserva su nacimiento",
          rev.get("ventas_efectivo") == 2000.0 and rev.get("created_by_name") == USERS[2][0],
          f"ventas_efectivo={rev.get('ventas_efectivo')} capturo={rev.get('created_by_name')}")
    r = httpx.put(f"{BASE}/cash-cuts/{cut_id}", headers=gerente, timeout=30,
                  json={"reason": "   ", "efectivo_contado": 2600})
    check(6, "sin motivo no corrige: 400", r.status_code == 400,
          f"HTTP {r.status_code} {r.json().get('detail', '')[:90]}")

    print("\n=== 7. Permisos ===")
    r = httpx.put(f"{BASE}/cash-cuts/{cut_id}", headers=cajero, timeout=30,
                  json={"reason": "yo lo arreglo", "efectivo_contado": 9999})
    check(7, "un cajero no corrige: 403", r.status_code == 403, f"HTTP {r.status_code}")
    r = httpx.post(f"{BASE}/cash-cuts", headers=cajero_tecno, timeout=30, json={
        "cafeteria_id": "c-sji", "turno": "matutino",
        "fondo_inicial": 100, "efectivo_contado": 400, "retiros": 0})
    check(7, "un cajero no captura el corte de otra sucursal: 403",
          r.status_code == 403, f"HTTP {r.status_code}")
    r = httpx.get(f"{BASE}/cash-cuts/prefill", params={"cafeteria_id": "c-sji"},
                  headers=cajero_tecno, timeout=30)
    check(7, "ni abre su prefill: 403", r.status_code == 403, f"HTTP {r.status_code}")
    # El defecto 2 de BOS-150: este GET es el que trae los montos, y se acotaba
    # solo cuando el parametro venia vacio.
    r = httpx.get(f"{BASE}/cash-cuts", params={"cafeteria_id": "c-sji"},
                  headers=cajero_tecno, timeout=30)
    check(7, "ni lee su historial con el parametro puesto: 403",
          r.status_code == 403, f"HTTP {r.status_code}")
    r = httpx.get(f"{BASE}/cash-cuts", headers=cajero_tecno, timeout=30).json()
    check(7, "el historial sin filtro se acota a su sucursal",
          all(c["cafeteria_id"] == "c-tecno" for c in r["cuts"]),
          f"sucursales={sorted({c['cafeteria_id'] for c in r['cuts']})}")
    r = httpx.post(f"{BASE}/cash-cuts", headers=admin, timeout=30, json={
        "cafeteria_id": "c-tecno", "fondo_inicial": 300, "efectivo_contado": 1300, "retiros": 0})
    check(7, "el admin si captura cualquier sucursal, con su marca",
          r.status_code == 200 and r.json().get("brand") == "le-pain-dore",
          f"HTTP {r.status_code} brand={r.json().get('brand')}")

    print("\n=== 8. Dia de operacion (despues de las 18:00 CDMX) ===")
    now_utc = datetime.now(timezone.utc)
    print(f"  (ahora UTC={now_utc.isoformat(timespec='seconds')} / "
          f"CDMX={now_utc.astimezone(BUSINESS_TZ).isoformat(timespec='seconds')}; "
          f"dia UTC={now_utc.date()}, dia de operacion={today})")
    # El caso que rompe: un instante sellado en UTC que en CDMX sigue siendo el
    # dia anterior. Las 02:30Z son las 20:30 del dia que cerro.
    r = httpx.post(f"{BASE}/cash-cuts", headers=admin, timeout=30, json={
        "cafeteria_id": "c-sji", "business_date": "2026-10-02T02:30:00Z", "turno": "nocturno",
        "fondo_inicial": 500, "efectivo_contado": 1200, "retiros": 0})
    check(8, "un cierre de 20:30 CDMX queda en el dia que cerro, no en el dia UTC siguiente",
          r.status_code == 200 and r.json().get("business_date") == "2026-10-01",
          f"HTTP {r.status_code} business_date={r.json().get('business_date')}")
    r = httpx.post(f"{BASE}/cash-cuts", headers=admin, timeout=30, json={
        "cafeteria_id": "c-sji", "business_date": "2026-10-01T20:30:00", "turno": "vespertino",
        "fondo_inicial": 500, "efectivo_contado": 800, "retiros": 0})
    check(8, "una hora sin offset se lee como hora del negocio",
          r.status_code == 200 and r.json().get("business_date") == "2026-10-01",
          f"HTTP {r.status_code} business_date={r.json().get('business_date')}")
    r = httpx.post(f"{BASE}/cash-cuts", headers=admin, timeout=30, json={
        "cafeteria_id": "c-sji", "turno": "nocturno",
        "business_date": (now_utc.date() + timedelta(days=1)).isoformat(),
        "fondo_inicial": 500, "efectivo_contado": 800, "retiros": 0})
    check(8, "un dia futuro no se puede contar: 400",
          r.status_code == 400 and "futuro" in r.json().get("detail", ""),
          f"HTTP {r.status_code}")

    print("\n" + "=" * 70)
    failed = [r for r in results if not r[2]]
    print(f"{len(results) - len(failed)} de {len(results)} comprobaciones PASS")
    for step, name, _, detail in failed:
        print(f"  FALLA paso {step}: {name} -> {detail}")
    client.drop_database(PROBE_DB)
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
