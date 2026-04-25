"""Tests para ProgressReporter y SilentReporter."""

from pathlib import Path

from src.cli.progress import ProgressReporter, SilentReporter


class TestProgressReporter:
    def test_start_imprime_titulo(self, capsys):
        r = ProgressReporter()
        r.start("El Monte Prohibido")
        out = capsys.readouterr().out
        assert "NarrativeForge" in out
        assert "El Monte Prohibido" in out

    def test_config_summary_imprime_separador(self, capsys):
        r = ProgressReporter()
        r.config_summary("ollama-qwen25-14b")
        out = capsys.readouterr().out
        assert "─" in out
        assert "ollama-qwen25-14b" in out

    def test_step_done_formato(self, capsys):
        r = ProgressReporter()
        r.step_done("🔍  Prueba de paso", 12.5)
        out = capsys.readouterr().out
        assert "🔍  Prueba de paso" in out
        assert "✓" in out
        assert "12.5s" in out

    def test_plan_done_formato(self, capsys):
        r = ProgressReporter()
        r.plan_done(8, 3.1)
        out = capsys.readouterr().out
        assert "📋" in out
        assert "8 beats" in out
        assert "✓" in out
        assert "3.1s" in out

    def test_beat_done_formato(self, capsys):
        r = ProgressReporter()
        r.beat_done(2, 8, 9.4, 8.8)
        out = capsys.readouterr().out
        assert "✍️" in out
        assert "2/8" in out
        assert "✓" in out
        assert "9.4s" in out
        assert "LLM 8.8s" in out

    def test_export_done_formato(self, capsys):
        r = ProgressReporter()
        r.export_done(0.1)
        out = capsys.readouterr().out
        assert "📄" in out
        assert "✓" in out
        assert "0.1s" in out

    def test_done_formato(self, capsys):
        r = ProgressReporter()
        r.done(82.4, Path("output_stories/El_Monte_82.md"))
        out = capsys.readouterr().out
        assert "✅" in out
        assert "1:22" in out
        assert "📁" in out
        assert "El_Monte_82.md" in out

    def test_done_imprime_separador(self, capsys):
        r = ProgressReporter()
        r.done(1.0, Path("out.md"))
        out = capsys.readouterr().out
        assert "─" in out

    def test_error_formato(self, capsys):
        r = ProgressReporter()
        r.error("timeout al conectar con Ollama", 9.0)
        out = capsys.readouterr().out
        assert "❌" in out
        assert "timeout al conectar con Ollama" in out
        assert "9.0s" in out


class TestSilentReporter:
    def test_no_imprime_nada(self, capsys):
        r = SilentReporter()
        r.start("X")
        r.plan_done(8, 1.0)
        r.beat_done(1, 8, 2.0, 1.5)
        r.export_done(0.1)
        r.done(10.0, Path("out.md"))
        r.error("algo", 1.0)
        out, err = capsys.readouterr()
        assert out == ""
        assert err == ""
