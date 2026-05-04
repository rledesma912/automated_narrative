"""Tests para CLIContainer."""

from src.application.use_cases import CreateStoryUseCase, DirectorUseCase, VozUseCase
from src.infrastructure.adapters import MockLLMAdapter
from src.infrastructure.container import CLIContainer
from src.infrastructure.database.repositories import SQLBeatRepository, SQLStoryRepository


class TestCLIContainer:
    def test_llm_con_mock(self):
        container = CLIContainer(use_mock=True)
        assert isinstance(container.llm, MockLLMAdapter)

    def test_llm_cached(self):
        container = CLIContainer(use_mock=True)
        assert container.llm is container.llm

    def test_story_repo_es_sql(self):
        container = CLIContainer()
        assert isinstance(container.story_repo, SQLStoryRepository)

    def test_story_repo_cached(self):
        container = CLIContainer()
        assert container.story_repo is container.story_repo

    def test_beat_repo_es_sql(self):
        container = CLIContainer()
        assert isinstance(container.beat_repo, SQLBeatRepository)

    def test_beat_repo_cached(self):
        container = CLIContainer()
        assert container.beat_repo is container.beat_repo

    def test_debug_collector_debug_true(self):
        container = CLIContainer(debug=True)
        from src.application.services.debug_collector import DebugCollector

        assert isinstance(container.debug_collector, DebugCollector)

    def test_debug_collector_debug_false(self):
        container = CLIContainer(debug=False)
        from src.application.services.debug_collector import NullDebugCollector

        assert isinstance(container.debug_collector, NullDebugCollector)

    def test_story_runner_tipo(self, tmp_path):
        container = CLIContainer(use_mock=True, output_dir=tmp_path)
        from src.core.orchestrator import StoryRunner

        runner = container.story_runner(tmp_path)
        assert isinstance(runner, StoryRunner)

    def test_director_use_case_tipo(self):
        container = CLIContainer(use_mock=True)
        use_case = container.director_use_case()
        assert isinstance(use_case, DirectorUseCase)

    def test_create_story_use_case_tipo(self):
        container = CLIContainer()
        use_case = container.create_story_use_case()
        assert isinstance(use_case, CreateStoryUseCase)

    def test_voz_use_case_tipo(self):
        container = CLIContainer(use_mock=True)
        use_case = container.voz_use_case()
        assert isinstance(use_case, VozUseCase)

    def test_prompt_builder(self):
        container = CLIContainer()
        from src.application.services import PromptBuilder

        assert isinstance(container.prompt_builder, PromptBuilder)

    def test_reporter(self):
        container = CLIContainer()
        from src.cli.progress import ProgressReporter

        assert isinstance(container.reporter, ProgressReporter)
