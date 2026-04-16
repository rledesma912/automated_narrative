#!/bin/bash
# Script para ejecutar CLI de NarrativeForge
# Uso: ./scripts/bash/run_generate.sh --title "Título" --protagonist "Protagonista" ...

set -e

cd "$(dirname "$0")/../.."

# Defaults
TITLE=""
PROTAGONIST=""
RELATOR="tercera_persona"
ESCENARIOS=""
SINOPSIS=""
ATMOSFERA=""
BEATS=10
REAL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --title)
            TITLE="$2"
            shift 2
            ;;
        --protagonist)
            PROTAGONIST="$2"
            shift 2
            ;;
        --relator)
            RELATOR="$2"
            shift 2
            ;;
        --escenarios)
            ESCENARIOS="$2"
            shift 2
            ;;
        --sinopsis)
            SINOPSIS="$2"
            shift 2
            ;;
        --atmosfera)
            ATMOSFERA="$2"
            shift 2
            ;;
        --beats)
            BEATS="$2"
            shift 2
            ;;
        --real)
            REAL=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required args
if [[ -z "$TITLE" ]] || [[ -z "$PROTAGONIST" ]] || [[ -z "$ESCENARIOS" ]] || [[ -z "$SINOPSIS" ]] || [[ -z "$ATMOSFERA" ]]; then
    echo "Error: Faltan argumentos requeridos"
    echo "Uso: $0 --title \"Título\" --protagonist \"Protagonista\" --escenarios \"Escenario\" --sinopsis \"Sinopsis\" --atmosfera \"terror\""
    exit 1
fi

# Build command
CMD="PYTHONPATH=. uv run python -m src generate --title \"$TITLE\" --protagonist \"$PROTAGONIST\" --relator \"$RELATOR\" --escenarios \"$ESCENARIOS\" --sinopsis \"$SINOPSIS\" --atmosfera \"$ATMOSFERA\" --beats $BEATS"

if [[ "$REAL" == "true" ]]; then
    CMD="$CMD --real"
fi

echo "Ejecutando: $CMD"
echo "---"

eval "$CMD"

echo "---"
echo "Completado!"