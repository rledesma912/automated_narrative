"""Tests para BeatResponseParser."""

import pytest

from src.infrastructure.parsers.beat_response_parser import BeatResponseParser


@pytest.fixture
def parser():
    return BeatResponseParser()


class TestBeatResponseParser:

    def test_parse_scenario_and_events(self, parser):
        """Respuesta bien formateada — extrae escenario y eventos correctamente."""
        text = (
            "ESCENARIO: La casa de campo\n\n"
            "EVENTOS:\n"
            "- La familia llega al atardecer\n"
            "- La abuela advierte sobre el monte\n"
            "- La fiesta comienza"
        )
        summary, scenario = parser.parse_map_one_response(text, 1, [])

        assert scenario == "La casa de campo"
        assert "La familia llega al atardecer" in summary
        assert "La abuela advierte" in summary

    def test_parse_with_empty_events(self, parser):
        """Sin bullets de eventos — summary cae al texto completo."""
        text = "ESCENARIO: El monte\n\nAlgo ocurrió aquí sin formato de lista."

        summary, scenario = parser.parse_map_one_response(text, 2, [])

        assert scenario == "El monte"
        assert "Algo ocurrió aquí" in summary

    def test_parse_invalid_format(self, parser):
        """Texto sin formato reconocible — summary es el texto completo, scenario vacío."""
        text = "Lorem ipsum sin estructura alguna."

        summary, scenario = parser.parse_map_one_response(text, 1, [])

        assert scenario == ""
        assert "Lorem ipsum" in summary

    def test_fallback_scenario_by_position(self, parser):
        """Sin ESCENARIO: en la respuesta — usa posición en cronologic_scenarios."""
        text = "EVENTOS:\n- La tormenta llegó\n- El camino se cortó"
        scenarios = ["Casa", "Monte", "Camino"]

        summary, scenario = parser.parse_map_one_response(text, 2, scenarios)

        assert scenario == "Monte"

    def test_fallback_scenario_clamps_to_last(self, parser):
        """beat_id > len(scenarios) — usa el último escenario disponible."""
        text = "EVENTOS:\n- Algo pasó"
        scenarios = ["Casa", "Monte"]

        summary, scenario = parser.parse_map_one_response(text, 10, scenarios)

        assert scenario == "Monte"

    def test_second_escenario_block_stops_parsing(self, parser):
        """Segundo bloque ESCENARIO dentro de eventos detiene el parseo."""
        text = (
            "ESCENARIO: Primer lugar\n"
            "EVENTOS:\n"
            "- Evento uno\n"
            "ESCENARIO: Segundo lugar\n"
            "- Evento del siguiente acto"
        )
        summary, scenario = parser.parse_map_one_response(text, 1, [])

        assert scenario == "Primer lugar"
        assert "Evento uno" in summary
        assert "Segundo lugar" not in summary

    def test_events_with_parenthetical_stripped(self, parser):
        """Paréntesis al final de un evento se eliminan."""
        text = "ESCENARIO: Bosque\nEVENTOS:\n- La figura apareció (detalle extra)"

        summary, _ = parser.parse_map_one_response(text, 1, [])

        assert "(detalle extra)" not in summary
        assert "La figura apareció" in summary

    def test_empty_text_returns_fallback_summary(self, parser):
        """Texto vacío — summary usa el texto de fallback con el beat_id."""
        summary, scenario = parser.parse_map_one_response("", 3, [])

        assert "3" in summary
        assert scenario == ""
