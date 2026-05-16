#!/bin/bash
# Script para levantar el entorno de desarrollo local (Spec-325)

echo "🚀 Levantando entorno de DESARROLLO (NarrativeForge)..."

# Cargar variables de entorno de forma segura
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✅ Variables cargadas de .env"
else
    echo "❌ Error: .env no encontrado"
    exit 1
fi

# Puertos configurados (sobrescriben lo del .env si es necesario para el script)
BACKEND_PORT=8020
FRONTEND_PORT=3010

echo "---"
echo "Backend: http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "---"

# Función para limpiar procesos al salir
cleanup() {
    echo "🛑 Deteniendo servicios..."
    # Matar a todos los hijos de este script
    pkill -P $$
    exit
}

trap cleanup SIGINT SIGTERM

# 1. Levantar Backend (Python) usando uv para el venv
echo "Starting Backend..."
uv run uvicorn src.main:app --host 127.0.0.1 --port $BACKEND_PORT --reload &

# 2. Levantar Frontend (Node)
echo "Starting Frontend..."
cd frontend
CORE_API_URL=http://localhost:$BACKEND_PORT PORT=$FRONTEND_PORT npm run dev &

# Esperar a los procesos
wait
