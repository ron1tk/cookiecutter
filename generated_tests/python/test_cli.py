import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# File: tests/test_cli.py

import json
import os
import sys
from collections import OrderedDict
from unittest import mock

import pytest
from click.testing import CliRunner

from cookiecutter import __version__
from cookiecutter.cli import main, list_installed_templates, validate_extra_context, version_msg
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


def test_version_msg():
    """Test that version_msg returns the correct version string."""
    expected_location = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_version = sys.version
    expected = f"Cookiecutter {__version__} from {expected_location} (Python {python_version})"
    with mock.patch("os.path.dirname", return_value="/mock/location"):
        with mock.patch("os.path.abspath", return_value="/mock/location/cli.py"):
            msg = version_msg()
            assert "Cookiecutter" in msg
            assert __version__ in msg
            assert "Python" in msg


def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    ctx = mock.MagicMock()
    param = mock.MagicMock()
    value = ["key1=value1", "key2=value2"]
    expected = OrderedDict([("key1", "value1"), ("key2", "value2")])
    result = validate_extra_context(ctx, param, value)
    assert result == expected


def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter for invalid input."""
    ctx = mock.MagicMock()
    param = mock.MagicMock()
    value = ["key1value1", "key2=value2"]
    with pytest.raises(mock.MockException):
        with mock.patch("click.BadParameter") as BadParameter:
            BadParameter.side_effect = mock.MockException("Invalid format")
            validate_extra_context(ctx, param, value)


@mock.patch("cookiecutter.cli.get_user_config")
@mock.patch("os.path.exists")
@mock.patch("os.listdir")
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_list_installed_templates_exists(
    mock_exit, mock_echo, mock_listdir, mock_exists, mock_get_user_config
):
    """Test list_installed_templates lists templates when directory exists."""
    mock_get_user_config.return_value = {"cookiecutters_dir": "/path/to/cookiecutters"}
    mock_exists.return_value = True
    mock_listdir.return_value = ["template1", "template2", "not_a_template"]
    with mock.patch("os.path.exists", side_effect=[True, True, False]):
        list_installed_templates(default_config=True, passed_config_file=None)
        mock_echo.assert_any_call("2 installed templates: ")
        mock_echo.assert_any_call(" * template1")
        mock_echo.assert_any_call(" * template2")
        mock_exit.assert_not_called()


@mock.patch("cookiecutter.cli.get_user_config")
@mock.patch("os.path.exists")
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_list_installed_templates_not_exists(
    mock_exit, mock_echo, mock_exists, mock_get_user_config
):
    """Test list_installed_templates exits with error when directory does not exist."""
    mock_get_user_config.return_value = {"cookiecutters_dir": "/path/to/cookiecutters"}
    mock_exists.return_value = False
    list_installed_templates(default_config=True, passed_config_file=None)
    mock_echo.assert_called_with(
        "Error: Cannot list installed templates. Folder does not exist: /path/to/cookiecutters"
    )
    mock_exit.assert_called_with(-1)


@mock.patch("cookiecutter.cli.list_installed_templates")
@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=True)
def test_main_list_installed(
    mock_confirm, mock_configure_logger, mock_cookiecutter, mock_list_installed, runner
):
    """Test main command with --list-installed flag."""
    result = runner.invoke(main, ["--list-installed"])
    assert result.exit_code == 0
    mock_list_installed.assert_called_once()


@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.click.get_current_context")
def test_main_no_arguments(mock_get_ctx, mock_echo, runner):
    """Test main command without arguments shows help and exits."""
    mock_ctx = mock.MagicMock()
    mock_get_ctx.return_value = mock_ctx
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    mock_ctx.get_help.assert_called_once()
    mock_echo.assert_called()


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=True)
def test_main_with_template_no_input(
    mock_confirm, mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with template and --no-input option."""
    result = runner.invoke(main, ["template_repo", "--no-input"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
        checkout=None,
        no_input=True,
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


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=False)
def test_main_with_extra_context(
    mock_confirm, mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with template and extra_context."""
    extra = ("key1=value1", "key2=value2")
    expected_context = OrderedDict([("key1", "value1"), ("key2", "value2")])
    result = runner.invoke(main, ["template_repo"] + list(extra))
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
        checkout=None,
        no_input=False,
        extra_context=expected_context,
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


@mock.patch("cookiecutter.cli.cookiecutter", side_effect=InvalidModeException("Invalid mode"))
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_main_invalid_mode(
    mock_exit, mock_echo, mock_cookiecutter, runner
):
    """Test main command with invalid combination of --no-input and --replay."""
    result = runner.invoke(main, ["template_repo", "--no-input", "--replay"])
    assert result.exit_code == 1
    mock_echo.assert_called_with("Invalid mode")
    mock_exit.assert_called_with(1)


@mock.patch("cookiecutter.cli.cookiecutter", side_effect=OutputDirExistsException("Output exists"))
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_main_output_dir_exists(
    mock_exit, mock_echo, mock_cookiecutter, runner
):
    """Test main command when OutputDirExistsException is raised."""
    result = runner.invoke(main, ["template_repo"])
    assert result.exit_code == 1
    mock_echo.assert_called_with("Output exists")
    mock_exit.assert_called_with(1)


@mock.patch("cookiecutter.cli.cookiecutter", side_effect=UndefinedVariableInTemplate(
    message="Undefined variable",
    error=mock.Mock(message="Template error"),
    context={"var": "value"}
))
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_main_undefined_variable(
    mock_exit, mock_echo, mock_cookiecutter, runner
):
    """Test main command when UndefinedVariableInTemplate is raised."""
    result = runner.invoke(main, ["template_repo"])
    assert result.exit_code == 1
    mock_echo.assert_any_call("Undefined variable")
    mock_echo.assert_any_call("Error message: Template error")
    mock_echo.assert_any_call('Context: {\n    "var": "value"\n}')
    mock_exit.assert_called_with(1)


@mock.patch("cookiecutter.cli.cookiecutter", side_effect=RepositoryNotFound("Repo not found"))
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_main_repository_not_found(
    mock_exit, mock_echo, mock_cookiecutter, runner
):
    """Test main command when RepositoryNotFound is raised."""
    result = runner.invoke(main, ["nonexistent_repo"])
    assert result.exit_code == 1
    mock_echo.assert_called_with("Repo not found")
    mock_exit.assert_called_with(1)


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=True)
def test_main_verbose_logging(
    mock_confirm, mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with --verbose flag."""
    result = runner.invoke(main, ["template_repo", "--verbose"])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_with(stream_level='DEBUG', debug_file=None)
    mock_cookiecutter.assert_called_once()


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=True)
def test_main_with_hooks_accept_yes(
    mock_confirm, mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with accept_hooks set to yes."""
    result = runner.invoke(main, ["template_repo", "--accept-hooks", "yes"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
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


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
@mock.patch("cookiecutter.cli.click.confirm", return_value=False)
def test_main_with_hooks_accept_no(
    mock_confirm, mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with accept_hooks set to no."""
    result = runner.invoke(main, ["template_repo", "--accept-hooks", "no"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
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


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_with_output_dir(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with --output-dir option."""
    result = runner.invoke(main, ["template_repo", "--output-dir", "/output/path"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
        checkout=None,
        no_input=False,
        extra_context={},
        replay=False,
        overwrite_if_exists=False,
        output_dir="/output/path",
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_with_overwrite(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with --overwrite-if-exists flag."""
    result = runner.invoke(main, ["template_repo", "--overwrite-if-exists"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
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


@mock.patch("cookiecutter.cli.cookiecutter")
@mock.patch("cookiecutter.cli.configure_logger")
def test_main_with_replay(
    mock_configure_logger, mock_cookiecutter, runner
):
    """Test main command with --replay flag."""
    result = runner.invoke(main, ["template_repo", "--replay"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "template_repo",
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


@mock.patch("cookiecutter.cli.cookiecutter", side_effect=Exception("General error"))
@mock.patch("cookiecutter.cli.click.echo")
@mock.patch("cookiecutter.cli.sys.exit")
def test_main_general_exception(
    mock_exit, mock_echo, mock_cookiecutter, runner
):
    """Test main command handles general exceptions."""
    result = runner.invoke(main, ["template_repo"])
    assert result.exit_code != 0
    mock_echo.assert_called_with("General error")
    mock_exit.assert_called_with(1)