#!/usr/bin/env python3
"""Trinidad Computers - actualizador semanal de precios.

Modos: local (archivos en esta carpeta), --firebase (lee y escribe en Firestore; lo usa el robot semanal
de GitHub Actions) y --sembrar (sube por unica vez tus config/costos locales a Firestore).

Lee los listados publicos de tus proveedores, actualiza costos.json (PRIVADO) y genera
precios.json (PUBLICO: solo precios de venta, sin costos ni margen). Ver LEEME.txt.
Solo usa la biblioteca estandar de Python 3.8+.
"""
import argparse, html, json, os, re, sys, time, urllib.error, urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
CFG = json.loads((BASE / "config.publica.json").read_text(encoding="utf-8"))
if (BASE / "config.json").exists():  # privado, solo en tu PC (no se sube al repositorio): margen, armado, envio, cooler
    CFG.update(json.loads((BASE / "config.json").read_text(encoding="utf-8")))
COSTOS_PATH = BASE / "costos.json"

# ---------------------------------------------------------------------------
# Que producto del proveedor corresponde a cada pieza del catalogo del armador.
# inc: todas estas expresiones deben aparecer en el nombre | exc: ninguna debe aparecer
# k: cantidad de unidades por pieza (los kits de RAM dual channel son 2 modulos)
# Se toma el producto mas barato que cumpla. Para agregar o ajustar una pieza, edita aca.
# ---------------------------------------------------------------------------
TRAY = r"tray|sin cooler"
WIFI = r"wifi|wf6|\bac\b"
KIT = r"kit|\+|2x|sodim|laptop|notebook"
SSD_EXC = r"2230|externo|sata|adaptador|carry|portatil"
MATCH = {
    # --- procesadores (los que "incluyen cooler" excluyen las versiones TRAY)
    "cpu:r5-4500": dict(inc=[r"ryzen\s*5\s*4500(?![a-z0-9])"], exc=[TRAY]),
    "cpu:r5-5500": dict(inc=[r"ryzen\s*5\s*5500(?![a-z0-9])"], exc=[TRAY]),
    "cpu:r5-5600": dict(inc=[r"ryzen\s*5\s*5600(?![a-z0-9])"]),
    "cpu:r5-5600gt": dict(inc=[r"5600gt"], exc=[TRAY]),
    "cpu:r7-5700g": dict(inc=[r"5700g"], exc=[TRAY]),
    "cpu:r7-5700x": dict(inc=[r"5700x(?![a-z0-9])"]),
    "cpu:r7-5800xt": dict(inc=[r"5800xt"]),
    "cpu:r7-5800x3d": dict(inc=[r"5800x3d"]),
    "cpu:r5-7600": dict(inc=[r"ryzen\s*5\s*7600(?![a-z0-9])"], exc=[TRAY]),
    "cpu:r5-7600x": dict(inc=[r"7600x"]),
    "cpu:r7-7800x3d": dict(inc=[r"7800x3d"]),
    "cpu:r5-8400f": dict(inc=[r"8400f"], exc=[TRAY]),
    "cpu:r5-8500g": dict(inc=[r"8500g"], exc=[TRAY]),
    "cpu:r5-8600g": dict(inc=[r"8600g"], exc=[TRAY]),
    "cpu:r7-8700f": dict(inc=[r"8700f"], exc=[TRAY]),
    "cpu:r7-8700g": dict(inc=[r"8700g"], exc=[TRAY]),
    "cpu:r5-9600x": dict(inc=[r"9600x"]),
    "cpu:r7-9700x": dict(inc=[r"9700x(?![a-z0-9])"]),
    "cpu:r7-9800x3d": dict(inc=[r"9800x3d"]),
    "cpu:r9-9900x": dict(inc=[r"9900x(?![a-z0-9])"]),
    "cpu:r9-9950x": dict(inc=[r"9950x(?![a-z0-9])"]),
    "cpu:r9-9950x3d": dict(inc=[r"9950x3d"]),
    # --- placas madre
    "mb:a520m": dict(inc=[r"a520m"], exc=[WIFI]),
    "mb:b550m": dict(inc=[r"b550m"], exc=[WIFI]),
    "mb:a620m": dict(inc=[r"a620a?m"], exc=[WIFI]),
    "mb:b650m": dict(inc=[r"b650e?m"], exc=[WIFI]),
    "mb:b840m": dict(inc=[r"b840m"], exc=[WIFI]),
    "mb:b850m": dict(inc=[r"b850m"], exc=[WIFI]),
    "mb:b850": dict(inc=[r"b850(?!m|-m)", r"\batx\b"], exc=[r"micro|m-atx"]),
    # --- memoria RAM (kits dual channel = 2 modulos iguales)
    "ram:16d4": dict(inc=[r"\b8\s?gb", r"ddr4", r"3200"], exc=[KIT], k=2),
    "ram:32d4": dict(inc=[r"\b16\s?gb", r"ddr4", r"3200"], exc=[KIT], k=2),
    "ram:16d5": dict(inc=[r"\b8\s?gb", r"ddr5", r"5600"], exc=[KIT], k=2),
    "ram:32d5": dict(inc=[r"\b16\s?gb", r"ddr5", r"5600"], exc=[KIT], k=2),
    # --- placas de video
    "gpu:3050": dict(inc=[r"rtx\s*3050"]),
    "gpu:5050": dict(inc=[r"rtx\s*5050"]),
    "gpu:5060": dict(inc=[r"rtx\s*5060(?!\s*ti)"]),
    "gpu:5060ti": dict(inc=[r"5060\s*ti", r"\b8\s?gb"], exc=[r"16\s?gb"]),
    "gpu:5060ti16": dict(inc=[r"5060\s*ti", r"16\s?gb"]),
    "gpu:5070": dict(inc=[r"rtx\s*5070(?!\s*ti)"]),
    "gpu:5070ti": dict(inc=[r"5070\s*ti"]),
    # --- SSD NVMe Gen4
    "st:500": dict(inc=[r"nvme", r"\b(500|512)\s?gb", r"g4|gen\s?4"], exc=[SSD_EXC]),
    "st:1t": dict(inc=[r"nvme", r"\b1\s?tb", r"g4|gen\s?4"], exc=[SSD_EXC]),
    "st:2t": dict(inc=[r"nvme", r"\b2\s?tb", r"g4|gen\s?4"], exc=[SSD_EXC]),
    # --- gabinetes (sin kits que traigan fuente)
    "cs:mini": dict(inc=[r"micro-?\s?atx|m-atx", r"3 (coolers?|fan|ventilad)"], exc=[KIT, r"sin coolers?"]),
    "cs:atx": dict(inc=[r"\batx\b", r"3 (coolers?|fan|ventilad)"], exc=[KIT, r"micro|m-atx", r"sin coolers?"]),
    # --- fuentes (certificadas 80 Plus)
    "ps:500": dict(inc=[r"fuente", r"\b550\s?w", r"80\s?(plus|\+)"], exc=[r"generica|performance"]),
    "ps:600": dict(inc=[r"fuente", r"\b650\s?w", r"gold"]),
    "ps:750": dict(inc=[r"fuente", r"\b750\s?w", r"gold"]),
    "ps:850": dict(inc=[r"fuente", r"\b850\s?w", r"gold"]),
}

# ---------------------------------------------------------------------------
RE_EF = re.compile(r"\$\s*([\d\.]+(?:,\d{1,2})?)\s*con\s+Efectivo", re.I)
RE_PRECIO = re.compile(r"\$\s*([\d\.]+(?:,\d{1,2})?)")


def numero(s):
    return float(s.strip().replace(".", "").replace(",", "."))


def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (TrinidadPrecios; uso interno)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parsear_tiendanube(h):
    """Devuelve [(nombre, precio_contado, precio_lista, estimado)] de un listado Tiendanube."""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    anclas = []
    for m in re.finditer(r'<a\b[^>]*href="([^"]*/productos/[^"#?]+)[^"]*"[^>]*>', h):
        t = re.search(r'title="([^"]*)"', m.group(0))
        anclas.append((m.start(), m.group(1).rstrip("/"), html.unescape(t.group(1)) if t else ""))
    primero, nombres = {}, {}
    for pos, href, titulo in anclas:
        primero.setdefault(href, pos)
        if titulo and href not in nombres:
            nombres[href] = titulo
    orden = sorted(primero.items(), key=lambda x: x[1])
    out = []
    for i, (href, ini) in enumerate(orden):
        fin = orden[i + 1][1] if i + 1 < len(orden) else min(len(h), ini + 4000)
        texto = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h[ini:fin])))
        if re.search(r"sin stock|agotado", texto, re.I):
            continue
        nombre = nombres.get(href) or texto[:120]
        ef = RE_EF.search(texto)
        lista = RE_PRECIO.search(texto)
        if ef:
            out.append((nombre, numero(ef.group(1)), numero(lista.group(1)) if lista else None, False))
        elif lista:
            est = numero(lista.group(1)) * (1 - CFG.get("descuento_efectivo_estimado", 0.28))
            out.append((nombre, round(est, 2), numero(lista.group(1)), True))
    return out


def leer_fuente(f):
    productos = []
    for url in f["urls"]:
        vistos = set()
        for n in range(1, f.get("paginas_max", 6) + 1):
            u = url if n == 1 else url + f"page/{n}/"
            try:
                items = parsear_tiendanube(bajar(u))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break
                print(f"  ! {u}: HTTP {e.code}")
                break
            except Exception as e:
                print(f"  ! {u}: {e}")
                break
            nuevos = [it for it in items if it[0] not in vistos]
            if not nuevos:
                break
            vistos.update(it[0] for it in nuevos)
            productos += [(f["nombre"],) + it for it in nuevos]
            time.sleep(1.0)  # cortesia con el servidor
        print(f"  {f['nombre']}: {len(vistos)} productos en {url.rstrip('/').split('/')[-1]}")
    return productos


def mejor(productos, regla):
    inc = [re.compile(p, re.I) for p in regla["inc"]]
    exc = [re.compile(p, re.I) for p in regla.get("exc", [])]
    cand = [p for p in productos
            if all(r.search(p[1]) for r in inc) and not any(r.search(p[1]) for r in exc) and p[2] > 0]
    return min(cand, key=lambda p: p[2]) if cand else None


def generar_precios(costos, fecha):
    margen, mcat = CFG["margen"], CFG.get("margenCat", {})
    pv = lambda c, cat: int(round(c * (1 + mcat.get(cat, margen)) / 1000.0)) * 1000
    precios = {k: pv(c, k.split(":")[0]) for k, c in costos.items()}
    return {"fecha": fecha, "fuente": CFG.get("fuente_texto", ""), "armado": CFG["armado"], "envio": CFG["envio"],
            "cooler": pv(CFG["cooler_costo"], "cooler"), "precios": precios}


CLAVES_PRIVADAS = ("margen", "margenCat", "armado", "envio", "cooler_costo", "fuente_texto")


def fb_init():
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        sys.exit("Falta firebase-admin: ejecuta  pip install firebase-admin")
    if os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
        cred = credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"]))
    elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    else:
        sys.exit("Falta la clave de servicio: define FIREBASE_SERVICE_ACCOUNT o GOOGLE_APPLICATION_CREDENTIALS")
    firebase_admin.initialize_app(cred)
    return firestore.client()


def leer_doc(db, col, doc):
    s = db.collection(col).document(doc).get()
    return s.to_dict() if s.exists else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="muestra los cambios sin guardar")
    ap.add_argument("--sin-red", action="store_true", help="no consulta los proveedores; solo recalcula precios")
    ap.add_argument("--aceptar-todo", action="store_true", help="acepta variaciones mayores al limite")
    ap.add_argument("--firebase", action="store_true", help="lee y escribe en Firestore (modo robot semanal)")
    ap.add_argument("--sembrar", action="store_true", help="sube config.json y costos.json a Firestore (una sola vez)")
    a = ap.parse_args()
    hoy = date.today().strftime("%d/%m/%Y")
    local = json.loads(COSTOS_PATH.read_text(encoding="utf-8")) if COSTOS_PATH.exists() else {"items": {}}
    db = fb_init() if (a.firebase or a.sembrar) else None
    if a.sembrar:
        costos = dict(local["items"])
        db.collection("privado").document("config").set({k: CFG[k] for k in CLAVES_PRIVADAS if k in CFG})
        db.collection("privado").document("costos").set({"_fecha": hoy, "items": costos})
        db.collection("publico").document("precios").set(generar_precios(costos, hoy))
        print(f"Listo: se subieron config, {len(costos)} costos y los precios de venta a Firestore.")
        return
    costos = dict(local["items"])
    if a.firebase:
        if leer_doc(db, "privado", "config") is None or not (leer_doc(db, "privado", "costos") or {}).get("items"):
            sys.exit("Firestore todavia no tiene tu config y tus costos: corre primero  python actualizar_precios.py --sembrar")
        for k, v in (leer_doc(db, "privado", "config") or {}).items():
            if k in CLAVES_PRIVADAS:
                CFG[k] = v
        cd = leer_doc(db, "privado", "costos")
        if cd and cd.get("items"):
            costos = dict(cd["items"])
    lineas = [f"Reporte de precios {hoy}", ""]
    if not a.sin_red:
        productos = []
        for f in CFG["fuentes"]:
            productos += leer_fuente(f)
        if not productos:
            sys.exit("No se pudo leer ningun producto: revisa la conexion o si cambio la pagina del proveedor.")
        limite = CFG.get("variacion_maxima", 0.35)
        for clave, regla in MATCH.items():
            p = mejor(productos, regla)
            viejo = costos.get(clave)
            if not p:
                lineas.append(f"SIN ACTUALIZAR  {clave:16} no se encontro en los proveedores (queda {viejo})")
                continue
            nuevo = round(p[2] * regla.get("k", 1), 1)
            var = (nuevo - viejo) / viejo if viejo else 0
            marca = "~estimado " if p[4] else ""
            if viejo and abs(var) > limite and not a.aceptar_todo:
                lineas.append(f"RETENIDO        {clave:16} {viejo:>12,.0f} -> {nuevo:>12,.0f} ({var:+.0%}) {p[0]}: {p[1][:60]}")
                continue
            costos[clave] = nuevo
            flag = "CAMBIO " if viejo is None or abs(var) >= 0.01 else "igual  "
            lineas.append(f"{flag}{'!' if abs(var) >= 0.10 else ' '}        {clave:16} {viejo or 0:>12,.0f} -> {nuevo:>12,.0f} ({var:+.0%}) {marca}{p[1][:60]}")
    faltan = [k for k in ("margen", "armado", "envio", "cooler_costo") if k not in CFG]
    if faltan:
        sys.exit("Falta " + ", ".join(faltan) + ": cargalos en config.json (local) o en Firestore (privado/config).")
    salida = generar_precios(costos, hoy)
    print("\n".join(lineas))
    if a.dry:
        print("\n(--dry: no se guardo nada)")
        return
    if a.firebase:
        db.collection("privado").document("costos").set({"_fecha": hoy, "items": costos})
        db.collection("publico").document("precios").set(salida)
        db.collection("privado").document("reporte").set({"fecha": hoy, "lineas": lineas})
        print("\nListo. Costos, precios de venta y reporte publicados en Firestore.")
        return
    local.update({"_fecha": hoy, "items": costos})
    COSTOS_PATH.write_text(json.dumps(local, indent=1, ensure_ascii=False), encoding="utf-8")
    dest = (BASE / CFG["salida_precios"]).resolve()
    dest.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    (BASE / "reportes").mkdir(exist_ok=True)
    (BASE / "reportes" / f"reporte-{date.today().isoformat()}.txt").write_text("\n".join(lineas), encoding="utf-8")
    print(f"\nListo. Se genero {dest}  -> subi ese archivo al sitio.")


if __name__ == "__main__":
    main()
