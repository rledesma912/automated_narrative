"""Tests for PromptBuilder service."""

import json
import uuid
from unittest.mock import patch

from src.application.services import PromptBuilder
from src.domain.models import Scenario, Story


class TestPromptBuilder:
    """Tests for PromptBuilder service."""

    def test_build_system_prompt(self):
        """Test building system prompt."""
        story_id = uuid.uuid4()
        story = Story(
            id=story_id,
            title="Test",
            protagonista="Protagonist",
            relator="tercera_persona",
            sinopsis="Synopsis",
            atmosfera="terror",
            reglas=["Sin miedo"],
            scenarios=[Scenario(story_id=story_id, order_index=0, name="Location")],
        )

        builder = PromptBuilder()
        prompt = builder.build_system_prompt(story)

        assert "terror" in prompt
        assert "Protagonist" in prompt
        assert "Location" in prompt

    def test_build_beat_prompt(self):
        """Test building beat prompt."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="El protagonista entra a la casa")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat)

        assert "El protagonista entra a la casa" in prompt
        assert "terror" in prompt

    def test_build_beat_prompt_with_previous_context(self):
        """Test building beat prompt with previous beats."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat1 = Beat(
            number=1,
            summary="El protagonista llega a la puerta",
            generated_act="Llegó a la puerta.",
        )
        beat2 = Beat(number=2, summary="El protagonista sube las escaleras")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat2, previous_beats=[beat1])

        assert "2" in prompt and "El protagonista sube las escaleras" in prompt

    def test_build_beat_prompt_with_relator_name(self):
        """Test beat prompt includes specific relator name."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="Irene",
            sinopsis="Synopsis",
            atmosfera="terror",
        )

        beat = Beat(number=1, summary="Llegan a la casa")

        builder = PromptBuilder()
        prompt = builder.build_beat_prompt(story, beat)

        assert "Irene" in prompt
        assert "primera persona" in prompt.lower()

    def test_build_beat_prompt_compact_no_incluye_sinopsis(self):
        """El template compact no expone la sinopsis en el prompt (se omite por diseño)."""
        from src.domain.models import Beat

        story = Story(
            title="El Monte Prohibido",
            protagonista="Ricardo, Irene",
            relator="Irene",
            sinopsis="SINOPSIS_UNICA_IDENTIFICADORA_XYZ",
            atmosfera="terror folclórico",
        )
        beat = Beat(number=1, summary="La advertencia de la abuela")

        builder = PromptBuilder()
        # El perfil activo por defecto es compact — no requiere parcheo
        prompt = builder.build_beat_prompt(story, beat)

        assert "SINOPSIS_UNICA_IDENTIFICADORA_XYZ" not in prompt

    def test_build_beat_prompt_fallback_includes_sinopsis(self):
        """El fallback inline (sin template) incluye la sinopsis cuando la estrategia la resuelve."""
        from src.domain.models import Beat

        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            sinopsis="Sinopsis única de prueba para verificar fallback.",
            atmosfera="terror",
        )
        beat = Beat(number=1, summary="Inicio")

        builder = PromptBuilder(prompts_dir="/ruta/que/no/existe")
        sinopsis_text = "Sinopsis única de prueba para verificar fallback."
        with patch.object(builder, "_resolve_sinopsis", return_value=sinopsis_text):
            prompt = builder.build_beat_prompt(story, beat)

        assert sinopsis_text in prompt

    def test_resolve_sinopsis_full_strategy(self):
        """full: retorna la sinopsis completa sin recortar."""
        builder = PromptBuilder()
        sinopsis = "Párrafo 1.\n\nPárrafo 2.\n\nPárrafo 3.\n\nPárrafo 4.\n\nPárrafo 5."
        result = builder._resolve_sinopsis(sinopsis, beat_number=1, total_beats=5, strategy="full")
        assert result == sinopsis

    def test_resolve_sinopsis_none_strategy(self):
        """none: retorna string vacío."""
        builder = PromptBuilder()
        result = builder._resolve_sinopsis("algo", beat_number=1, total_beats=5, strategy="none")
        assert result == ""

    def test_resolve_sinopsis_beat_slice_strategy_long_sinopsis(self):
        """beat_slice con sinopsis larga: cada beat recibe su segmento proporcional."""
        builder = PromptBuilder()
        sinopsis = "\n\n".join([f"Párrafo {i}." for i in range(1, 6)])  # 5 párrafos

        s1 = builder._resolve_sinopsis(sinopsis, 1, 5, "beat_slice")
        s5 = builder._resolve_sinopsis(sinopsis, 5, 5, "beat_slice")

        assert "Párrafo 1." in s1
        assert "Párrafo 5." not in s1  # no espoilea el final
        assert "Párrafo 5." in s5

    def test_resolve_sinopsis_beat_slice_short_sinopsis_falls_back_to_two_sentences(self):
        """beat_slice con sinopsis corta: devuelve primeras 2 oraciones como contexto general."""
        builder = PromptBuilder()
        sinopsis = "Primera oración. Segunda oración. Tercera oración que espoilea el final."
        result = builder._resolve_sinopsis(
            sinopsis, beat_number=1, total_beats=5, strategy="beat_slice"
        )

        assert "Primera oración." in result
        assert "Segunda oración." in result
        assert "Tercera oración que espoilea el final." not in result

    def test_resolve_sinopsis_unknown_strategy_defaults_to_beat_slice(self):
        """Estrategia desconocida cae al comportamiento por defecto (beat_slice)."""
        builder = PromptBuilder()
        sinopsis = "Solo una oración."
        result = builder._resolve_sinopsis(sinopsis, 1, 5, "cualquier_cosa")
        assert "Solo una oración." in result

    def test_build_voice_prompt(self):
        """Test building voice prompt."""
        story = Story(
            title="Test",
            protagonista="Protagonist",
            relator="primera_persona",
            sinopsis="Synopsis",
            atmosfera="terror_psicologico",
        )

        builder = PromptBuilder()
        prompt = builder.build_voice_prompt(story)

        assert "terror_psicologico" in prompt
        assert "primera_persona" in prompt


class TestPromptVariants:
    """Tests para selección de variante compact/frontier (Spec 029)."""

    def _story(self):
        return Story(
            title="Historia de Test",
            protagonista="Ana",
            relator="primera_persona",
            sinopsis="Una mujer investiga una casa abandonada.",
            atmosfera="terror",
        )

    def test_compact_variant_loads_compact_voice_template(self):
        # El perfil activo por defecto es compact — la estrategia elige voice_compact.md
        builder = PromptBuilder()
        assert builder._get_strategy().get_template_name("voice") == "voice_compact.md"

    def test_frontier_variant_loads_standard_voice_template(self):
        builder = PromptBuilder()
        with patch.object(builder._loader, "get_variant", return_value="frontier"):
            builder._strategy = None  # forzar resolución con frontier
            assert builder._get_strategy().get_template_name("voice") == "voice.md"

    def test_compact_previous_context_max_500(self):
        from src.domain.models import Beat

        builder = PromptBuilder()
        long_content = "x" * 600
        beat = Beat(number=1, summary="s", generated_act=long_content, status="completed")
        result = builder._build_previous_context([beat], max_chars=500)
        assert len(result) < 600
        assert "x" * 500 in result

    def test_frontier_previous_context_max_150(self):
        from src.domain.models import Beat

        builder = PromptBuilder()
        long_content = "x" * 300
        beat = Beat(number=1, summary="s", generated_act=long_content, status="completed")
        result = builder._build_previous_context([beat], max_chars=150)
        assert "x" * 150 in result
        assert "x" * 151 not in result

    def test_compact_voice_beat1_uses_primer_fragmento_cta(self):
        from src.domain.models import Beat

        # Perfil activo por defecto es compact — carga voice_compact.md con {continuation_cta}
        builder = PromptBuilder()
        story = self._story()
        beat = Beat(number=1, summary="La protagonista llega a la casa")
        prompt = builder.build_beat_prompt(story, beat)
        assert "primer fragmento" in prompt

    def test_compact_voice_beat2_uses_continua_cta(self):
        from src.domain.models import Beat

        builder = PromptBuilder()
        story = self._story()
        beat = Beat(number=2, summary="El misterio se intensifica")
        prompt = builder.build_beat_prompt(story, beat)
        assert "Continúa el relato:" in prompt

    def test_compact_beat_summary_in_second_half(self):
        """El beat_summary aparece en la segunda mitad del prompt compact."""
        from src.domain.models import Beat

        builder = PromptBuilder()
        story = self._story()
        beat = Beat(number=1, summary="ESCENA_UNICA_IDENTIFICADORA")
        prompt = builder.build_beat_prompt(story, beat)
        mid = len(prompt) // 2
        assert "ESCENA_UNICA_IDENTIFICADORA" in prompt[mid:]


class TestBuildScenarioResolverPromptActsEnrichment:
    """Spec-052: acts_json incluye intent, intensity, must y must_not del YAML."""

    def _story(self):
        sid = uuid.uuid4()
        return Story(
            id=sid,
            title="T",
            protagonista="P",
            relator="tercera_persona",
            sinopsis="S",
            atmosfera="a",
            reglas=["regla 1"],
            scenarios=[Scenario(story_id=sid, order_index=0, name="Escenario A")],
        )

    def _acts(self, prompt: str) -> list[dict]:
        """Extrae la lista de acts del bloque JSON entre 'Actos:' y 'Escenarios:'."""
        block = prompt.split("Actos:\n", 1)[1].split("\n\nEscenarios", 1)[0].strip()
        return json.loads(block)

    def test_acts_json_includes_intent(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        assert all("intent" in a and a["intent"] for a in acts)

    def test_acts_json_includes_intensity(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        intensities = {a["type"]: a["intensity"] for a in acts}
        assert intensities["exposicion"] == "baja"
        assert intensities["climax"] == "alta"
        assert intensities["desenlace"] == "baja"

    def test_acts_json_includes_must(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        assert all("must" in a and isinstance(a["must"], list) and a["must"] for a in acts)

    def test_acts_json_includes_must_not(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        assert all("must_not" in a and isinstance(a["must_not"], list) for a in acts)

    def test_acts_json_excludes_anchor_priorities(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        assert all("anchor_priorities" not in a for a in acts)

    def test_acts_json_excludes_state_change(self):
        builder = PromptBuilder()
        prompt = builder.build_scenario_resolver_prompt(self._story())
        acts = self._acts(prompt)
        assert all("state_change" not in a for a in acts)
