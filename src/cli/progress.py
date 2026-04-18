"""Progress reporter para la salida de consola del CLI."""

from pathlib import Path


class ProgressReporter:
    """Imprime progreso limpio con emojis y tiempos a consola."""

    def start(self, title: str) -> None:
        print(f"\n🎬  NarrativeForge — {title}")
        print("─" * 40)

    def plan_done(self, num_beats: int, elapsed_s: float) -> None:
        print(f"📋  Planificando {num_beats} beats...           ✓  {elapsed_s:.1f}s")

    def beat_done(self, n: int, total: int, elapsed_s: float, llm_elapsed_s: float) -> None:
        print(
            f"✍️   Beat {n}/{total}...                       ✓  {elapsed_s:.1f}s"
            f"  (LLM {llm_elapsed_s:.1f}s)"
        )

    def export_done(self, elapsed_s: float) -> None:
        print(f"📄  Exportando Markdown...            ✓  {elapsed_s:.1f}s")

    def done(self, total_elapsed_s: float, output_path: Path) -> None:
        print("─" * 40)
        print(f"✅  Completado en {total_elapsed_s:.1f}s")
        print(f"📁  {output_path}")

    def error(self, msg: str, elapsed_s: float) -> None:
        print(f"❌  {msg}  ({elapsed_s:.1f}s)")


class SilentReporter:
    """Implementación no-op para tests y modo API."""

    def start(self, title: str) -> None:
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
