"""Consultas a la DB de producción para el deploy (Spec-520).

Solo biblioteca estándar (corre con cualquier python3, sin el entorno del
proyecto) y la DB de origen se abre en modo solo lectura.

    python3 scripts/prod_db.py active-jobs data/prod/stories.db
        → imprime la cantidad de jobs queued/running.
          exit 0 = ninguno, 1 = hay alguno, 2 = la DB no existe.

    python3 scripts/prod_db.py backup data/prod/stories.db <dir> <sufijo>
        → copia consistente en <dir>/stories-pre-deploy-<sufijo>.db,
          verificada con integrity_check; imprime la ruta.
"""

import sqlite3
import sys
from pathlib import Path

ACTIVE_STATUSES = ("queued", "running")


def _open_ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def active_jobs(db: Path) -> int:
    conn = _open_ro(db)
    try:
        (count,) = conn.execute(
            "SELECT count(*) FROM generation_job WHERE status IN (?, ?)", ACTIVE_STATUSES
        ).fetchone()
    finally:
        conn.close()
    return count


def backup(db: Path, dest_dir: Path, suffix: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"stories-pre-deploy-{suffix}.db"
    if dest.exists():
        raise FileExistsError(f"ya existe {dest}")
    source = _open_ro(db)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
        (result,) = target.execute("PRAGMA integrity_check").fetchone()
    finally:
        target.close()
        source.close()
    if result != "ok":
        raise RuntimeError(f"el backup {dest} no pasó integrity_check: {result}")
    return dest


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "active-jobs":
        db = Path(argv[1])
        if not db.exists():
            print(f"no existe la DB {db}", file=sys.stderr)
            return 2
        count = active_jobs(db)
        print(count)
        return 1 if count else 0
    if len(argv) >= 4 and argv[0] == "backup":
        db = Path(argv[1])
        if not db.exists():
            print(f"no existe la DB {db}", file=sys.stderr)
            return 2
        try:
            print(backup(db, Path(argv[2]), argv[3]))
        except (FileExistsError, RuntimeError, sqlite3.Error) as exc:
            print(f"backup fallido: {exc}", file=sys.stderr)
            return 1
        return 0
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
