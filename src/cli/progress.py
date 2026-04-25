"""Progress reporter para la salida de consola del CLI."""

from pathlib import Path

from src.application.services.checkpoint import PHASE_LABELS
from src.cli.spinner import Spinner


def _fmt_time(s: float) -> str:
    """Formatea segundos: <60s → '1.2s', >=60s → '1:23'."""
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s) // 60}:{int(s) % 60:02d}"


class ProgressReporter:
    """Imprime progreso limpio con emojis y tiempos a consola."""

    def __init__(self) -> None:
        self._spinner = Spinner()

    def start(self, title: str) -> None:
        print(f"\n🎬  NarrativeForge — {title}")

    def config_summary(self, profile: str) -> None:
        print(f"📐  Perfil: {profile}")
        print("─" * 50)

    def phase_start(self, checkpoint: str) -> None:
        label = PHASE_LABELS.get(checkpoint, checkpoint)
        print(label)

    def step_start(self, message: str) -> None:
        """Inicia el spinner con el mensaje de la fase en curso."""
        self._spinner.start(message)

    def step_stop(self, final_line: str | None = None) -> None:
        """Detiene el spinner, opcionalmente imprimiendo una línea final."""
        self._spinner.stop(final_line)

    def step_done(self, label: str, elapsed_s: float) -> None:
        """Detiene el spinner y reporta un sub-paso completado con su tiempo."""
        self._spinner.stop()
        print(f"{label:<41} ✓  {_fmt_time(elapsed_s)}")

    def plan_done(self, num_beats: int, elapsed_s: float) -> None:
        self._spinner.stop()
        print(f"📋  Planificando {num_beats} beats...           ✓  {_fmt_time(elapsed_s)}")

    def beat_done(self, n: int, total: int, elapsed_s: float, llm_elapsed_s: float) -> None:
        self._spinner.stop()
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
        self._spinner.stop()
        print(f"❌  {msg}  ({_fmt_time(elapsed_s)})")

    def checkpoint_pause(
        self,
        stop_after: str,
        story_id: str,
        total_llms: int,
        debug_path: str | None = None,
    ) -> None:
        """Informa que el pipeline fue detenido en un checkpoint."""
        self._spinner.stop()
        print(f"\n[PAUSA] Pipeline detenido en '{stop_after}' ({total_llms}/17 llamadas LLM).")
        print(f"[PAUSA] Story ID: {story_id}")
        if debug_path:
            print(f"[PAUSA] Debug: {debug_path}")


class SilentReporter:
    """Implementación no-op para tests y modo API."""

    def start(self, title: str) -> None:
        pass

    def config_summary(self, profile: str) -> None:
        pass

    def phase_start(self, checkpoint: str) -> None:
        pass

    def step_start(self, message: str) -> None:
        pass

    def step_stop(self, final_line: str | None = None) -> None:
        pass

    def step_done(self, label: str, elapsed_s: float) -> None:
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

    def checkpoint_pause(
        self,
        stop_after: str,
        story_id: str,
        total_llms: int,
        debug_path: str | None = None,
    ) -> None:
        pass
