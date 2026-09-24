"""PersonaService — resuelve la perspectiva gramatical del narrador."""

import logging

logger = logging.getLogger(__name__)


class PersonaService:
    """
    Convierte la identidad del narrador en instrucciones gramaticales.

    Prioridad:
    1. narrator_config['voice']['person']
    2. narrator_config['gender']
    3. Mapeo directo de palabras clave en 'relator'
    """

    def resolve(self, relator: str, narrator_config: dict | None = None) -> str:
        config = narrator_config or {}
        voice = config.get("voice", {})

        # 1. Configuración explícita de Voz
        person = voice.get("person")
        if person:
            person_map = {
                "primera": "primera persona",
                "segunda": "segunda persona",
                "tercera": "tercera persona",
            }
            base_person = person_map.get(person.lower(), person)

            # Ajuste de género si es primera persona
            gender = config.get("gender", "").lower()
            if "primera" in base_person:
                if "femenino" in gender or "mujer" in gender or "ella" in gender:
                    return "primera persona (ella narra)"
                if "masculino" in gender or "hombre" in gender or "él" in gender:
                    return "primera persona (él narra)"
            return base_person

        # 2. Mapeo por palabra clave en el campo relator (Fallback)
        normalized = relator.lower().strip()

        if "tercera" in normalized or "3ra" in normalized:
            return "tercera persona"
        if "segunda" in normalized or "2da" in normalized:
            return "segunda persona"
        if "primera" in normalized or "1ra" in normalized:
            return "primera persona"

        # 3. Fallback final
        return f"primera persona ({relator} narra)"
