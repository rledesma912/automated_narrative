# ruff: noqa — script de investigación de la Spec-530, se conserva tal como se corrió.
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/mnt/LLM/apps/automated_narrative")
import scripts.evaluate_voice as ev

S = Path(__file__).parent


async def main():
    for label, f in [("base", "pena.yaml"), ("escaleta", "pena_escaleta.yaml")]:
        ev.STORY_FILE = S / f
        await ev.run(label, ["sin"], 1, S / "out")


asyncio.run(main())
