"""Response normalizer for LLM output."""

import re


class ResponseNormalizer:
    """Normalizes LLM responses."""

    def __init__(self):
        self.thinking_tags = ["think", "thought"]
        self.noise_patterns = []

    def normalize(self, text: str) -> str:
        """Normalize LLM response."""
        result = text.strip()

        for tag in self.thinking_tags:
            pattern = rf"<{tag}>.*?</{tag}>"
            result = re.sub(pattern, "", result, flags=re.DOTALL)

        result = re.sub(r"```[\s\S]*?```", "", result)

        lines = [line.strip() for line in result.split("\n") if line.strip()]
        result = "\n".join(lines)

        return result.strip()
