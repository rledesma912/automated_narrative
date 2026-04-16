"""Tests for CLI logger."""

import tempfile

import pytest

from src.cli.logger import NarrativeLogger


class TestNarrativeLogger:
    """Tests for NarrativeLogger."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_logger_creates_log_directory(self, temp_log_dir):
        """Test that logger creates log directory."""
        from pathlib import Path

        NarrativeLogger(log_dir=Path(temp_log_dir))

        assert (Path(temp_log_dir)).exists()

    def test_logger_writes_to_file(self, temp_log_dir):
        """Test that logger writes to file."""
        import datetime
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))
        logger.info("Test message", module="test", line=1)

        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = Path(temp_log_dir) / f"narrative-{today}.log"

        assert log_file.exists()

    def test_logger_error_writes_to_error_file(self, temp_log_dir):
        """Test that error logger writes to error file."""
        import datetime
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))
        logger.error("Error message", module="test", line=1)

        today = datetime.datetime.now().strftime("%Y%m%d")
        error_log = Path(temp_log_dir) / f"narrative-error-{today}.log"

        assert error_log.exists()

    def test_logger_has_all_levels(self, temp_log_dir):
        """Test that logger has all levels configured."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert logger._logger is not None
        assert logger._error_logger is not None

    def test_logger_debug_method_exists(self, temp_log_dir):
        """Test that debug method exists."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert hasattr(logger, "debug")
        assert callable(logger.debug)

    def test_logger_info_method_exists(self, temp_log_dir):
        """Test that info method exists."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert hasattr(logger, "info")
        assert callable(logger.info)

    def test_logger_warning_method_exists(self, temp_log_dir):
        """Test that warning method exists."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert hasattr(logger, "warning")
        assert callable(logger.warning)

    def test_logger_error_method_exists(self, temp_log_dir):
        """Test that error method exists."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert hasattr(logger, "error")
        assert callable(logger.error)

    def test_logger_critical_method_exists(self, temp_log_dir):
        """Test that critical method exists."""
        from pathlib import Path

        logger = NarrativeLogger(log_dir=Path(temp_log_dir))

        assert hasattr(logger, "critical")
        assert callable(logger.critical)
