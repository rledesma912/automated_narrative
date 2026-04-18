"""Progress reporter para la salida de consola del CLI."""

from pathlib import Path


def _fmt_time(s: float) -> str:
    """Formatea segundos: <60s → '1.2s', >=60s → '1:23'."""
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s) // 60}:{int(s) % 60:02d}"


class ProgressReporter:
    """Imprime progreso limpio con emojis y tiempos a consola."""

    def start(self, title: str) -> None:
        print(f"\n🎬  NarrativeForge — {title}")

    def config_summary(
        self,
        model: str,
        director_t: float,
        voz_t: float,
        journal_t: float,
    ) -> None:
        print(
            f"📐  Modelo: {model}"
            f"  |  Director: {director_t}"
            f"  |  Voz: {voz_t}"
            f"  |  Journal: {journal_t}"
        )
        print("─" * 50)

    def plan_done(self, num_beats: int, elapsed_s: float) -> None:
        print(f"📋  Planificando {num_beats} beats...           ✓  {_fmt_time(elapsed_s)}")

    def beat_done(self, n: int, total: int, elapsed_s: float, llm_elapsed_s: float) -> None:
        print(
            f"✍️   Beat {n}/{total}...                       ✓  {_fmt_time(elapsed_s)}"
            f"  (LLM {_fmt_time(llm_elapsed_s)})"
        )

    def export_done(self, elapsed_s: float) -> None:
        print(f"📄  Exportando Markdown...            ✓  {_fmt_time(elapsed_s)}")

    def done(self, total_elapsed_s: float, output_path: Path) -> None:
        print("─" * 50)
        print(f"✅  Completado en {_fmt_time(total_elapsed_s)}")
        print(f"📁  {output_path}")

    def error(self, msg: str, elapsed_s: float) -> None:
        print(f"❌  {msg}  ({_fmt_time(elapsed_s)})")


class SilentReporter:
    """Implementación no-op para tests y modo API."""

    def start(self, title: str) -> None:
        pass

    def config_summary(self, model: str, director_t: float, voz_t: float, journal_t: float) -> None:
        pass

    def plan_done(self, num_beats: int, elapsed_s: float) -> None:
        pass

    def beat_done(self, n: int, total: int, elapsed_s: float, llm_elapsed_s: float) -> None:
        pass

    def export_done(self, elapsed_s: float) -> None:
        pass

    def done(self, total_elapsed_s: float, output_path: Path) -> None:
        pass

    def error(self, msg: str, elapsed_s: float) -> None:
        pass
