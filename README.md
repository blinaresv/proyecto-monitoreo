# API Huella de Carbono — Monitoreo y Observabilidad

**Nombre:** Brandon Felipe Linares Viasus  
**Codigo:** 202312703601  
**Curso:** Herramientas y Visualización de Datos  
**Actividad:** Monitoreo y Observabilidad  
**Institución:** Fundación Universitaria Los Libertadores

---

## Qué hace esta API

Calcula la huella de carbono (emisiones de CO₂ equivalente) de tres actividades cotidianas: transporte, consumo eléctrico y tipo de dieta. Está instrumentada con métricas en formato Prometheus y visualizada en Grafana, todo corriendo sobre Docker Compose.

La idea es sencilla: das un par de datos (cuántos km recorres al día, cuánto consumes en kWh, qué comes), y la API te devuelve cuánto CO₂ estás emitiendo y en qué nivel estás (bajo, medio, alto o crítico).

---

## Estructura del proyecto

```
proyecto-monitoreo/
├── docker-compose.yml              ← orquesta los 3 servicios
├── README.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                      ← FastAPI + métricas Prometheus
├── prometheus/
│   ├── prometheus.yml              ← configuración de scraping
│   └── alerts.yml                  ← reglas de alerta
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml      ← fuente de datos automática
│       └── dashboards/
│           ├── dashboard.yml
│           └── api-dashboard.json  ← dashboard pre-configurado con 8 paneles
└── scripts/
    └── generate_traffic.py         ← tráfico sintético
```

---

## Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- Python 3.8+ (solo para el script de tráfico, usa solo stdlib)

---

## Inicio rápido

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd proyecto-monitoreo
```

### 2. Levantar los servicios

```bash
docker-compose up -d
```

### 3. Verificar que todo esté corriendo

```bash
docker-compose ps
```

Los 3 servicios deben aparecer en estado `Up`:

```
NAME           STATUS
co2-api        Up
prometheus     Up
grafana        Up
```

### 4. URLs de acceso

| Servicio   | URL                        | Credenciales     |
|------------|----------------------------|------------------|
| API REST   | http://localhost:3000      | —                |
| Prometheus | http://localhost:9090      | —                |
| Grafana    | http://localhost:3001      | admin / admin    |

### 5. Generar tráfico sintético

```bash
python scripts/generate_traffic.py

# Con opciones
python scripts/generate_traffic.py --requests 200 --delay 0.3
```

---

## Endpoints

| Método | Endpoint                  | Descripción                                | Latencia   |
|--------|---------------------------|--------------------------------------------|------------|
| GET    | `/`                       | Health check                               | ~5ms       |
| GET    | `/factores`               | Factores de emisión por categoría          | ~10ms      |
| POST   | `/calcular/transporte`    | CO₂ según km recorridos y tipo de vehículo | ~20ms      |
| POST   | `/calcular/energia`       | CO₂ según consumo eléctrico mensual (kWh)  | ~150ms     |
| POST   | `/calcular/dieta`         | CO₂ según tipo de dieta                    | ~250ms     |
| GET    | `/clasificar/{kg_co2}`    | Nivel de huella: bajo, medio, alto, crítico| ~5ms       |
| POST   | `/reporte/anual`          | Reporte completo de huella anual           | 2–3s       |
| GET    | `/metrics`                | Métricas en formato Prometheus             | —          |

### Ejemplos de uso

```bash
# Health check
curl http://localhost:3000/

# CO2 por transporte
curl -X POST http://localhost:3000/calcular/transporte \
  -H "Content-Type: application/json" \
  -d '{"km": 150, "tipo_vehiculo": "auto"}'

# CO2 por consumo eléctrico
curl -X POST http://localhost:3000/calcular/energia \
  -H "Content-Type: application/json" \
  -d '{"kwh_mes": 350, "pais": "colombia"}'

# CO2 por dieta
curl -X POST http://localhost:3000/calcular/dieta \
  -H "Content-Type: application/json" \
  -d '{"tipo_dieta": "omnivora", "personas": 3}'

# Clasificar una huella
curl http://localhost:3000/clasificar/1800

# Reporte anual completo
curl -X POST http://localhost:3000/reporte/anual \
  -H "Content-Type: application/json" \
  -d '{"km_transporte": 20, "tipo_vehiculo": "auto", "kwh_mes": 350, "tipo_dieta": "omnivora", "personas": 2}'

# Métricas Prometheus
curl http://localhost:3000/metrics
```

---

## Métricas implementadas

| Métrica | Tipo | Descripción |
|---|---|---|
| `http_requests_total` | Counter | Requests por método, endpoint y código de respuesta |
| `http_request_duration_seconds` | Histogram | Latencia con soporte para p50, p95, p99 |
| `http_requests_active` | Gauge | Requests en procesamiento ahora mismo |
| `system_cpu_usage_percent` | Gauge | CPU del servidor en porcentaje |
| `system_memory_usage_bytes` | Gauge | RAM usada en bytes |
| `co2_calculations_total` | Counter | Cálculos realizados por categoría |

---

## Queries PromQL útiles

```promql
# Requests por segundo, separados por endpoint
sum by (endpoint) (rate(http_requests_total[1m]))

# Latencia promedio por endpoint
rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])

# Percentil 95 de latencia
histogram_quantile(0.95, sum by (le, endpoint) (rate(http_request_duration_seconds_bucket[2m])))

# Percentil 99 de latencia
histogram_quantile(0.99, sum by (le, endpoint) (rate(http_request_duration_seconds_bucket[2m])))

# Porcentaje de errores HTTP
sum(rate(http_requests_total{status_code=~"4..|5.."}[2m])) / sum(rate(http_requests_total[2m]))

# Cálculos por categoría
co2_calculations_total

# Throughput total
sum(rate(http_requests_total[5m]))
```

---

## Dashboard de Grafana

El dashboard carga automáticamente cuando Grafana arranca. Tiene 8 paneles:

1. Requests por segundo — throughput en tiempo real por endpoint
2. Latencia promedio por endpoint
3. Percentiles p95 y p99
4. Tasa de errores 4xx/5xx
5. Requests activos en este momento
6. Conteo de cálculos de CO₂ por categoría
7. CPU del sistema
8. RAM usada

---

## Alertas configuradas

| Alerta | Se dispara cuando | Severidad |
|---|---|---|
| `AltaLatenciaAPI` | Latencia promedio > 1s durante 1 min | warning |
| `AltaTasaErrores` | Más del 5% de requests con error 5xx | critical |
| `SinTraficoAPI` | Sin requests por más de 3 minutos | info |
| `AltoCPU` | CPU > 80% durante 2 minutos | warning |

---

## Parar los servicios

```bash
# Solo parar
docker-compose down

# Parar y borrar los volúmenes (datos de Prometheus y Grafana)
docker-compose down -v
```

---

## Stack usado

- Python 3.11 + FastAPI
- prometheus-client para las métricas
- psutil para CPU y memoria
- Prometheus para recolección
- Grafana para visualización
- Docker + Docker Compose
