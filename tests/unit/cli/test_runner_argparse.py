"""Tests de Costura CLI: argparse → commands.generate."""

import inspect
from unittest.mock import patch


class TestRunnerArgparse:
    def test_generate_pasa_input_file(self):
        with patch("src.cli.commands.generate") as mock_gen:
            mock_gen.return_value = None
            from src.cli.runner import main

            with patch(
                "sys.argv",
                ["narrative", "generate", "--input", "input_stories/la_ofrenda.yaml", "--mock"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args.kwargs
            assert call_kwargs.get("input_file") == "input_stories/la_ofrenda.yaml"
            assert call_kwargs.get("use_mock") is True

    def test_generate_pasa_use_mock(self):
        with patch("src.cli.commands.generate") as mock_gen:
            mock_gen.return_value = None
            from src.cli.runner import main

            with patch(
                "sys.argv",
                ["narrative", "generate", "--input", "input_stories/la_ofrenda.yaml", "--mock"],
            ):
                try:
                    main()
                except SystemExit:
                    pass

            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args.kwargs
            assert call_kwargs.get("use_mock") is True


class TestGenerateSignature:
    def test_generate_acepta_input_file(self):
        from src.cli.commands import generate

        sig = inspect.signature(generate)
        assert "input_file" in sig.parameters

    def test_generate_async_acepta_input_file(self):
        from src.cli.commands import _generate_async

        sig = inspect.signature(_generate_async)
        assert "input_file" in sig.parameters
