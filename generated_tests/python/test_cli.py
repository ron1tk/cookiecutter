import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# tests/test_cli.py

import json
import os
import sys
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest
import click
from click.testing import CliRunner

from cookiecutter import __version__
from cookiecutter.cli import (
    main,
    version_msg,
    validate_extra_context,
    list_installed_templates,
)
from cookiecutter.exceptions import (
    ContextDecodingException,
    EmptyDirNameException,
    FailedHookException,
    InvalidModeException,
    InvalidZipRepository,
    OutputDirExistsException,
    RepositoryCloneFailed,
    RepositoryNotFound,
    UndefinedVariableInTemplate,
    UnknownExtension,
)
from cookiecutter.log import configure_logger


@pytest.fixture
def runner():
    return CliRunner()


class TestVersionMsg:
    def test_version_msg_format(self):
        expected_start = f"Cookiecutter {__version__} from "
        msg = version_msg()
        assert msg.startswith(expected_start)
        assert "Python" in msg


class TestValidateExtraContext:
    def test_valid_extra_context(self):
        ctx = MagicMock()
        param = MagicMock()
        value = ("key1=value1", "key2=value2")
        expected = OrderedDict([("key1", "value1"), ("key2", "value2")])
        result = validate_extra_context(ctx, param, value)
        assert result == expected

    def test_empty_extra_context(self):
        ctx = MagicMock()
        param = MagicMock()
        value = ()
        result = validate_extra_context(ctx, param, value)
        assert result is None

    def test_invalid_extra_context_missing_equal(self):
        ctx = MagicMock()
        param = MagicMock()
        value = ("key1value1",)
        with pytest.raises(click.BadParameter) as exc_info:
            validate_extra_context(ctx, param, value)
        assert "EXTRA_CONTEXT should contain items of the form key=value" in str(
            exc_info.value
        )


class TestListInstalledTemplates:
    @patch("cookiecutter.cli.get_user_config")
    @patch("cookiecutter.cli.os.path.exists")
    @patch("cookiecutter.cli.os.listdir")
    @patch("cookiecutter.cli.click.echo")
    @patch("cookiecutter.cli.sys.exit")
    def test_list_installed_templates_success(
        self,
        mock_exit,
        mock_echo,
        mock_listdir,
        mock_exists,
        mock_get_user_config,
    ):
        mock_get_user_config.return_value = {"cookiecutters_dir": "/fake/dir"}
        mock_exists.side_effect = lambda path: True if path.endswith("cookiecutter.json") else path == "/fake/dir"
        mock_listdir.return_value = ["template1", "template2", "not_a_template"]
        list_installed_templates(default_config=True, passed_config_file=None)
        mock_echo.assert_any_call("2 installed templates: ")
        mock_echo.assert_any_call(" * template1")
        mock_echo.assert_any_call(" * template2")
        mock_exit.assert_not_called()

    @patch("cookiecutter.cli.get_user_config")
    @patch("cookiecutter.cli.os.path.exists")
    @patch("cookiecutter.cli.click.echo")
    @patch("cookiecutter.cli.sys.exit")
    def test_list_installed_templates_dir_not_exists(
        self, mock_exit, mock_echo, mock_exists, mock_get_user_config
    ):
        mock_get_user_config.return_value = {"cookiecutters_dir": "/fake/dir"}
        mock_exists.return_value = False
        list_installed_templates(default_config=True, passed_config_file=None)
        mock_echo.assert_called_with(
            "Error: Cannot list installed templates. Folder does not exist: /fake/dir"
        )
        mock_exit.assert_called_with(-1)


class TestMainCommand:
    @pytest.fixture
    def mock_cookiecutter(self):
        with patch("cookiecutter.cli.cookiecutter") as mock:
            yield mock

    @pytest.fixture
    def mock_get_user_config_func(self):
        with patch("cookiecutter.cli.get_user_config") as mock:
            yield mock

    @pytest.fixture
    def mock_configure_logger(self):
        with patch("cookiecutter.cli.configure_logger") as mock:
            yield mock

    @pytest.fixture
    def mock_list_installed_templates_func(self):
        with patch("cookiecutter.cli.list_installed_templates") as mock:
            yield mock

    @pytest.fixture
    def mock_sys_exit(self):
        with patch("cookiecutter.cli.sys.exit") as mock:
            yield mock

    @pytest.fixture
    def mock_click_echo(self):
        with patch("cookiecutter.cli.click.echo") as mock:
            yield mock

    def test_main_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Create a project from a Cookiecutter project template" in result.output

    def test_main_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert f"Cookiecutter {__version__}" in result.output

    def test_main_list_installed(
        self,
        runner,
        mock_list_installed_templates_func,
        mock_sys_exit,
    ):
        result = runner.invoke(main, ["--list-installed"])
        mock_list_installed_templates_func.assert_called_once()
        mock_sys_exit.assert_called_with(0)

    def test_main_no_arguments(
        self, runner, mock_click_echo, mock_sys_exit
    ):
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_click_echo.assert_called()
        mock_sys_exit.assert_called_with(0)

    def test_main_help_argument(
        self, runner, mock_click_echo, mock_sys_exit
    ):
        result = runner.invoke(main, ["help"])
        assert result.exit_code == 0
        mock_click_echo.assert_called()
        mock_sys_exit.assert_called_with(0)

    def test_main_invalid_extra_context(
        self, runner
    ):
        result = runner.invoke(
            main,
            ["template", "key_without_value"],
        )
        assert result.exit_code != 0
        assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output

    @patch("cookiecutter.cli.run_pre_prompt_hook")
    def test_main_success(
        self,
        mock_run_pre_prompt_hook,
        runner,
        mock_cookiecutter,
        mock_get_user_config_func,
        mock_configure_logger,
        mock_sys_exit,
    ):
        mock_get_user_config_func.return_value = {}
        mock_run_pre_prompt_hook.return_value = "/fake/repo_dir"
        result = runner.invoke(
            main,
            [
                "template",
                "--no-input",
                "--verbose",
                "--output-dir",
                "/output",
            ],
        )
        assert result.exit_code == 0
        mock_configure_logger.assert_called_with(stream_level="DEBUG", debug_file=None)
        mock_cookiecutter.assert_called_once()
        mock_sys_exit.assert_not_called()

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_cookiecutter_exception(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
        mock_click_echo,
        mock_sys_exit,
    ):
        mock_cookiecutter.side_effect = OutputDirExistsException("Output directory exists.")
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--no-input",
                "--output-dir",
                "/existing_output",
            ],
        )
        assert result.exit_code == 1
        assert "Output directory exists." in result.output
        mock_click_echo.assert_called()
        mock_sys_exit.assert_called_with(1)

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_undefined_variable_in_template(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
        mock_click_echo,
        mock_sys_exit,
    ):
        error = MagicMock()
        error.message = "Undefined variable error."
        undefined_error = UndefinedVariableInTemplate(
            "Undefined variable in template",
            error,
            {"variable": "value"},
        )
        mock_cookiecutter.side_effect = undefined_error
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--no-input",
            ],
        )
        assert result.exit_code == 1
        assert "Undefined variable in template" in result.output
        assert "Error message: Undefined variable error." in result.output
        assert '"variable": "value"' in result.output
        mock_click_echo.assert_called()
        mock_sys_exit.assert_called_with(1)

    def test_main_conflicting_options(
        self, runner
    ):
        result = runner.invoke(
            main,
            [
                "template",
                "--no-input",
                "--replay",
            ],
        )
        assert result.exit_code != 0
        assert "Cannot be combined with the --replay flag" in result.output

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_accept_hooks_yes(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--accept-hooks", "yes",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_accept_hooks_no(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--accept-hooks", "no",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=False,
            keep_project_on_failure=False,
        )

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_accept_hooks_ask_yes(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        with patch("cookiecutter.cli.click.confirm", return_value=True):
            mock_get_user_config_func.return_value = {}
            result = runner.invoke(
                main,
                [
                    "template",
                    "--accept-hooks", "ask",
                ],
            )
            assert result.exit_code == 0
            mock_cookiecutter.assert_called_once()

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_accept_hooks_ask_no(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        with patch("cookiecutter.cli.click.confirm", return_value=False):
            mock_get_user_config_func.return_value = {}
            result = runner.invoke(
                main,
                [
                    "template",
                    "--accept-hooks", "ask",
                ],
            )
            assert result.exit_code == 0
            mock_cookiecutter.assert_called_once()

    def test_main_overwrite_if_exists(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--overwrite-if-exists",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=True,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_skip_if_file_exists(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--skip-if-file-exists",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=True,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_extra_context(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "key1=value1",
                "key2=value2",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context=OrderedDict([("key1", "value1"), ("key2", "value2")]),
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_output_dir(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--output-dir",
                "/custom/output",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir="/custom/output",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    @patch("cookiecutter.cli.cookiecutter")
    def test_main_replay(
        self,
        mock_cookiecutter,
        runner,
        mock_get_user_config_func,
        mock_configure_logger,
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--replay",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=True,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_config_file(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {"config_key": "config_value"}
        result = runner.invoke(
            main,
            [
                "template",
                "--config-file",
                "/path/to/config.yaml",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file="/path/to/config.yaml",
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_default_config(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--default-config",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=True,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_debug_file(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--debug-file",
                "/path/to/debug.log",
            ],
        )
        assert result.exit_code == 0
        mock_configure_logger.assert_called_with(
            stream_level="INFO", debug_file="/path/to/debug.log"
        )
        mock_cookiecutter.assert_called_once()

    def test_main_password(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        with patch.dict(os.environ, {"COOKIECUTTER_REPO_PASSWORD": "secret"}):
            result = runner.invoke(
                main,
                [
                    "template",
                ],
            )
            assert result.exit_code == 0
            mock_cookiecutter.assert_called_once_with(
                "template",
                checkout=None,
                no_input=False,
                extra_context={},
                replay=False,
                overwrite_if_exists=False,
                output_dir=".",
                config_file=None,
                default_config=False,
                password="secret",
                directory=None,
                skip_if_file_exists=False,
                accept_hooks=True,
                keep_project_on_failure=False,
            )

    def test_main_directory(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--directory",
                "subdir/templates",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory="subdir/templates",
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )

    def test_main_keep_project_on_failure(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--keep-project-on-failure",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=True,
        )

    def test_main_verbose(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--verbose",
            ],
        )
        assert result.exit_code == 0
        mock_configure_logger.assert_called_with(stream_level="DEBUG", debug_file=None)
        mock_cookiecutter.assert_called_once()

    def test_main_replay_file(
        self, runner, mock_cookiecutter, mock_get_user_config_func, mock_configure_logger
    ):
        mock_get_user_config_func.return_value = {}
        result = runner.invoke(
            main,
            [
                "template",
                "--replay-file",
                "/path/to/replay.json",
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "template",
            checkout=None,
            no_input=False,
            extra_context={},
            replay="/path/to/replay.json",
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )