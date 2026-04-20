"""Tests para SynopsisBeatMapper (Spec 030)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services import PromptBuilder
from src.application.use_cases.synopsis_beat_mapper import SynopsisBeatMapper
from src.domain.models import Story


def _make_story(**kwargs):
    defaults = dict(
        title="El Monte Prohibido",
        protagonista="Irene, Ricardo",
        relator="Irene",
        escenarios="El monte",
        sinopsis="Una familia sube al monte. Encuentran señales extrañas. Huyen.",
        atmosfera="terror folclórico",
    )
    defaults.update(kwargs)
    return Story(**defaults)


def _make_llm(response_text: str = "1. Llegada al monte\n2. Señales extrañas\n3. La huida"):
    llm = AsyncMock()
    llm_response = MagicMock()
    llm_response.text = response_text
    llm_response.elapsed_s = 1.0
    llm.generate = AsyncMock(return_value=llm_response)
    return llm


class TestSynopsisBeatMapper:
    def _builder(self):
        return PromptBuilder()

    @pytest.mark.asyncio
    async def test_map_returns_beats_list(self):
        llm = _make_llm("1. Llegada al monte\n2. Señales extrañas\n3. La huida\n4. El horror\n5. Resolución")
        mapper = SynopsisBeatMapper(llm, self._builder())
        beats = await mapper.map(_make_story())
        assert len(beats) == 5
        assert beats[0].number == 1
        assert "Llegada" in beats[0].summary

    @pytest.mark.asyncio
    async def test_map_uses_director_role_config(self):
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        with patch("src.application.use_cases.synopsis_beat_mapper.settings") as mock_s:
            mock_s.role_config.return_value = {"model": "test-model", "temperature": 0.3}
            mock_s.llm_model = "fallback-model"
            mapper = SynopsisBeatMapper(llm, self._builder())
            await mapper.map(_make_story())
            mock_s.role_config.assert_called_with("director")
            call_kwargs = llm.generate.call_args.kwargs
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["temperature"] == 0.3
            assert call_kwargs["role"] == "director"

    @pytest.mark.asyncio
    async def test_map_normalizes_response(self):
        raw = "### Encabezado\n1. Primer beat\n2. Segundo beat\n3. Tercero\n4. Cuarto\n5. Quinto"
        llm = _make_llm(raw)
        normalizer = MagicMock()
        normalizer.normalize.return_value = "1. Primer beat\n2. Segundo beat\n3. Tercero\n4. Cuarto\n5. Quinto"
        mapper = SynopsisBeatMapper(llm, self._builder(), normalizer=normalizer)
        beats = await mapper.map(_make_story())
        normalizer.normalize.assert_called_once()
        assert len(beats) == 5

    @pytest.mark.asyncio
    async def test_map_respects_num_beats_from_yaml(self):
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        builder = self._builder()
        mapper = SynopsisBeatMapper(llm, builder)
        beats = await mapper.map(_make_story())
        assert len(beats) == builder.num_beats

    @pytest.mark.asyncio
    async def test_map_fallback_on_unreadable_response(self):
        llm = _make_llm("Aquí tienes una historia muy larga sin formato numérico.")
        mapper = SynopsisBeatMapper(llm, self._builder())
        beats = await mapper.map(_make_story())
        assert len(beats) == self._builder().num_beats
        assert all("generado automáticamente" in b.summary for b in beats)

    @pytest.mark.asyncio
    async def test_compact_variant_loads_system_prompt_if_file_exists(self):
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        builder = self._builder()
        with patch.object(builder, "_get_prompt_variant", return_value="compact"):
            mapper = SynopsisBeatMapper(llm, builder)
            await mapper.map(_make_story())
        call_kwargs = llm.generate.call_args.kwargs
        # synopsis_mapper_system_compact.md existe → system_prompt es str no vacío
        assert call_kwargs["system_prompt"] is not None
        assert len(call_kwargs["system_prompt"]) > 0

    @pytest.mark.asyncio
    async def test_frontier_variant_passes_system_prompt(self):
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        builder = self._builder()
        with patch.object(builder, "_get_prompt_variant", return_value="frontier"):
            mapper = SynopsisBeatMapper(llm, builder)
            await mapper.map(_make_story())
        call_kwargs = llm.generate.call_args.kwargs
        assert call_kwargs["system_prompt"] is not None
        assert len(call_kwargs["system_prompt"]) > 0

    @pytest.mark.asyncio
    async def test_map_with_empty_brief_behaves_as_before(self):
        """map() sin narrative_brief es backwards compatible."""
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        mapper = SynopsisBeatMapper(llm, self._builder())
        beats = await mapper.map(_make_story())
        assert len(beats) == 5

    @pytest.mark.asyncio
    async def test_map_with_brief_injects_into_prompt(self):
        """El narrative_brief se inyecta en el prompt del mapper."""
        llm = _make_llm("1. A\n2. B\n3. C\n4. D\n5. E")
        builder = self._builder()
        mapper = SynopsisBeatMapper(llm, builder)
        brief = "Amenaza: fantasma del monte. Estado inicial: tranquila."
        await mapper.map(_make_story(), narrative_brief=brief)
        prompt_sent = llm.generate.call_args.kwargs["prompt"]
        assert brief in prompt_sent
