"""Spec-520 T0.1: scripts/prod_db.py (consultas a la DB de prod para el deploy)."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "prod_db.py"


def _db(path: Path, statuses: list[str]) -> Path:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE generation_job (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO generation_job VALUES (?, ?)", [(str(i), s) for i, s in enumerate(statuses)]
    )
    conn.commit()
    conn.close()
    return path


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    ("statuses", "exit_code", "count"),
    [
        ([], 0, "0"),
        (["done", "failed"], 0, "0"),
        (["done", "running"], 1, "1"),
        (["queued", "running", "done"], 1, "2"),
    ],
)
def test_active_jobs(tmp_path, statuses, exit_code, count):
    db = _db(tmp_path / "stories.db", statuses)

    result = _run("active-jobs", str(db))

    assert result.returncode == exit_code
    assert result.stdout.strip() == count


def test_active_jobs_sin_db(tmp_path):
    result = _run("active-jobs", str(tmp_path / "no-existe.db"))

    assert result.returncode == 2
    assert "no existe" in result.stderr
    assert not (tmp_path / "no-existe.db").exists()


def test_backup_integro_y_sin_tocar_el_origen(tmp_path):
    db = _db(tmp_path / "stories.db", ["done", "running"])
    before = db.read_bytes()

    result = _run("backup", str(db), str(tmp_path / "backup_hoy"), "1030-abc1234")

    dest = tmp_path / "backup_hoy" / "stories-pre-deploy-1030-abc1234.db"
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(dest)
    conn = sqlite3.connect(dest)
    assert conn.execute("SELECT count(*) FROM generation_job").fetchone() == (2,)
    conn.close()
    assert db.read_bytes() == before


def test_backup_no_pisa_uno_existente(tmp_path):
    db = _db(tmp_path / "stories.db", [])
    args = ("backup", str(db), str(tmp_path / "b"), "1030-abc")
    assert _run(*args).returncode == 0

    again = _run(*args)

    assert again.returncode != 0
    assert "ya existe" in again.stderr


def test_backup_sin_db(tmp_path):
    result = _run("backup", str(tmp_path / "x.db"), str(tmp_path / "b"), "s")
    assert result.returncode == 2


def test_uso_invalido():
    assert _run("otra-cosa").returncode == 64
