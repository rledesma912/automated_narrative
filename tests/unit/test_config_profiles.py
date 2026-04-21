"""Tests para el resolver de perfiles LLM (Spec 027)."""

from src.config import _DEFAULT_PROFILE, _resolve_active_profile


def _core_with_profiles() -> dict:
    return {
        "active_profile": "ollama-natsumura",
        "profiles": {
            "ollama-natsumura": {
                "provider": "ollama",
                "ollama": {"host": "http://localhost:11434"},
                "roles": {
                    "director": {"model": "Tohur/natsumura", "temperature": 0.4},
                    "voz": {"model": "Tohur/natsumura", "temperature": 0.6},
                    "journal": {"model": "mistral:latest", "temperature": 0.3},
                },
            },
            "anthropic-sonnet": {
                "provider": "anthropic",
                "anthropic": {"model": "claude-sonnet-4-6"},
                "roles": {
                    "director": {"model": "claude-sonnet-4-6", "temperature": 0.4},
                    "voz": {"model": "claude-sonnet-4-6", "temperature": 0.6},
                    "journal": {"model": "claude-sonnet-4-6", "temperature": 0.3},
                },
            },
        },
    }


class TestResolveActiveProfile:
    def test_active_profile_from_yaml(self):
        """Sin env override, usa active_profile: de la YAML."""
        core = _core_with_profiles()
        name, profile = _resolve_active_profile(core, env_override=None)

        assert name == "ollama-natsumura"
        assert profile["provider"] == "ollama"
        assert profile["roles"]["voz"]["model"] == "Tohur/natsumura"

    def test_env_override_wins_over_yaml(self):
        """LLM_PROFILE pisa active_profile de la YAML."""
        core = _core_with_profiles()
        name, profile = _resolve_active_profile(core, env_override="anthropic-sonnet")

        assert name == "anthropic-sonnet"
        assert profile["provider"] == "anthropic"
        assert profile["roles"]["voz"]["model"] == "claude-sonnet-4-6"

    def test_env_empty_string_treated_as_no_override(self):
        """Env vacío no debe pisar el YAML (pydantic default es '')."""
        core = _core_with_profiles()
        name, _ = _resolve_active_profile(core, env_override="")

        assert name == "ollama-natsumura"

    def test_unknown_env_profile_falls_back_to_yaml(self):
        """Si env apunta a un perfil inexistente, cae al active_profile de la YAML."""
        core = _core_with_profiles()
        name, profile = _resolve_active_profile(core, env_override="no-existe")

        assert name == "ollama-natsumura"
        assert profile["provider"] == "ollama"

    def test_unknown_yaml_profile_falls_back_to_default(self):
        """Si active_profile del YAML no existe, cae al _DEFAULT_PROFILE."""
        core = _core_with_profiles()
        core["active_profile"] = "perfil-fantasma"
        name, profile = _resolve_active_profile(core, env_override=None)

        assert name == _DEFAULT_PROFILE
        assert profile["provider"] == "ollama"

    def test_no_profiles_returns_empty_dict(self):
        """Sin profiles definidos devuelve dict vacío para no crashear al runtime."""
        name, profile = _resolve_active_profile({}, env_override=None)

        assert profile == {}
        assert name == _DEFAULT_PROFILE

    def test_role_config_reflects_active_profile(self):
        """Cambiar de perfil cambia el modelo devuelto por cada rol."""
        core = _core_with_profiles()

        _, ollama_profile = _resolve_active_profile(core, env_override=None)
        _, anthropic_profile = _resolve_active_profile(core, env_override="anthropic-sonnet")

        assert ollama_profile["roles"]["director"]["model"] == "Tohur/natsumura"
        assert anthropic_profile["roles"]["director"]["model"] == "claude-sonnet-4-6"

    def test_llm_provider_reflects_active_profile(self):
        """Cambiar de perfil cambia el provider."""
        core = _core_with_profiles()

        _, ollama_profile = _resolve_active_profile(core, env_override=None)
        _, anthropic_profile = _resolve_active_profile(core, env_override="anthropic-sonnet")

        assert ollama_profile["provider"] == "ollama"
        assert anthropic_profile["provider"] == "anthropic"

    def test_precedence_chain_env_beats_yaml_beats_fallback(self):
        """Orden de precedencia: env válido > yaml válido > fallback."""
        core = _core_with_profiles()

        _, env_wins = _resolve_active_profile(core, env_override="anthropic-sonnet")
        assert env_wins["provider"] == "anthropic"

        _, yaml_wins = _resolve_active_profile(core, env_override="inexistente")
        assert yaml_wins["provider"] == "ollama"  # YAML active_profile = ollama-natsumura

        core_no_yaml = {"profiles": core["profiles"]}
        _, fallback = _resolve_active_profile(core_no_yaml, env_override=None)
        assert fallback["provider"] == "ollama"  # fallback = ollama-natsumura

    def test_active_profile_config_returns_full_block(self):
        """settings.active_profile_config() devuelve el bloque completo con prompt_variant."""
        from src.config import settings

        profile = settings.active_profile_config()
        assert isinstance(profile, dict)
        assert "provider" in profile
        assert "roles" in profile
        assert "prompt_variant" in profile
