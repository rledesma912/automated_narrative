"""CLIContainer: Centralized dependency injection for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.application.services import PromptBuilder
from src.application.services.debug_collector import DebugCollector, NullDebugCollector
from src.application.use_cases import CreateStoryUseCase, DirectorUseCase, VozUseCase
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository
from src.infrastructure.factories import LLMFactory

if TYPE_CHECKING:
    from src.cli.progress import ProgressReporter
    from src.core.orchestrator import StoryRunner
    from src.infrastructure.parsers import MarkdownStoryParser
    from src.infrastructure.renderers import MarkdownRenderer


class CLIContainer:
    """Dependency container for CLI commands."""

    def __init__(
        self,
        use_mock: bool = False,
        provider: str | None = None,
        debug: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        self._use_mock = use_mock
        self._provider = provider
        self._debug = debug
        self._output_dir = output_dir

        self._llm = None
        self._story_repo = None
        self._beat_repo = None
        self._prompt_builder = None
        self._reporter = None
        self._debug_collector = None
        self._markdown_renderer = None
        self._markdown_parser = None

    @property
    def llm(self) -> LLMFactory:
        if self._llm is None:
            self._llm = LLMFactory.get_provider(use_mock=self._use_mock, provider=self._provider)
        return self._llm

    @property
    def story_repo(self) -> SQLStoryRepository:
        if self._story_repo is None:
            self._story_repo = SQLStoryRepository()
        return self._story_repo

    @property
    def beat_repo(self) -> SQLBeatRepository:
        if self._beat_repo is None:
            self._beat_repo = SQLBeatRepository()
        return self._beat_repo

    @property
    def prompt_builder(self) -> PromptBuilder:
        if self._prompt_builder is None:
            self._prompt_builder = PromptBuilder()
        return self._prompt_builder

    @property
    def reporter(self) -> "ProgressReporter":
        from src.cli.progress import ProgressReporter

        if self._reporter is None:
            self._reporter = ProgressReporter()
        return self._reporter

    @property
    def debug_collector(self) -> DebugCollector | NullDebugCollector:
        if self._debug_collector is None:
            self._debug_collector = DebugCollector() if self._debug else NullDebugCollector()
        return self._debug_collector

    @property
    def markdown_renderer(self) -> "MarkdownRenderer":
        if self._markdown_renderer is None:
            from src.infrastructure.renderers import MarkdownRenderer

            self._markdown_renderer = MarkdownRenderer()
        return self._markdown_renderer

    @property
    def markdown_parser(self) -> "MarkdownStoryParser":
        if self._markdown_parser is None:
            from src.infrastructure.parsers import MarkdownStoryParser

            self._markdown_parser = MarkdownStoryParser()
        return self._markdown_parser

    def create_story_use_case(self) -> CreateStoryUseCase:
        return CreateStoryUseCase(self.story_repo)

    def director_use_case(self) -> DirectorUseCase:
        return DirectorUseCase(self.llm, self.prompt_builder)

    def voz_use_case(self) -> VozUseCase:
        return VozUseCase(self.llm)

    def story_runner(self, output_dir: Path) -> "StoryRunner":
        from src.core.orchestrator import StoryRunner

        return StoryRunner(
            llm_adapter=self.llm,
            story_repo=self.story_repo,
            beat_repo=self.beat_repo,
            prompt_builder=self.prompt_builder,
            output_dir=output_dir,
            reporter=self.reporter,
            debug_collector=self.debug_collector,
        )
