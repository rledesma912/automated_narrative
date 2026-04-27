"""Adaptador para Gemini CLI via Subprocess."""

import asyncio
import logging

from src.config import settings
from src.domain.interfaces import LLMResponse

logger = logging.getLogger("gemini_cli")


class GeminiCLIAdapter:
    """Adaptador que interactúa con el binario 'gemini' del sistema."""

    def __init__(self, cli_command: str | None = None, model_name: str | None = None):
        self.cli_command = cli_command or settings.gemini_cli_command
        self.model_name = model_name or settings.gemini_model_name

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        role: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Genera texto ejecutando el comando CLI de Gemini.
        """
        # Si el modelo pasado es de Ollama (contiene ":") o es None, usamos el de Gemini
        # Gemini CLI solo acepta modelos de Google, no de Ollama
        if model and ":" not in model:
            model_to_use = model
        else:
            model_to_use = self.model_name

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        cmd = [self.cli_command, "--model", model_to_use]

        logger.info(f"[GEMINI-CLI] Ejecutando comando: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Enviamos el prompt y esperamos la respuesta
            stdout, stderr = await process.communicate(input=full_prompt.encode("utf-8"))

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8").strip()
                logger.error(
                    f"[GEMINI-CLI] Error de ejecución (code {process.returncode}): {error_msg}"
                )
                raise Exception(f"Error de Gemini CLI: {error_msg}")

            response_text = stdout.decode("utf-8").strip()

            if not response_text:
                logger.warning("[GEMINI-CLI] La respuesta obtenida está vacía.")

            # Importante: Retornamos el valor calculado envuelto en LLMResponse
            return LLMResponse(text=response_text)

        except FileNotFoundError:
            logger.error(
                f"[GEMINI-CLI] El comando '{self.cli_command}' no fue encontrado en el PATH."
            )
            raise Exception(f"Comando no encontrado: {self.cli_command}")
        except Exception as e:
            logger.error(f"[GEMINI-CLI] Error inesperado: {str(e)}")
            raise

    async def close(self) -> None:
        """Cerrar recursos (no-op para llamadas CLI via subprocess)."""
        pass
