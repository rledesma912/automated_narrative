"""Tests para YamlStoryLoader."""

import tempfile
from pathlib import Path

import pytest

from src.infrastructure.loaders import YamlStoryLoader, YamlStoryLoaderError


class TestYamlStoryLoader:
    def test_carga_la_ofrenda(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert dto.title == "La ofrenda"
        assert "Ramiro" in dto.protagonista
        assert "Primera" in dto.relator or "primera" in dto.relator
        assert len(dto.sinopsis) > 100

    def test_escenarios_vienen_de_storyteller_config(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert len(dto.escenarios) == 4
        assert "El Destacamento de Cuesta del Ternero" in dto.escenarios[0]

    def test_el_monte_prohibido_escenarios(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/el_monte_prohibido.yaml"))

        assert len(dto.escenarios) == 4
        assert dto.escenarios[0] == "Casa de María"

    def test_typed_rules_tiene_content_no_text(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path("input_stories/la_ofrenda.yaml"))

        assert len(dto.typed_rules) > 0
        assert "content" in dto.typed_rules[0]
        assert "text" not in dto.typed_rules[0]

    def test_archivo_inexistente(self):
        loader = YamlStoryLoader()

        with pytest.raises(YamlStoryLoaderError) as exc:
            loader.load_from_file(Path("input_stories/no_existe.yaml"))
        assert "no encontrado" in str(exc.value).lower()

    def test_yaml_vacio(self):
        loader = YamlStoryLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            path = Path(f.name)

        with pytest.raises(YamlStoryLoaderError):
            loader.load_from_file(path)

        path.unlink()

    def test_load_from_dict(self):
        loader = YamlStoryLoader()
        dto = loader.load_from_dict(
            {
                "title": "Test",
                "protagonista": "Protagonista",
                "relator": "tercera_persona",
                "sinopsis": "Sinopsis de prueba",
                "atmosfera": "terror",
            }
        )

        assert dto.title == "Test"
        assert dto.protagonista == "Protagonista"


_OLD = {
    "title": "Viejo",
    "protagonista": "Rosa",
    "relator": "Primera persona",
    "sinopsis": "Algo pasa.",
    "personajes_full": [{"id": "P1", "name": "Rosa", "role": "peona", "traits": ["valiente"]}],
    "storyteller_config": {
        "storyteller_id": "P1",
        "storyteller_name": "Rosa",
        "voice_style": "intimista",
        "voice": {"person": "primera", "tense": "pasado", "style": "intimista"},
        "atmosphere": {"genre": "folk_horror", "subgenre": "rural", "tone": "creciente"},
        "rules": [{"id": "R1", "text": "Nadie entra de noche", "type": "fenomeno"}],
        "perception": {"reliability": "subjetiva"},
        "knowledge": {"interpretation_style": "simbolica"},
        "language": {"register": "coloquial"},
        "bias": {"fear_focus": []},
    },
}


class TestYamlViejo:
    """Spec-530 §6: el loader acepta los YAML viejos e ignora lo que ya no existe."""

    def test_ignora_claves_eliminadas(self):
        dto = YamlStoryLoader().load_from_dict(_OLD)

        assert dto.narrator_config == {
            "storyteller_id": "P1",
            "storyteller_name": "Rosa",
            "voice": {"person": "primera", "tense": "pasado"},
        }
        assert dto.personajes_full == [{"id": "P1", "name": "Rosa", "role": "peona"}]
        assert dto.typed_rules == [
            {"id": "R1", "content": "Nadie entra de noche", "applies_to_beat": None}
        ]
        assert (dto.genero, dto.subgenero) == ("folk_horror", "rural")

    @pytest.mark.parametrize(
        "atmosfera, expected",
        [
            ("folk_horror (rural)", ("folk_horror", "rural")),
            ("folk_horror (rural) - creciente", ("folk_horror", "rural")),
            ("terror - lento", ("terror", "")),
            ("", ("", "")),
        ],
    )
    def test_atmosfera_de_texto(self, atmosfera, expected):
        data = {k: v for k, v in _OLD.items() if k != "storyteller_config"}
        dto = YamlStoryLoader().load_from_dict({**data, "atmosfera": atmosfera})

        assert (dto.genero, dto.subgenero) == expected
