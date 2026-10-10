"""Spec-650: la cantidad de actos sale de la estructura de la historia, nunca de un 5 fijo.

Recorre `src/` con `ast` y falla con:
- `range(1, 6)` (o `range(1, 5 + 1)`),
- un nombre `NUM_ACTS`,
- una comparación entre un número de acto (`number`, `numero`, `beat`, `acto`,
  `reveal_act`, `se_revela_en`…) y el literal 5.

Los topes técnicos (`Field(le=5)`, el `CHECK` de SQL) no son comparaciones y no se
miran. Lo que sí tiene que quedar fijo va en `PERMITIDOS` con su motivo.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_ACT_WORDS = ("number", "numero", "beat", "acto", "act", "reveal", "revela")

# (archivo, línea de código sin espacios) → motivo.
PERMITIDOS: dict[tuple[str, str], str] = {
    (
        "src/application/services/narrator_config_sanitizer.py",
        "foriinrange(1,6):",
    ): "YAML viejo del wizard: `actos` siempre trae los 5 de la estructura larga",
}


def _is_five(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == 5


def _is_six(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and node.value == 6:
        return True
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Add)
        and _is_five(node.left)
        and isinstance(node.right, ast.Constant)
        and node.right.value == 1
    )


def _mentions_act(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        name = (
            sub.id
            if isinstance(sub, ast.Name)
            else sub.attr
            if isinstance(sub, ast.Attribute)
            else ""
        )
        if any(w in name.lower() for w in _ACT_WORDS):
            return True
    return False


def _findings(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and len(node.args) >= 2
            and _is_six(node.args[1])
        ):
            out.append((node.lineno, "range(…, 6)"))
        elif isinstance(node, ast.Name) and node.id == "NUM_ACTS":
            out.append((node.lineno, "NUM_ACTS"))
        elif isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(_is_five(s) for s in sides) and any(
                _mentions_act(s) for s in sides if not _is_five(s)
            ):
                out.append((node.lineno, "comparación con 5"))
    return out


def test_no_hay_cinco_actos_fijos_en_src():
    found = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, what in _findings(path):
            code = "".join(lines[lineno - 1].split())
            if (rel, code) not in PERMITIDOS:
                found.append(f"{rel}:{lineno}: {what} → {lines[lineno - 1].strip()}")
    assert not found, (
        "Cantidad de actos fija: preguntale a la estructura de la historia "
        "(`PromptBuilder.estructura(story)` / `BeatSpecRepository().estructura(...)`).\n"
        + "\n".join(found)
    )


def test_el_guardian_detecta_los_casos():
    sample = ROOT / "tests" / "unit" / "_muestra_cinco_actos.py"
    sample.write_text(
        "NUM_ACTS = 5\n"
        "for n in range(1, 6): pass\n"
        "ok = act.number == 5\n"
        "ok2 = 1 <= number <= 5\n"
        "fine = len(words) == 5\n",
        encoding="utf-8",
    )
    try:
        kinds = [w for _, w in _findings(sample)]
    finally:
        sample.unlink()
    assert kinds.count("NUM_ACTS") == 1
    assert kinds.count("range(…, 6)") == 1
    assert kinds.count("comparación con 5") == 2  # `len(words) == 5` no es un acto


def test_no_hay_cinco_actos_fijos_en_los_prompts():
    """Los prompts reciben la cantidad de actos de la estructura (`{num_actos}`,
    `{total}`, `{ultimo}`); un «5 actos» o «ACTO N DE 5» escrito a mano le miente
    al relato corto (pasó en S2: lo encontró la lectura de los snapshots)."""
    import re

    pattern = re.compile(r"\b5 actos\b|\bde 5\b|\b1 a 5\b|\bacto 5\b|\bactos 2[–-]5\b", re.I)
    found = []
    for path in sorted((ROOT / "config" / "prompts_generation").rglob("*.md")):
        if path.name == "README.md":  # documentación de los huecos, no la lee el LLM
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                found.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not found, "\n".join(found)
