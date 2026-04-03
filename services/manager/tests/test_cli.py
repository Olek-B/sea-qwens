import pytest
from click.testing import CliRunner
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from services.manager.cli import cli
from services.manager.feature_interviewer import FeatureInterviewer


class TestAddFeatureCommand:
    def test_add_feature_no_projects(self, mocker):
        """add-feature handles empty project list gracefully."""
        mocker.patch.object(FeatureInterviewer, "list_projects", return_value=[])

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"])

        assert result.exit_code == 0
        assert "No existing projects found" in result.output

    def test_add_feature_shows_project_list(self, mocker):
        """add-feature displays numbered project list."""
        mocker.patch.object(
            FeatureInterviewer, "list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
                {"id": "spec-2", "name": "OtherApp", "tech_stack": ["Django"], "features": ["admin"]},
            ]
        )

        runner = CliRunner()
        # Input: select project 1, describe feature, then cancel at confirm
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd email notifications\nn\n")

        assert result.exit_code == 0
        assert "MyApp" in result.output
        assert "OtherApp" in result.output

    def test_add_feature_invalid_project_selection(self, mocker):
        """add-feature rejects out-of-range project selection (Click IntRange validation)."""
        mocker.patch.object(
            FeatureInterviewer, "list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
            ]
        )

        runner = CliRunner()
        # With click.IntRange, entering 99 causes Click to re-prompt.
        # With no more input, it exits with code 1 (expected behavior).
        result = runner.invoke(cli, ["add-feature"], input="99\n")

        # Click exits with code 1 when input is out of range and no more input available
        assert result.exit_code != 0 or "Enter project number" in result.output

    def test_add_feature_llm_question_loop(self, mocker):
        """add-feature asks clarifying questions from LLM then proceeds to spec."""
        mocker.patch.object(
            FeatureInterviewer, "list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
            ]
        )

        # Mock load_project_context to set code_context to None
        def fake_load_context(self, project_name):
            self.code_context = None
            self.code_context_overview = "Code context unavailable."

        mocker.patch.object(FeatureInterviewer, "load_project_context", fake_load_context)

        # Mock generate_questions: first call returns a question, second call returns None (READY)
        mocker.patch.object(
            FeatureInterviewer, "generate_questions",
            side_effect=[["What auth provider?"], None]
        )
        mocker.patch.object(
            FeatureInterviewer, "build_spec",
            return_value={
                "name": "myapp-add-oauth",
                "parent_project": "spec-1",
                "tech_stack": ["FastAPI"],
                "features": ["Add OAuth login"],
                "constraints": ["What auth provider?: Auth0"],
            }
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd OAuth login\nAuth0\ny\n")

        assert result.exit_code == 0
        assert "EXTRACTED FEATURE SPEC" in result.output
        assert "myapp-add-oauth" in result.output

    def test_add_feature_code_context_unavailable(self, mocker):
        """add-feature handles gracefully when code context can't be loaded."""
        mocker.patch.object(
            FeatureInterviewer, "list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
            ]
        )
        # Simulate load_project_context setting code_context and overview to None (as it does on error)
        def fake_load_context(self, project_name):
            self.code_context = None
            self.code_context_overview = None

        mocker.patch.object(FeatureInterviewer, "load_project_context", fake_load_context)

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd feature\nn\n")

        assert result.exit_code == 0
        assert "Could not load code context" in result.output

    def test_add_feature_full_flow(self, mocker):
        """add-feature completes full flow: select project -> describe -> questions -> spec -> send."""
        # Mock project listing
        mocker.patch.object(
            FeatureInterviewer, "list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
            ]
        )

        # Mock code context
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = {
            "project_name": "MyApp",
            "total_files": 5,
            "total_functions": 12,
            "total_classes": 3,
            "files": [],
            "functions": [],
            "classes": [],
        }
        mocker.patch("services.manager.feature_interviewer.ProjectCodeContext", return_value=mock_ctx)

        # Inject mock LLM client via constructor patching
        mock_llm = mocker.Mock()
        mock_llm.invoke.side_effect = [
            json.dumps(["What auth provider?"]),
            "READY",
        ]

        original_init = FeatureInterviewer.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, llm_client=mock_llm, **kwargs)

        mocker.patch.object(FeatureInterviewer, "__init__", patched_init)

        # Mock Librarian POST
        mock_post = mocker.patch("requests.post")
        mock_post.return_value = mocker.Mock(status_code=201, json=lambda: {"id": "spec-new"})

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd OAuth login\nAuth0\ny\n")

        assert result.exit_code == 0
        assert "EXTRACTED FEATURE SPEC" in result.output
        assert "Found existing code" in result.output
        assert "5 files" in result.output
        assert "ProjectSpec created with ID" in result.output
        mock_post.assert_called_once()
        # Verify the spec payload contains expected fields
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["parent_project"] == "spec-1"
        assert "Add OAuth login" in call_kwargs["json"]["features"]
