"""Tests de Costura: _generate_async con input_file."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestGenerateAsyncInput:
    @pytest.mark.asyncio
    async def test_generate_async_con_input_file(self, tmp_path):
        from src.cli.commands import _generate_async

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """title: Historia Test
protagonista: Protagonista de prueba
relator: tercera_persona
sinopsis: Sinopsis de prueba para test
genero: terror
"""
            )
            f.flush()
            yaml_path = f.name

        with patch("src.cli.commands._init_database", new_callable=AsyncMock) as mock_init:
            with patch("src.core.orchestrator.StoryRunner") as mock_runner_cls:
                mock_runner_instance = AsyncMock()
                mock_runner_instance.run_full = AsyncMock(
                    return_value=type(
                        "Story",
                        (),
                        {"id": "test-id", "title": "Historia Test"},
                    )()
                )
                mock_runner_cls.return_value = mock_runner_instance

                await _generate_async(
                    "",
                    "",
                    "",
                    [],
                    "",
                    "",
                    True,
                    tmp_path,
                    input_file=yaml_path,
                )

                mock_init.assert_called_once()
                mock_runner_instance.run_full.assert_called_once()

                call_kwargs = mock_runner_instance.run_full.call_args.kwargs
                assert call_kwargs["title"] == "Historia Test"
                assert call_kwargs["protagonista"] == "Protagonista de prueba"
                assert call_kwargs["sinopsis"] == "Sinopsis de prueba para test"
                assert call_kwargs["genero"] == "terror"

        Path(yaml_path).unlink()

    @pytest.mark.asyncio
    async def test_generate_async_sin_input_file(self, tmp_path):
        from src.cli.commands import _generate_async

        with patch("src.cli.commands._init_database", new_callable=AsyncMock):
            with patch("src.core.orchestrator.StoryRunner") as mock_runner_cls:
                mock_runner_instance = AsyncMock()
                mock_runner_instance.run_full = AsyncMock(
                    return_value=type(
                        "Story",
                        (),
                        {"id": "test-id", "title": "Historia Test"},
                    )()
                )
                mock_runner_cls.return_value = mock_runner_instance

                await _generate_async(
                    "Historia Manual",
                    "Protagonista",
                    "tercera_persona",
                    [],
                    "Sinopse",
                    "terror",
                    True,
                    tmp_path,
                    input_file=None,
                )

                mock_runner_instance.run_full.assert_called_once()
                call_kwargs = mock_runner_instance.run_full.call_args.kwargs
                assert call_kwargs["title"] == "Historia Manual"

    @pytest.mark.asyncio
    async def test_generate_async_input_invalido_no_invoca_runner(self, tmp_path):
        from src.cli.commands import _generate_async
        from src.cli.exceptions import ValidationError

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("title: SoloTitulo\n")
            f.flush()
            yaml_path = f.name

        with patch("src.cli.commands._init_database", new_callable=AsyncMock):
            with patch("src.core.orchestrator.StoryRunner") as mock_runner_cls:
                mock_runner_instance = AsyncMock()
                mock_runner_instance.run_full = AsyncMock()
                mock_runner_cls.return_value = mock_runner_instance

                with pytest.raises(ValidationError):
                    await _generate_async(
                        "",
                        "",
                        "",
                        [],
                        "",
                        "",
                        True,
                        tmp_path,
                        input_file=yaml_path,
                    )

                mock_runner_instance.run_full.assert_not_called()

        Path(yaml_path).unlink()
