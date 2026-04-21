"""DebugMarkdownRenderer — genera el archivo de diagnóstico de prompts y respuestas."""

from datetime import datetime
from pathlib import Path

from src.application.services.debug_collector import LLMCallRecord


class DebugMarkdownRenderer:
    """Renderiza la lista de LLMCallRecord a un archivo Markdown de diagnóstico."""

    def render(
        self,
        records: list[LLMCallRecord],
        story_meta: dict,
        output_dir: Path,
        session_start: datetime,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = session_start.strftime("debug_prompts_responses_%Y%m%d%H%M.md")
        output_path = output_dir / filename

        total_elapsed = sum(r.elapsed_s for r in records)
        lines: list[str] = []

        lines += self._header(story_meta, session_start, total_elapsed)
        lines += self._story_params(story_meta)

        for i, record in enumerate(records, start=1):
            lines += self._call_section(i, record)

        lines += self._summary_table(records, total_elapsed)

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _header(self, meta: dict, start: datetime, total_elapsed: float) -> list[str]:
        return [
            "# Debug Session — NarrativeForge",
            f"**Generado:** {start.strftime('%Y-%m-%d %H:%M')}  ",
            f"**Perfil activo:** {meta.get('profile', '?')}  ",
            f"**Provider:** {meta.get('provider', '?')}  ",
            f"**Duración total:** {total_elapsed:.1f} s  ",
            f"**Story ID:** {meta.get('story_id', '?')}  ",
            "",
            "---",
            "",
        ]

    def _story_params(self, meta: dict) -> list[str]:
        lines = [
            "## Parámetros de la Historia",
            "",
            "| Campo | Valor |",
            "|---|---|",
            f"| Título | {meta.get('title', '')} |",
            f"| Protagonista | {meta.get('protagonista', '')} |",
            f"| Sinopsis | {meta.get('sinopsis', '')} |",
            f"| Atmósfera | {meta.get('atmosfera', '')} |",
            f"| Relator | {meta.get('relator', '')} |",
            "",
            "---",
            "",
        ]
        return lines

    def _call_section(self, idx: int, r: LLMCallRecord) -> list[str]:
        beat_label = f"Beat #{r.beat_number}" if r.beat_number is not None else "—"
        role_upper = r.role.upper()
        title = f"## Llamada {idx} — {role_upper} {beat_label}"

        lines = [
            title,
            "",
            "### Componente",
            f"`{r.source_component}`",
            "",
            "### Parámetros de Inferencia",
            "",
            "| Param | Valor |",
            "|---|---|",
            f"| model | `{r.model}` |",
            f"| temperature | {r.temperature} |",
            f"| num_ctx | {r.num_ctx if r.num_ctx is not None else '—'} |",
            f"| num_predict | {r.num_predict if r.num_predict is not None else '—'} |",
            "",
        ]

        if r.narrative_context:
            lines += [
                "### Narrative Context (pre-baked)",
                "```",
                r.narrative_context,
                "```",
                "",
            ]

        lines += self._prompt_block("System Prompt", r.system_prompt or "_(ninguno)_")
        lines += self._prompt_block("Prompt Enviado", r.user_prompt)
        lines += self._prompt_block("Respuesta Raw", r.raw_response)
        lines += self._prompt_block("Respuesta Normalizada", r.normalized_response)

        raw_chars = len(r.raw_response)
        norm_chars = len(r.normalized_response)
        diff_pct = ((raw_chars - norm_chars) / raw_chars * 100) if raw_chars else 0.0

        lines += [
            "### Resultado del Parser",
            f"**Estado:** {r.parser_result}  ",
            f"**Raw chars:** {raw_chars} | **Norm chars:** {norm_chars} | "
            f"**Diferencia:** {diff_pct:.1f}%",
            "",
            "### Timing",
            f"- Elapsed LLM: {r.elapsed_s:.2f} s",
            "",
            "---",
            "",
        ]
        return lines

    def _prompt_block(self, title: str, content: str) -> list[str]:
        return [
            f"### {title}",
            "```",
            content,
            "```",
            "",
        ]

    def _summary_table(self, records: list[LLMCallRecord], total_elapsed: float) -> list[str]:
        lines = [
            "## Resumen de Sesión",
            "",
            "| # | Rol | Componente | Beat | Modelo | Elapsed | Raw chars | Norm chars | Parser |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(records, start=1):
            beat = str(r.beat_number) if r.beat_number is not None else "—"
            lines.append(
                f"| {i} | {r.role} | {r.source_component} | {beat} "
                f"| {r.model} | {r.elapsed_s:.1f}s "
                f"| {len(r.raw_response)} | {len(r.normalized_response)} "
                f"| {r.parser_result} |"
            )
        lines.append(
            f"| **TOTAL** | | | | | **{total_elapsed:.1f}s** | | | |"
        )
        lines.append("")
        return lines
