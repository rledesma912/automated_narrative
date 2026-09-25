"""Configuration using pydantic-settings."""

import logging
import os
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_LLM_CORE_FILE = "config/llm_core_definitions.yaml"
_DEFAULT_PROFILE = "ollama-natsumura"


def _load_llm_core() -> dict:
    """Carga llm_core_definitions.yaml. Retorna dict vacío si no existe."""
    path = Path(_LLM_CORE_FILE)
    if not path.exists():
        logger.warning(f"[CONFIG] {_LLM_CORE_FILE} no encontrado — usando defaults hardcodeados")
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Roles del pipeline que llaman al LLM (cada uno puede tener su proveedor, Spec-480).
LLM_ROLES = (
    "story_analyst",
    "director",
    "voz",
    "journal",
    # Spec-530: asistente de autoría.
    "consultor",
    "planificador",
    "verificador",
)
# Los roles del asistente que un perfil no declara heredan la config del director.
_ROLE_FALLBACK = {"consultor": "director", "planificador": "director", "verificador": "director"}

# Spec-510: duración estimada de un job (segundos) cuando el perfil no la declara
# (`profiles.<perfil>.estimated_seconds`) y no hay historial.
DEFAULT_ESTIMATED_SECONDS = {"full_generation": 240, "regenerate_voz": 60}


def _resolve_active_profile(core: dict, env_override: str | None) -> tuple[str, dict]:
    """Resuelve el perfil activo aplicando precedencia: env → yaml → fallback.

    Retorna (nombre_perfil, dict_perfil). Si el perfil pedido no existe cae al
    fallback con warning.
    """
    profiles = core.get("profiles", {}) or {}

    candidates: list[tuple[str, str]] = []
    if env_override:
        candidates.append((env_override, "env LLM_PROFILE"))
    yaml_active = core.get("active_profile")
    if yaml_active:
        candidates.append((yaml_active, "active_profile YAML"))
    candidates.append((_DEFAULT_PROFILE, "fallback"))

    for name, source in candidates:
        if name in profiles:
            logger.info(f"[CONFIG] perfil activo: {name} (fuente: {source})")
            return name, profiles[name]
        if source != "fallback":
            logger.warning(
                f"[CONFIG] perfil '{name}' (fuente: {source}) no existe en profiles — "
                f"intentando siguiente candidato"
            )

    logger.warning(
        f"[CONFIG] ningún perfil válido encontrado. profiles={list(profiles)} — "
        f"devolviendo dict vacío"
    )
    return _DEFAULT_PROFILE, {}


_llm_core: dict = _load_llm_core()
_active_profile_name, _profile = _resolve_active_profile(_llm_core, os.getenv("LLM_PROFILE"))


class Settings(BaseSettings):
    """Global settings.

    Secretos y paths vienen del .env.
    Toda la configuración LLM viene del perfil activo de config/llm_core_definitions.yaml.
    Las propiedades de compatibilidad (llm_model, director_temperature, etc.)
    delegan al perfil activo para no romper el código existente.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    env: str = "dev"
    api_host: str = "0.0.0.0:8010"

    # Override del perfil por env var (captured por pydantic-settings como LLM_PROFILE)
    llm_profile: str = ""

    # Secretos (siguen en .env)
    anthropic_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///data/dev/stories.db"

    # Paths
    output_dir: str = "frontend/public/output_stories"
    prompts_dir: str = "config/prompts_generation"
    input_dir: str = "input_stories"
    beats_definition_file: str = "config/llm_beats_definition.yaml"

    # Prompt filenames
    prompt_file_voice: str = "voice.md"
    prompt_file_system: str = "system.md"
    prompt_file_journal: str = "journal.md"

    # Prompting strategy (Spec-170): assertive | auto | descriptive
    # Vacío = no forzado por env → se lee del perfil YAML o se usa "auto"
    prompting_strategy: str = ""

    # ── Properties del perfil activo ─────────────────────────────────────────

    @property
    def active_profile_name(self) -> str:
        """Nombre del perfil actualmente activo."""
        return _active_profile_name

    @property
    def effective_prompting_strategy(self) -> str:
        """Estrategia de prompting activa: env PROMPTING_STRATEGY > perfil YAML > 'auto'."""
        if self.prompting_strategy:
            return self.prompting_strategy
        return _profile.get("prompting_strategy", "auto")

    @property
    def llm_provider(self) -> str:
        """Provider del perfil activo."""
        return _profile.get("provider", "ollama")

    @property
    def llm_role_config(self) -> dict[str, dict]:
        """Dict completo de roles del perfil activo."""
        return _profile.get("roles", {})

    def role_config(self, role: str) -> dict:
        """Config de un rol del perfil activo; los del asistente sin declarar heredan
        la del director (Spec-530)."""
        roles = self.llm_role_config
        if role not in roles and role in _ROLE_FALLBACK:
            return roles.get(_ROLE_FALLBACK[role], {})
        return roles.get(role, {})

    def role_provider(self, role: str) -> str:
        """Proveedor de un rol (Spec-480): `roles.<rol>.provider` o el del perfil."""
        return self.role_config(role).get("provider") or self.llm_provider

    @property
    def llm_providers(self) -> set[str]:
        """Proveedores en uso por los roles del perfil activo (Spec-480)."""
        return {self.role_provider(role) for role in LLM_ROLES}

    def estimated_seconds(self, kind: str) -> int:
        """Duración inicial estimada de un job del perfil activo (Spec-510)."""
        value = (_profile.get("estimated_seconds") or {}).get(kind)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            return int(value)
        return DEFAULT_ESTIMATED_SECONDS[kind]

    def active_profile_config(self) -> dict:
        """Bloque completo del perfil activo (provider, prompt_variant, roles, etc.)."""
        return _profile

    @property
    def llm_response_filter_config(self) -> dict:
        """Config de filtros de respuesta (top-level, transversal a perfiles)."""
        return _llm_core.get("response_filters", {})

    @property
    def ollama_host(self) -> str:
        # Precedencia: env OLLAMA_HOST → profiles.<perfil>.ollama.host → fallback localhost.
        # Permite que la API en Docker use host.docker.internal vía docker-compose env
        # mientras el CLI en host cae al YAML (localhost).
        env_host = os.getenv("OLLAMA_HOST")
        if env_host:
            return env_host
        return _profile.get("ollama", {}).get("host", "http://localhost:11434")

    @property
    def gemini_cli_command(self) -> str:
        return _profile.get("gemini", {}).get("cli_command", "gemini")

    @property
    def gemini_model_name(self) -> str:
        return _profile.get("gemini", {}).get("model", "gemini-1.5-pro-latest")

    @property
    def anthropic_model(self) -> str:
        return _profile.get("anthropic", {}).get("model", "claude-sonnet-4-6")

    @property
    def api_host_port(self) -> tuple[str, int]:
        host, port = self.api_host.rsplit(":", 1)
        return host, int(port)


def _reload_profile_for_tests() -> None:
    """Helper de testing: recarga _llm_core y resuelve perfil nuevamente.

    Úsalo desde tests que monkeypatcheen _LLM_CORE_FILE o variables de entorno.
    No forma parte del API público.
    """
    global _llm_core, _active_profile_name, _profile
    _llm_core = _load_llm_core()
    _active_profile_name, _profile = _resolve_active_profile(_llm_core, os.getenv("LLM_PROFILE"))


settings = Settings()
