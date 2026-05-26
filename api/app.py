"""
API de Huella de Carbono
Curso: Herramientas y Visualización de Datos — Monitoreo y Observabilidad
"""

import time
import random
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    make_asgi_app,
    CONTENT_TYPE_LATEST,
    generate_latest,
)

# ─────────────────────────────────────────────
# Métricas Prometheus
# ─────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de requests HTTP recibidos",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latencia de los requests en segundos",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Requests activos en este momento",
)

CPU_USAGE = Gauge(
    "system_cpu_usage_percent",
    "Uso de CPU del sistema en porcentaje",
)

MEMORY_USAGE = Gauge(
    "system_memory_usage_bytes",
    "Uso de memoria RAM en bytes",
)

CO2_CALCULATIONS_TOTAL = Counter(
    "co2_calculations_total",
    "Total de cálculos de huella de carbono realizados",
    ["categoria"],
)

# ─────────────────────────────────────────────
# App FastAPI
# ─────────────────────────────────────────────

app = FastAPI(
    title="API Huella de Carbono",
    description="Calcula emisiones de CO₂ por transporte, energia y dieta",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")


# ─────────────────────────────────────────────
# Middleware de métricas
# ─────────────────────────────────────────────

RUTAS_IGNORAR = {
    "/favicon.ico",
    "/apple-touch-icon.png",
    "/apple-touch-icon-precomposed.png",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
}

def normalizar_path(path: str) -> str:
    """Agrupa rutas con parámetros dinámicos para no crear una serie por cada valor."""
    if path.startswith("/clasificar/"):
        return "/clasificar/{kg_co2}"
    return path


@app.middleware("http")
async def metrics_middleware(request, call_next):
    path = request.url.path

    # Ignorar rutas internas y del navegador
    if path in RUTAS_IGNORAR:
        response = await call_next(request)
        return response

    endpoint = normalizar_path(path)

    ACTIVE_REQUESTS.inc()
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
    ).inc()

    # Actualizar métricas del sistema
    CPU_USAGE.set(psutil.cpu_percent(interval=None))
    MEMORY_USAGE.set(psutil.virtual_memory().used)

    ACTIVE_REQUESTS.dec()
    return response


# ─────────────────────────────────────────────
# Modelos de entrada
# ─────────────────────────────────────────────

class TransporteInput(BaseModel):
    km: float
    tipo_vehiculo: str  # "auto", "moto", "bus", "avion", "bicicleta", "tren"

class EnergiaInput(BaseModel):
    kwh_mes: float
    pais: str = "colombia"  # Factor de emisión varía por país

class DietaInput(BaseModel):
    tipo_dieta: str  # "vegana", "vegetariana", "omnivora", "carnivora"
    personas: int = 1

class ReporteAnualInput(BaseModel):
    km_transporte: float
    tipo_vehiculo: str
    kwh_mes: float
    tipo_dieta: str
    personas: int = 1


# ─────────────────────────────────────────────
# Factores de emisión (kg CO₂ por unidad)
# ─────────────────────────────────────────────

FACTORES_TRANSPORTE = {
    "auto":       0.21,   # kg CO2 por km
    "moto":       0.11,
    "bus":        0.04,
    "avion":      0.255,
    "bicicleta":  0.0,
    "tren":       0.014,
}

FACTORES_ENERGIA = {
    "colombia":    0.126,   # kg CO2 por kWh (red eléctrica)
    "argentina":   0.310,
    "chile":       0.290,
    "mexico":      0.454,
    "españa":      0.181,
    "mundial":     0.475,
}

FACTORES_DIETA = {
    "vegana":        1.5,    # toneladas CO2 por persona/año
    "vegetariana":   1.7,
    "omnivora":      2.5,
    "carnivora":     3.3,
}

NIVELES_HUELLA = [
    (0,     500,   "🟢 Bajo",    "Tu huella es baja. ¡Excelente!"),
    (500,   1500,  "🟡 Medio",   "Huella moderada. Hay margen de mejora."),
    (1500,  3000,  "🟠 Alto",    "Huella alta. Considera cambios de hábitos."),
    (3000,  float("inf"), "🔴 Crítico", "Huella muy elevada. Acción urgente recomendada."),
]


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/", tags=["General"])
def health_check():
    """Estado de la API."""
    return {
        "status": "ok",
        "api": "API Huella de Carbono",
        "version": "1.0.0",
        "descripcion": "Calcula emisiones de CO2 por transporte, energia y dieta",
    }


@app.get("/factores", tags=["Referencia"])
def obtener_factores():
    """Lista de factores de emisión por categoria y tipo."""
    return {
        "transporte_kg_co2_por_km": FACTORES_TRANSPORTE,
        "energia_kg_co2_por_kwh": FACTORES_ENERGIA,
        "dieta_toneladas_co2_por_anio": FACTORES_DIETA,
        "fuente": "IPCC 2023 / UPME Colombia",
    }


@app.post("/calcular/transporte", tags=["Calculo"])
def calcular_transporte(data: TransporteInput):
    """CO2 emitido segun km recorridos y tipo de vehiculo."""
    tipo = data.tipo_vehiculo.lower()
    if tipo not in FACTORES_TRANSPORTE:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de vehículo no reconocido. Opciones: {list(FACTORES_TRANSPORTE.keys())}",
        )

    factor = FACTORES_TRANSPORTE[tipo]
    kg_co2 = round(data.km * factor, 3)

    CO2_CALCULATIONS_TOTAL.labels(categoria="transporte").inc()

    return {
        "categoria": "transporte",
        "vehiculo": tipo,
        "km": data.km,
        "factor_emision_kg_por_km": factor,
        "kg_co2_emitidos": kg_co2,
        "equivalente_arboles_para_compensar": round(kg_co2 / 21.77, 2),
    }


@app.post("/calcular/energia", tags=["Calculo"])
def calcular_energia(data: EnergiaInput):
    """CO2 emitido segun consumo electrico mensual en kWh."""
    # Simula consulta a tabla de factores
    time.sleep(random.uniform(0.1, 0.3))

    pais = data.pais.lower()
    factor = FACTORES_ENERGIA.get(pais, FACTORES_ENERGIA["mundial"])

    kg_co2_mes = round(data.kwh_mes * factor, 3)
    kg_co2_anio = round(kg_co2_mes * 12, 3)

    CO2_CALCULATIONS_TOTAL.labels(categoria="energia").inc()

    return {
        "categoria": "energia",
        "pais": pais,
        "kwh_mes": data.kwh_mes,
        "factor_emision_kg_por_kwh": factor,
        "kg_co2_mes": kg_co2_mes,
        "kg_co2_anio": kg_co2_anio,
        "equivalente_arboles_para_compensar": round(kg_co2_anio / 21.77, 2),
    }


@app.post("/calcular/dieta", tags=["Calculo"])
def calcular_dieta(data: DietaInput):
    """CO2 anual segun tipo de dieta y numero de personas."""
    time.sleep(random.uniform(0.15, 0.4))

    tipo = data.tipo_dieta.lower()
    if tipo not in FACTORES_DIETA:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de dieta no reconocido. Opciones: {list(FACTORES_DIETA.keys())}",
        )

    toneladas_co2 = round(FACTORES_DIETA[tipo] * data.personas, 3)
    kg_co2 = round(toneladas_co2 * 1000, 1)

    CO2_CALCULATIONS_TOTAL.labels(categoria="dieta").inc()

    return {
        "categoria": "dieta",
        "tipo_dieta": tipo,
        "personas": data.personas,
        "toneladas_co2_anio": toneladas_co2,
        "kg_co2_anio": kg_co2,
        "comparacion": {
            "vegana": round(FACTORES_DIETA["vegana"] * data.personas, 3),
            "vegetariana": round(FACTORES_DIETA["vegetariana"] * data.personas, 3),
            "omnivora": round(FACTORES_DIETA["omnivora"] * data.personas, 3),
            "carnivora": round(FACTORES_DIETA["carnivora"] * data.personas, 3),
        },
    }


@app.get("/clasificar/{kg_co2}", tags=["Utilidad"])
def clasificar_huella(kg_co2: float):
    """Devuelve el nivel de huella: bajo, medio, alto o critico."""
    for minimo, maximo, nivel, mensaje in NIVELES_HUELLA:
        if minimo <= kg_co2 < maximo:
            return {
                "kg_co2_anio": kg_co2,
                "nivel": nivel,
                "mensaje": mensaje,
                "toneladas_co2_anio": round(kg_co2 / 1000, 3),
            }


@app.post("/reporte/anual", tags=["Reporte"])
def generar_reporte_anual(data: ReporteAnualInput):
    """
    Reporte anual consolidado de huella de carbono.
    Tarda 2-3 segundos: simula un calculo mas pesado.
    """
    time.sleep(random.uniform(2.0, 3.0))  # Simula cálculo pesado

    # Transporte (anualizado)
    tipo = data.tipo_vehiculo.lower()
    factor_t = FACTORES_TRANSPORTE.get(tipo, 0.21)
    kg_transporte_anio = round(data.km_transporte * factor_t * 365, 2)

    # Energía (anualizada)
    pais = "colombia"
    factor_e = FACTORES_ENERGIA.get(pais, FACTORES_ENERGIA["mundial"])
    kg_energia_anio = round(data.kwh_mes * factor_e * 12, 2)

    # Dieta
    tipo_dieta = data.tipo_dieta.lower()
    factor_d = FACTORES_DIETA.get(tipo_dieta, 2.5)
    kg_dieta_anio = round(factor_d * data.personas * 1000, 2)

    total_kg = round(kg_transporte_anio + kg_energia_anio + kg_dieta_anio, 2)

    # Nivel
    nivel = "Desconocido"
    mensaje = ""
    for minimo, maximo, n, m in NIVELES_HUELLA:
        if minimo <= total_kg < maximo:
            nivel = n
            mensaje = m
            break

    CO2_CALCULATIONS_TOTAL.labels(categoria="reporte_anual").inc()

    return {
        "reporte": "Huella de Carbono Anual",
        "desglose_kg_co2": {
            "transporte": kg_transporte_anio,
            "energia": kg_energia_anio,
            "dieta": kg_dieta_anio,
        },
        "total_kg_co2_anio": total_kg,
        "total_toneladas_co2_anio": round(total_kg / 1000, 3),
        "clasificacion": nivel,
        "mensaje": mensaje,
        "arboles_para_compensar": round(total_kg / 21.77, 0),
        "recomendaciones": _generar_recomendaciones(
            kg_transporte_anio, kg_energia_anio, kg_dieta_anio
        ),
    }


def _generar_recomendaciones(kg_t, kg_e, kg_d):
    recs = []
    mayor = max(kg_t, kg_e, kg_d)
    if mayor == kg_t:
        recs.append("🚌 Tu mayor fuente de emisión es el transporte. Considera transporte público o bicicleta.")
    if mayor == kg_e:
        recs.append("⚡ Tu consumo energético es el más alto. Revisa electrodomésticos y considera energía solar.")
    if mayor == kg_d:
        recs.append("🥗 Tu dieta tiene alto impacto. Reducir el consumo de carne roja puede marcar la diferencia.")
    recs.append("🌱 Compensar con árboles es una opción mientras reduces tu huella.")
    return recs


# ─────────────────────────────────────────────
# Endpoint /metrics para Prometheus
# ─────────────────────────────────────────────

@app.get("/metrics", tags=["Monitoreo"], include_in_schema=False)
def metrics():
    """Metricas en formato Prometheus para scraping."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
