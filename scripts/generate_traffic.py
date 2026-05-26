"""
Generador de trafico sintetico para la API de Huella de Carbono.
Manda requests a todos los endpoints con datos aleatorios para que
Prometheus tenga algo que recolectar y Grafana algo que mostrar.

Uso:
    python scripts/generate_traffic.py
    python scripts/generate_traffic.py --url http://localhost:3000 --requests 200
"""

import argparse
import random
import time
import json
import urllib.request
import urllib.error
from datetime import datetime

# ─────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────

DEFAULT_URL = "http://localhost:3000"
DEFAULT_REQUESTS = 100
DEFAULT_DELAY = 0.5  # segundos entre requests

VEHICULOS = ["auto", "moto", "bus", "avion", "bicicleta", "tren"]
DIETAS = ["vegana", "vegetariana", "omnivora", "carnivora"]
PAISES = ["colombia", "argentina", "chile", "mexico", "españa", "mundial"]

COLORES = {
    "verde": "\033[92m",
    "amarillo": "\033[93m",
    "rojo": "\033[91m",
    "azul": "\033[94m",
    "cyan": "\033[96m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def color(texto, c):
    return f"{COLORES[c]}{texto}{COLORES['reset']}"


def log(msg, tipo="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    iconos = {"ok": "✅", "error": "❌", "info": "ℹ️ ", "slow": "🐢"}
    print(f"[{ts}] {iconos.get(tipo, '·')} {msg}")


# ─────────────────────────────────────────────
# Funciones de request
# ─────────────────────────────────────────────

def get(base_url, path):
    url = f"{base_url}{path}"
    try:
        start = time.time()
        with urllib.request.urlopen(url, timeout=10) as resp:
            duration = time.time() - start
            data = json.loads(resp.read())
            return resp.status, duration, data
    except urllib.error.HTTPError as e:
        return e.code, 0, {}
    except Exception as e:
        return 0, 0, {"error": str(e)}


def post(base_url, path, body):
    url = f"{base_url}{path}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=15) as resp:
            duration = time.time() - start
            data = json.loads(resp.read())
            return resp.status, duration, data
    except urllib.error.HTTPError as e:
        return e.code, 0, {}
    except Exception as e:
        return 0, 0, {"error": str(e)}


# ─────────────────────────────────────────────
# Escenarios de tráfico
# ─────────────────────────────────────────────

def escenario_health_check(base_url):
    status, dur, _ = get(base_url, "/")
    tipo = "ok" if status == 200 else "error"
    log(f"GET /  → {status} ({dur:.3f}s)", tipo)


def escenario_factores(base_url):
    status, dur, _ = get(base_url, "/factores")
    tipo = "ok" if status == 200 else "error"
    log(f"GET /factores  → {status} ({dur:.3f}s)", tipo)


def escenario_transporte(base_url):
    vehiculo = random.choice(VEHICULOS)
    km = round(random.uniform(1, 500), 1)
    status, dur, data = post(base_url, "/calcular/transporte", {
        "km": km, "tipo_vehiculo": vehiculo
    })
    tipo = "ok" if status == 200 else "error"
    kg = data.get("kg_co2_emitidos", "?")
    log(f"POST /calcular/transporte [{vehiculo} {km}km] → {status} ({dur:.3f}s) — {kg} kg CO₂", tipo)


def escenario_energia(base_url):
    pais = random.choice(PAISES)
    kwh = round(random.uniform(50, 800), 1)
    status, dur, data = post(base_url, "/calcular/energia", {
        "kwh_mes": kwh, "pais": pais
    })
    tipo = "ok" if status == 200 else "error"
    kg = data.get("kg_co2_mes", "?")
    log(f"POST /calcular/energia [{pais} {kwh}kWh] → {status} ({dur:.3f}s) — {kg} kg CO₂/mes", tipo)


def escenario_dieta(base_url):
    dieta = random.choice(DIETAS)
    personas = random.randint(1, 5)
    status, dur, data = post(base_url, "/calcular/dieta", {
        "tipo_dieta": dieta, "personas": personas
    })
    tipo = "ok" if status == 200 else "error"
    kg = data.get("kg_co2_anio", "?")
    log(f"POST /calcular/dieta [{dieta} x{personas}] → {status} ({dur:.3f}s) — {kg} kg CO₂/año", tipo)


def escenario_clasificar(base_url):
    kg = round(random.uniform(100, 5000), 1)
    status, dur, data = get(base_url, f"/clasificar/{kg}")
    tipo = "ok" if status == 200 else "error"
    nivel = data.get("nivel", "?")
    log(f"GET /clasificar/{kg}  → {status} ({dur:.3f}s) — {nivel}", tipo)


def escenario_reporte(base_url):
    vehiculo = random.choice(VEHICULOS)
    dieta = random.choice(DIETAS)
    log(f"POST /reporte/anual [cálculo completo]  → enviando...", "info")
    status, dur, data = post(base_url, "/reporte/anual", {
        "km_transporte": round(random.uniform(5, 50), 1),
        "tipo_vehiculo": vehiculo,
        "kwh_mes": round(random.uniform(100, 600), 1),
        "tipo_dieta": dieta,
        "personas": random.randint(1, 4),
    })
    tipo = "slow" if dur > 2 else ("ok" if status == 200 else "error")
    total = data.get("total_kg_co2_anio", "?")
    clasificacion = data.get("clasificacion", "?")
    log(f"POST /reporte/anual → {status} ({dur:.2f}s) — {total} kg CO₂/año  {clasificacion}", tipo)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

ESCENARIOS = [
    (escenario_health_check, 10),   # peso relativo
    (escenario_factores, 8),
    (escenario_transporte, 25),
    (escenario_energia, 20),
    (escenario_dieta, 20),
    (escenario_clasificar, 12),
    (escenario_reporte, 5),         # menos frecuente (es lento)
]

# Expandir lista según peso
POOL = []
for fn, peso in ESCENARIOS:
    POOL.extend([fn] * peso)


def main():
    parser = argparse.ArgumentParser(description="Generador de tráfico sintético — CO₂ API")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL base de la API")
    parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS, help="Número de requests a enviar")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Segundos entre requests")
    args = parser.parse_args()

    print(color(f"\n{'='*55}", "cyan"))
    print(color("  🌱 Generador de Tráfico — API Huella de Carbono", "bold"))
    print(color(f"{'='*55}", "cyan"))
    print(f"  URL:      {args.url}")
    print(f"  Requests: {args.requests}")
    print(f"  Delay:    {args.delay}s entre requests")
    print(color(f"{'='*55}\n", "cyan"))

    # Verificar que la API este arriba antes de empezar
    log("Verificando conexion con la API...", "info")
    status, _, _ = get(args.url, "/")
    if status != 200:
        print(color(f"\n❌ No se pudo conectar a {args.url} (status: {status})", "rojo"))
        print("   Revisa que docker-compose este corriendo: docker-compose up -d")
        return

    log(color("API disponible. Arrancando trafico...", "verde"), "ok")
    print()

    for i in range(1, args.requests + 1):
        print(color(f"[{i}/{args.requests}] ", "azul"), end="")
        escenario = random.choice(POOL)
        escenario(args.url)
        time.sleep(args.delay + random.uniform(-0.1, 0.2))

    print(color(f"\n✅ {args.requests} requests enviados a {args.url}", "verde"))
    print(color("   Grafana: http://localhost:3001\n", "cyan"))


if __name__ == "__main__":
    main()
