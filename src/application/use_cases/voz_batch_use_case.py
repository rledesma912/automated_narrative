"""VozBatchUseCase - genera todos los beats."""

from src.application.use_cases.voz_use_case import VozUseCase
from src.domain.models import Beat, Story


class VozBatchUseCase:
    """Caso de uso para narrar múltiples beats (Voz)."""

    def __init__(self, voz_use_case: VozUseCase):
        self.voz = voz_use_case

    async def execute(
        self,
        story: Story,
        beats: list[Beat],
    ) -> list[Beat]:
        """Narra todos los beats en secuencia."""
        completed_beats = []
        journal = None

        for beat in beats:
            if beat.status == "completed":
                completed_beats.append(beat)
                continue

            generated_beat, journal = await self.voz.execute(
                story=story,
                beat=beat,
                previous_beats=completed_beats,
                journal=journal,
            )

            completed_beats.append(generated_beat)

        return completed_beats


# Alias para backwards compatibility
NarrateBatchUseCase = VozBatchUseCase
