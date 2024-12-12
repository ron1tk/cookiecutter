import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# tests/test_cli.py

import json
import os
import sys
from collections import OrderedDict
from unittest import mock

import pytest
from click.testing import CliRunner

from cookiecutter import __version__
from cookiecutter.cli import (
    list_installed_templates,
    main,
    validate_extra_context,
    version_msg,
)
from cookiecutter.config import get_user_config
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
from cookiecutter.main import cookiecutter


@pytest.fixture
def runner():
    """Fixture for Click CliRunner."""
    return CliRunner()


def test_version_msg():
    """Test that version_msg returns the correct version string."""
    expected_location = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    msg = version_msg()
    assert msg.startswith(f"Cookiecutter {__version__} from ")
    assert f"(Python {sys.version})" in msg


@pytest.mark.parametrize(
    "extra_context,expected",
    [
        (["key=value", "foo=bar"], OrderedDict([("key", "value"), ("foo", "bar")])),
        ([], None),
        (["single=pair"], OrderedDict([("single", "pair")])),
    ],
)
def test_validate_extra_context_normal_cases(extra_context, expected):
    """Test validate_extra_context with normal input."""
    ctx = mock.MagicMock()
    param = mock.MagicMock()
    result = validate_extra_context(ctx, param, extra_context)
    assert result == expected


@pytest.mark.parametrize("invalid_context", [["keyvalue"], ["foo", "bar=baz", "invalid"]])
def test_validate_extra_context_error_cases(invalid_context):
    """Test validate_extra_context raises BadParameter on invalid input."""
    ctx = mock.MagicMock()
    param = mock.MagicMock()
    with pytest.raises(Exception) as exc_info:
        validate_extra_context(ctx, param, invalid_context)
    assert "EXTRA_CONTEXT should contain items of the form key=value" in str(exc_info.value)


@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.os.path.exists")
@mock.patch("cookiecutter.cli.os.listdir")
@mock.patch("cookiecutter.cli.get_user_config")
def test_list_installed_templates_success(
    mock_get_user_config, mock_listdir, mock_exists, mock_echo
):
    """Test list_installed_templates successfully lists templates."""
    mock_get_user_config.return_value = {"cookiecutters_dir": "/fake/dir"}
    mock_exists.side_effect = lambda path: path in [
        "/fake/dir",
        "/fake/dir/template1/cookiecutter.json",
        "/fake/dir/template2/cookiecutter.json",
    ]
    mock_listdir.return_value = ["template1", "template2", "not_a_template"]

    with pytest.raises(SystemExit) as exc:
        list_installed_templates(default_config=False, passed_config_file=None)

    assert exc.value.code is None
    mock_echo.assert_any_call("2 installed templates: ")
    mock_echo.assert_any_call(" * template1")
    mock_echo.assert_any_call(" * template2")


@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.os.path.exists")
@mock.patch("cookiecutter.cli.get_user_config")
def test_list_installed_templates_no_directory(mock_get_user_config, mock_exists, mock_echo):
    """Test list_installed_templates when cookiecutters_dir does not exist."""
    mock_get_user_config.return_value = {"cookiecutters_dir": "/non/existent/dir"}
    mock_exists.return_value = False

    with pytest.raises(SystemExit) as exc:
        list_installed_templates(default_config=False, passed_config_file=None)

    assert exc.value.code == -1
    mock_echo.assert_called_with(
        "Error: Cannot list installed templates. Folder does not exist: /non/existent/dir"
    )


def test_main_no_arguments(runner):
    """Test main command with no arguments."""
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "Usage" in result.output


@mock.patch("cookiecutter.cli.list_installed_templates")
def test_main_list_installed(mock_list_installed, runner):
    """Test main command with --list-installed option."""
    result = runner.invoke(main, ["--list-installed"])
    assert result.exit_code == 0
    mock_list_installed.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_success(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command successfully invokes cookiecutter."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--no-input", "--verbose"])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_with(stream_level="DEBUG", debug_file=None)
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_cookiecutter_exception(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command handles cookiecutter exceptions."""
    mock_cookiecutter.side_effect = OutputDirExistsException("Output directory exists")

    result = runner.invoke(main, ["template/path"])
    assert result.exit_code == 1
    assert "Output directory exists" in result.output


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_undefined_variable_exception(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command handles UndefinedVariableInTemplate exception."""
    undefined_err = UndefinedVariableInTemplate(
        message="Undefined variable",
        error=mock.Mock(message="Variable not defined"),
        context={"key": "value"},
    )
    mock_cookiecutter.side_effect = undefined_err

    result = runner.invoke(main, ["template/path"])
    assert result.exit_code == 1
    assert "Undefined variable" in result.output
    assert "Error message: Variable not defined" in result.output
    assert 'Context: {\n    "key": "value"\n}' in result.output


@mock.patch("cookiecutter.cli.list_installed_templates")
def test_main_help(runner, mock_list_installed):
    """Test main command with 'help' argument."""
    result = runner.invoke(main, ["help"])
    assert result.exit_code == 0
    assert "Usage" in result.output
    mock_list_installed.assert_not_called()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_version_option(runner, mock_cookiecutter):
    """Test main command with --version option."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert f"Cookiecutter {__version__}" in result.output
    mock_cookiecutter.assert_not_called()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_replay_option(mock_cookiecutter, runner):
    """Test main command with --replay option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--replay"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_extra_context(mock_cookiecutter, runner):
    """Test main command with extra_context."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(
        main, ["template/path", "key1=value1", "key2=value2", "--no-input"]
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["extra_context"] == OrderedDict([("key1", "value1"), ("key2", "value2")])


@mock.patch("cookiecutter.cli.List_installed_templates")
def test_main_invalid_combination_no_input_and_replay(runner):
    """Test main command with --no-input and --replay options."""
    result = runner.invoke(main, ["template/path", "--no-input", "--replay"])
    assert result.exit_code != 0
    assert "You can not use both replay and no_input or extra_context at the same time." in result.output


@mock.patch("cookiecutter.cli.os.environ.get")
@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_with_password(mock_cookiecutter, mock_env_get, runner):
    """Test main command with COOKIECUTTER_REPO_PASSWORD environment variable."""
    mock_env_get.return_value = "secret"
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["password"] == "secret"


@mock.patch("cookiecutter.cli.get_user_config")
@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_with_config_file(mock_cookiecutter, mock_get_user_config, runner):
    """Test main command with --config-file option."""
    mock_get_user_config.return_value = {"cookiecutters_dir": "/custom/dir"}
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--config-file", "config.yaml"])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_with(config_file="config.yaml", default_config=False)
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_overwrite_if_exists(mock_cookiecutter, runner):
    """Test main command with --overwrite-if-exists option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--overwrite-if-exists"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["overwrite_if_exists"] is True


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_skip_if_file_exists(mock_cookiecutter, runner):
    """Test main command with --skip-if-file-exists option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--skip-if-file-exists"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["skip_if_file_exists"] is True


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_output_dir(mock_cookiecutter, runner):
    """Test main command with --output-dir option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--output-dir", "/output/dir"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["output_dir"] == "/output/dir"


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_accept_hooks_yes(mock_cookiecutter, runner):
    """Test main command with --accept-hooks set to 'yes'."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--accept-hooks", "yes"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["accept_hooks"] is True


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.click.confirm")
def test_main_accept_hooks_ask_yes(mock_confirm, mock_cookiecutter, runner):
    """Test main command with --accept-hooks set to 'ask' and user agrees."""
    mock_confirm.return_value = True
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--accept-hooks", "ask"])
    assert result.exit_code == 0
    mock_confirm.assert_called_once_with("Do you want to execute hooks?")
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.click.confirm")
def test_main_accept_hooks_ask_no(mock_confirm, mock_cookiecutter, runner):
    """Test main command with --accept-hooks set to 'ask' and user declines."""
    mock_confirm.return_value = False
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--accept-hooks", "ask"])
    assert result.exit_code == 0
    mock_confirm.assert_called_once_with("Do you want to execute hooks?")
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_keep_project_on_failure(mock_cookiecutter, runner):
    """Test main command with --keep-project-on-failure option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--keep-project-on-failure"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["keep_project_on_failure"] is True


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_directory_option(mock_cookiecutter, runner):
    """Test main command with --directory option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--directory", "subdir"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["directory"] == "subdir"


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_debug_file_option(mock_cookiecutter, runner):
    """Test main command with --debug-file option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--debug-file", "debug.log"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["debug_file"] == "debug.log"


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_replay_file_option(mock_cookiecutter, runner):
    """Test main command with --replay-file option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--replay-file", "replay.json"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["replay"] == "replay.json"


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_checkout_option(mock_cookiecutter, runner):
    """Test main command with --checkout option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--checkout", "develop"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["checkout"] == "develop"


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_default_config_option(mock_cookiecutter, runner):
    """Test main command with --default-config option."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path", "--default-config"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["default_config"] is True


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_default_output_dir(mock_cookiecutter, runner):
    """Test main command with default output directory."""
    mock_cookiecutter.return_value = "generated_project"

    result = runner.invoke(main, ["template/path"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    _, kwargs = mock_cookiecutter.call_args
    assert kwargs["output_dir"] == "."


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_no_arguments_help_option(runner):
    """Test main command with --help option."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_invalid_accept_hooks_option(mock_cookiecutter, runner):
    """Test main command with invalid --accept-hooks option."""
    result = runner.invoke(main, ["template/path", "--accept-hooks", "invalid"])
    assert result.exit_code != 0
    assert "invalid choice" in result.output
    mock_cookiecutter.assert_not_called()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_invalid_extra_context_format(mock_cookiecutter, runner):
    """Test main command with invalid extra_context format."""
    result = runner.invoke(main, ["template/path", "invalid_format"])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output
    mock_cookiecutter.assert_not_called()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_empty_template_argument(mock_cookiecutter, runner):
    """Test main command with empty template argument."""
    result = runner.invoke(main, ["", "--no-input"])
    assert result.exit_code == 0
    assert "Usage" in result.output
    mock_cookiecutter.assert_not_called()


@mock.patch("cookiecutter.cli.cookiecutter")
def test_main_template_help_argument(mock_cookiecutter, runner):
    """Test main command with template argument as 'help'."""
    result = runner.invoke(main, ["help"])
    assert result.exit_code == 0
    assert "Usage" in result.output
    mock_cookiecutter.assert_not_called()