FROM python:3.11-slim

WORKDIR /app

# Instalar gcc para compilar psutil en ARM64 (Apple Silicon)
RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Instalar dependencias primero (aprovecha caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente y frontend
COPY app.py .
COPY frontend/ ./frontend/

# Exponer puerto
EXPOSE 3000

# Comando de inicio
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
