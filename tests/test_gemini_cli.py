"""Tests for Gemini CLI integration in llm_services and agent_orchestrator."""

import asyncio
import glob
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from codewiki.src.be.utils import sanitize_filename
from codewiki.src.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(use_gemini_cli: bool = True, main_model: str = "gemini-pro") -> Config:
    """Return a minimal Config wired for Gemini CLI tests."""
    return Config(
        repo_path="/tmp/fake_repo",
        output_dir="/tmp/fake_output",
        dependency_graph_dir="/tmp/fake_output/dep",
        docs_dir="/tmp/fake_output/wiki",
        max_depth=2,
        llm_base_url="",
        llm_api_key="",
        main_model=main_model,
        cluster_model=main_model,
        use_gemini_cli=use_gemini_cli,
    )


def _completed(stdout: str = "response text", returncode: int = 0):
    """Build a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["gemini"], returncode=returncode, stdout=stdout, stderr=""
    )


# ===================================================================
# call_llm – small prompt path (stdin piping)
# ===================================================================


class TestCallLlmSmallPrompt:
    """Prompts under the STDIN_SAFE_LIMIT should be piped via stdin."""

    @patch("subprocess.run", return_value=_completed("  hello world  "))
    def test_basic_invocation(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        result = call_llm("short prompt", _make_config())

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gemini", "-y", "-p"]
        assert mock_run.call_args[1]["input"] == "short prompt"
        assert result == "hello world"  # stripped

    @patch("subprocess.run", return_value=_completed("ok"))
    def test_model_flag_appended(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        call_llm("hi", _make_config(main_model="gemini-2.5-pro"))
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "gemini-2.5-pro" in cmd

    @patch("subprocess.run", return_value=_completed("ok"))
    def test_model_flag_omitted_when_empty(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        call_llm("hi", _make_config(main_model=""))
        cmd = mock_run.call_args[0][0]
        assert "-m" not in cmd

    @patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, ["gemini"], stderr="boom")
    )
    def test_subprocess_error_propagated(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        with pytest.raises(subprocess.CalledProcessError):
            call_llm("hi", _make_config())


# ===================================================================
# call_llm – large prompt path (temp file)
# ===================================================================


class TestCallLlmLargePrompt:
    """Prompts over 100 KB should be written to a temp file."""

    LARGE_PROMPT = "x" * 200_000  # ~200 KB

    @patch("subprocess.run", return_value=_completed("<DOCUMENTATION>doc</DOCUMENTATION>"))
    def test_writes_temp_file_and_passes_path_in_prompt(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        call_llm(self.LARGE_PROMPT, _make_config())

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        # No stdin piping for large prompts
        assert "input" not in mock_run.call_args[1]
        # The -p value should reference a temp file path
        p_index = cmd.index("-p")
        p_value = cmd[p_index + 1]
        assert "/tmp/" in p_value or "codewiki_prompt_" in p_value

    @patch("subprocess.run", return_value=_completed("response"))
    def test_temp_file_cleaned_up_after_success(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        call_llm(self.LARGE_PROMPT, _make_config())
        remaining = glob.glob("/tmp/codewiki_prompt_*")
        assert len(remaining) == 0, f"Leaked temp files: {remaining}"

    @patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["gemini"], stderr="sandbox error"),
    )
    def test_temp_file_cleaned_up_on_error(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        with pytest.raises(subprocess.CalledProcessError):
            call_llm(self.LARGE_PROMPT, _make_config())

        remaining = glob.glob("/tmp/codewiki_prompt_*")
        assert len(remaining) == 0, f"Leaked temp files: {remaining}"

    @patch("subprocess.run", return_value=_completed("ok"))
    def test_model_flag_appended_for_large(self, mock_run):
        from codewiki.src.be.llm_services import call_llm

        call_llm(self.LARGE_PROMPT, _make_config(main_model="gemini-2.5-pro"))
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "gemini-2.5-pro" in cmd


# ===================================================================
# call_llm – OpenAI fallback (use_gemini_cli=False)
# ===================================================================


class TestCallLlmOpenAI:
    """When use_gemini_cli is False, the OpenAI client path is used."""

    @patch("codewiki.src.be.llm_services.create_openai_client")
    def test_uses_openai_when_flag_disabled(self, mock_create):
        from codewiki.src.be.llm_services import call_llm

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="openai response"))]
        )
        mock_create.return_value = mock_client

        config = _make_config(use_gemini_cli=False)
        result = call_llm("prompt", config)
        assert result == "openai response"
        mock_client.chat.completions.create.assert_called_once()


# ===================================================================
# AgentOrchestrator – Gemini CLI predictive one-shot path
# ===================================================================


class TestAgentOrchestratorGeminiCLI:
    """Test the one-shot predictive generation bypass in AgentOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        config = _make_config(use_gemini_cli=True)
        with patch("codewiki.src.be.agent_orchestrator.create_fallback_models"):
            from codewiki.src.be.agent_orchestrator import AgentOrchestrator

            orch = AgentOrchestrator(config)
            # Mock create_agent to avoid OpenAI client initialization
            orch.create_agent = MagicMock()
            return orch

    @patch("codewiki.src.be.llm_services.call_llm")
    @patch("codewiki.src.utils.file_manager.load_json", return_value={})
    @patch("codewiki.src.utils.file_manager.save_text")
    @patch("os.path.exists", return_value=False)
    def test_one_shot_extracts_documentation_tags(
        self, mock_exists, mock_save, mock_load, mock_call, orchestrator
    ):
        """When Gemini CLI returns <DOCUMENTATION> tags, content is extracted."""
        mock_call.return_value = (
            "Preamble\n<DOCUMENTATION>\n# Module Docs\nContent here\n</DOCUMENTATION>\nDone."
        )

        asyncio.get_event_loop().run_until_complete(
            orchestrator.process_module(
                module_name="test_mod",
                components={},
                core_component_ids=[],
                module_path=["test_mod"],
                working_dir="/tmp/fake_output/wiki",
            )
        )

        mock_save.assert_called_once()
        saved_content = mock_save.call_args[0][0]
        assert saved_content == "# Module Docs\nContent here"
        assert "<DOCUMENTATION>" not in saved_content

    @patch("codewiki.src.be.llm_services.call_llm")
    @patch("codewiki.src.utils.file_manager.load_json", return_value={})
    @patch("codewiki.src.utils.file_manager.save_text")
    @patch("os.path.exists", return_value=False)
    def test_one_shot_uses_raw_when_no_tags(
        self, mock_exists, mock_save, mock_load, mock_call, orchestrator
    ):
        """When Gemini CLI returns raw markdown (no tags), it's saved as-is."""
        mock_call.return_value = "# Module Docs\nRaw content"

        asyncio.get_event_loop().run_until_complete(
            orchestrator.process_module(
                module_name="test_mod",
                components={},
                core_component_ids=[],
                module_path=["test_mod"],
                working_dir="/tmp/fake_output/wiki",
            )
        )

        saved_content = mock_save.call_args[0][0]
        assert saved_content == "# Module Docs\nRaw content"

    @patch("codewiki.src.be.llm_services.call_llm", side_effect=Exception("CLI failed"))
    @patch("codewiki.src.utils.file_manager.load_json", return_value={})
    @patch("os.path.exists", return_value=False)
    def test_one_shot_propagates_errors(self, mock_exists, mock_load, mock_call, orchestrator):
        """Errors from call_llm should propagate up."""
        with pytest.raises(Exception, match="CLI failed"):
            asyncio.get_event_loop().run_until_complete(
                orchestrator.process_module(
                    module_name="test_mod",
                    components={},
                    core_component_ids=[],
                    module_path=["test_mod"],
                    working_dir="/tmp/fake_output/wiki",
                )
            )

    @patch("codewiki.src.be.llm_services.call_llm")
    @patch("codewiki.src.utils.file_manager.load_json", return_value={})
    @patch("codewiki.src.utils.file_manager.save_text")
    @patch("os.path.exists", return_value=True)
    def test_skips_existing_docs(self, mock_exists, mock_save, mock_load, mock_call, orchestrator):
        """Should skip generation when docs already exist."""
        asyncio.get_event_loop().run_until_complete(
            orchestrator.process_module(
                module_name="test_mod",
                components={},
                core_component_ids=[],
                module_path=["test_mod"],
                working_dir="/tmp/fake_output/wiki",
            )
        )
        mock_call.assert_not_called()
        mock_save.assert_not_called()

    @patch("codewiki.src.be.llm_services.call_llm")
    @patch("codewiki.src.utils.file_manager.load_json", return_value={})
    @patch("codewiki.src.utils.file_manager.save_text")
    @patch("os.path.exists", return_value=False)
    def test_one_shot_saves_with_sanitized_filename(
        self, mock_exists, mock_save, mock_load, mock_call, orchestrator
    ):
        """File should be saved with sanitized (lowercase, hyphenated) name."""
        mock_call.return_value = "<DOCUMENTATION>content</DOCUMENTATION>"

        asyncio.get_event_loop().run_until_complete(
            orchestrator.process_module(
                module_name="Core Engine",
                components={},
                core_component_ids=[],
                module_path=["Core Engine"],
                working_dir="/tmp/fake_output/wiki",
            )
        )

        saved_path = mock_save.call_args[0][1]
        assert "core-engine.md" in saved_path
        assert "Core Engine.md" not in saved_path


# ===================================================================
# sanitize_filename
# ===================================================================


class TestSanitizeFilename:
    """Test filename sanitization for wiki page files."""

    def test_spaces_to_hyphens(self):
        assert sanitize_filename("Core Engine") == "core-engine"

    def test_uppercase_to_lowercase(self):
        assert sanitize_filename("API Gateway") == "api-gateway"

    def test_underscores_to_hyphens(self):
        assert sanitize_filename("my_module") == "my-module"

    def test_special_chars_removed(self):
        assert sanitize_filename("Data Processing & Storage") == "data-processing-storage"

    def test_multiple_spaces_collapsed(self):
        assert sanitize_filename("foo   bar") == "foo-bar"

    def test_leading_trailing_stripped(self):
        assert sanitize_filename("  hello  ") == "hello"

    def test_mixed_separators(self):
        assert sanitize_filename("some_module - v2") == "some-module-v2"

    def test_already_clean(self):
        assert sanitize_filename("clean-name") == "clean-name"
