# SPEC-015: Comando de Limpieza de Base de Datos (db-clean)

**Estado:** Implementado  
**Fecha:** 17 de abril de 2026  
**Autor:** Gemini CLI

## 1. Contexto
Durante el ciclo de vida del desarrollo y pruebas de NarrativeForge, se generan múltiples registros en las tablas de `story`, `beat` y `narrative_journal`. Para facilitar el reinicio de pruebas sin necesidad de manipular archivos de base de datos directamente o borrar el archivo `.db`, se requiere un comando estandarizado para vaciar las tablas principales.

## 2. Requerimientos Funcionales
- **RF1:** El comando debe vaciar las tablas `narrative_journal`, `beat` y `story`.
- **RF2:** Debe respetar la integridad referencial, eliminando los registros en el orden correcto (cascada manual).
- **RF3:** Debe solicitar confirmación del usuario para evitar borrados accidentales en producción/entornos importantes.
- **RF4:** Debe reiniciar los contadores de `AUTOINCREMENT` de las tablas correspondientes.

## 3. Implementación Técnica

### 3.1 Script de Soporte (`scripts/bash/db_clean.sh`)
Se implementó un script en Bash que utiliza Python para interactuar con la base de datos, debido a la ausencia de la herramienta CLI `sqlite3` en el entorno de ejecución estándar.

**Lógica de Python integrada:**
```python
import sqlite3
conn = sqlite3.connect('stories.db')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys = ON;')
tables = ['narrative_journal', 'beat', 'story']
for table in tables:
    cursor.execute(f'DELETE FROM {table};')
cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('beat', 'narrative_journal');")
conn.commit()
cursor.execute('VACUUM;')
conn.close()
```

### 3.2 Integración en Makefile
Se añadió el target `db-clean` al `Makefile` principal:
```makefile
db-clean:
	@chmod +x scripts/bash/db_clean.sh && ./scripts/bash/db_clean.sh
```

## 4. Validación
- **Prueba de confirmación:** El script aborta si se responde 'n' o cualquier tecla distinta de 'y/Y'.
- **Prueba de integridad:** Verificado que los registros se eliminan en el orden: Journal -> Beats -> Story.
- **Prueba de autoincremento:** Los IDs de nuevos beats comienzan desde 1 tras la limpieza.
- **Prueba de Vacuum:** El comando libera espacio en disco tras el borrado masivo.

## 5. Documentación
- Actualizada la ayuda de `make help`.
- Actualizada la sección de comandos de mantenimiento en `README.md`.
