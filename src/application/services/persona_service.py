"""PersonaService — convierte relator en persona gramatical para el prompt."""


class PersonaService:
    """Convierte el campo `relator` de una historia en persona gramatical."""

    _FEMENINOS = {"maría", "irene", "soledad", "mariana", "ana", "laura"}
    _MASCULINOS = {"ricardo", "mariano", "juan", "pedro", "diego"}

    def resolve(self, relator: str) -> str:
        normalized = relator.lower().strip()

        if normalized in ("tercera_persona", "tercera"):
            return "tercera persona"
        if normalized in ("segunda_persona", "segunda"):
            return "segunda persona"
        if normalized in ("primera_persona", "primera"):
            return "primera persona"

        if normalized in self._FEMENINOS:
            return "primera persona (ella narra)"
        if normalized in self._MASCULINOS:
            return "primera persona (él narra)"

        return f"primera persona ({relator} narra)"
