#!/bin/bash
# Listar todas las historias

echo "📚 Historias existentes:"

curl -s "http://localhost:8010/api/v1/stories" | jq '.[] | "\(.id) - \(.title) (\(.status))"'