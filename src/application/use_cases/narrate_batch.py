"""NarrateBatchUseCase - genera todos los beats."""

from src.application.use_cases.narrate_beat import NarrateBeatUseCase
from src.domain.models import Beat, Story


class NarrateBatchUseCase:
    """Caso de uso para narrar múltiples beats."""

    def __init__(self, narrate_beat_use_case: NarrateBeatUseCase):
        self.narrate_beat = narrate_beat_use_case

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

            generated_beat, journal = await self.narrate_beat.execute(
                story=story,
                beat=beat,
                previous_beats=completed_beats,
                journal=journal,
            )

            completed_beats.append(generated_beat)

        return completed_beats
