"""BeatResponseParser - extrae (summary, active_scenario) de la respuesta del Mapper LLM."""

import re


class BeatResponseParser:
    """Parsea la respuesta del LLM para map_one() del SynopsisBeatMapper."""

    def parse_map_one_response(
        self,
        text: str,
        macro_beat_id: int,
        cronologic_scenarios: list[str],
    ) -> tuple[str, str]:
        """Extrae (summary, active_scenario_name) de la respuesta del LLM."""
        lines = [line.strip() for line in text.strip().splitlines()]

        active_scenario = ""
        events: list[str] = []
        in_events = False

        for line in lines:
            if not line:
                continue
            line_lower = line.lower()
            is_scenario_header = bool(re.match(r"^escenario[n]?\s*:", line_lower))
            if is_scenario_header:
                if in_events:
                    break
                active_scenario = line.split(":", 1)[1].strip()
            elif line_lower.startswith("eventos:") or line_lower == "eventos":
                in_events = True
            elif in_events:
                if line.startswith("-"):
                    event_text = re.sub(r"\s*\([^)]*\)\s*$", "", line[1:].strip())
                    events.append(event_text)
                elif re.match(r"^\d+\.", line):
                    break
                elif line and not is_scenario_header:
                    event_text = re.sub(r"\s*\([^)]*\)\s*$", "", line.strip())
                    events.append(event_text)

        if not active_scenario and cronologic_scenarios:
            idx = min(macro_beat_id - 1, len(cronologic_scenarios) - 1)
            active_scenario = cronologic_scenarios[idx]

        if not events:
            summary = text.strip() or f"Acto {macro_beat_id} — sin eventos extraídos"
        else:
            summary = "\n".join(f"- {e}" for e in events)

        return summary, active_scenario
