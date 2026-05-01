"""Tests para el módulo checkpoint (Spec-040)."""

import pytest

from src.application.services.checkpoint import (
    VALID_CHECKPOINTS,
    label,
    ordinal,
    validate,
)


class TestValidate:
    def test_validate_valid_names(self):
        for name in VALID_CHECKPOINTS:
            validate(name)

    def test_validate_invalid_raises(self):
        with pytest.raises(ValueError) as exc_info:
            validate("foo")
        assert "foo" in str(exc_info.value)
        assert "analyst" in str(exc_info.value)

    def test_validate_empty_raises(self):
        with pytest.raises(ValueError):
            validate("")

    def test_validate_mapper_out_of_range(self):
        with pytest.raises(ValueError) as exc_info:
            validate("mapper:9")
        assert "mapper:9" in str(exc_info.value)


class TestOrdinal:
    def test_ordinal_analyst(self):
        assert ordinal("analyst") == 1

    def test_ordinal_mapper_beat_1(self):
        assert ordinal("mapper:1") == 2

    def test_ordinal_voz_beat_1(self):
        assert ordinal("voz:1") == 3

    def test_ordinal_journal_beat_1(self):
        assert ordinal("journal:1") == 4

    def test_ordinal_mapper_beat_5(self):
        assert ordinal("mapper:5") == 14

    def test_ordinal_voz_beat_5(self):
        assert ordinal("voz:5") == 15

    def test_ordinal_journal_beat_5(self):
        assert ordinal("journal:5") == 16


class TestLabel:
    def test_label_analyst(self):
        assert "Analyst" in label("analyst")

    def test_label_mapper_1(self):
        assert "Mapper" in label("mapper:1")
        assert "Beat 1" in label("mapper:1")

    def test_label_voz_3(self):
        assert "Voz" in label("voz:3")
        assert "Beat 3" in label("voz:3")

    def test_label_journal_5(self):
        assert "Journal" in label("journal:5")
        assert "Beat 5" in label("journal:5")

    def test_label_unknown_returns_input(self):
        assert label("unknown") == "unknown"
