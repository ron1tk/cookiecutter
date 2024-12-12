import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# tests/test_cli.py

import json
import os
import sys
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cookiecutter.cli import main, version_msg
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
from cookiecutter.log import logger


@pytest.fixture
def runner():
    """Fixture for Click CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock the cookiecutter.main.cookiecutter function."""
    with patch("cookiecutter.cli.cookiecutter") as mock_cc:
        yield mock_cc


@pytest.fixture
def mock_get_user_config():
    """Fixture to mock the cookiecutter.config.get_user_config function."""
    with patch("cookiecutter.cli.get_user_config") as mock_config:
        mock_config.return_value = {
            'cookiecutters_dir': '/fake/cookiecutters',
            'replay_dir': '/fake/replay',
            'default_context': {},
            'abbreviations': {},
        }
        yield mock_config


@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock the list_installed_templates function."""
    with patch("cookiecutter.cli.list_installed_templates") as mock_list:
        yield mock_list


@pytest.fixture
def mock_configure_logger():
    """Fixture to mock the configure_logger function."""
    with patch("cookiecutter.cli.configure_logger") as mock_logger:
        mock_logger.return_value = logger
        yield mock_logger


def test_version_option(runner):
    """Test that the version option displays the correct version message."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version_msg() in result.output


def test_help_option(runner):
    """Test that the help option displays the help message."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--version" in result.output


def test_list_installed_templates(runner, mock_list_installed_templates):
    """Test the --list-installed option lists installed templates."""
    result = runner.invoke(main, ["--list-installed"])
    assert result.exit_code == 0
    mock_list_installed_templates.assert_called_once()


@patch("cookiecutter.cli.sys.exit")
def test_list_installed_nonexistent_dir(
    mock_exit, runner, mock_list_installed_templates
):
    """Test listing installed templates when cookiecutters_dir does not exist."""
    mock_list_installed_templates.side_effect = None
    with patch("os.path.exists", return_value=False):
        result = runner.invoke(main, ["--list-installed"])
        assert result.exit_code == 0
        mock_list_installed_templates.assert_called_once()


def test_main_no_arguments(runner):
    """Test invoking main without arguments shows help and exits."""
    with patch("cookiecutter.cli.click.echo") as mock_echo, patch(
        "cookiecutter.cli.click.get_current_context"
    ) as mock_get_ctx, patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_ctx = MagicMock()
        mock_get_ctx.return_value = mock_ctx
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_get_ctx.return_value.get_help.assert_called_once()
        mock_echo.assert_called()
        mock_exit.assert_called_with(0)


def test_main_help_argument(runner):
    """Test invoking main with 'help' as template shows help and exits."""
    with patch("cookiecutter.cli.click.echo") as mock_echo, patch(
        "cookiecutter.cli.click.get_current_context"
    ) as mock_get_ctx, patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_ctx = MagicMock()
        mock_get_ctx.return_value = mock_ctx
        result = runner.invoke(main, ["help"])
        assert result.exit_code == 0
        mock_ctx.get_help.assert_called_once()
        mock_echo.assert_called()
        mock_exit.assert_called_with(0)


@patch("cookiecutter.cli.cookiecutter")
def test_main_success(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test successful invocation of cookiecutter with required arguments."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--no-input"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
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


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_extra_context(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with extra context parameters."""
    extra = ["key1=value1", "key2=value2"]
    result = runner.invoke(main, ["https://github.com/user/repo.git"] + extra)
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs["extra_context"] == {"key1": "value1", "key2": "value2"}


def test_validate_extra_context_invalid_format(runner):
    """Test that invalid extra_context format raises BadParameter."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "invalidcontext"])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_overwrite_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with overwrite-if-exists option."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--overwrite-if-exists"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
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


@patch("cookiecutter.cli.cookiecutter", side_effect=InvalidModeException("Invalid mode"))
def test_main_conflicting_options(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test that conflicting options --no-input and --replay raise an error."""
    result = runner.invoke(
        main, ["https://github.com/user/repo.git", "--no-input", "--replay"]
    )
    assert result.exit_code != 0
    assert "Invalid mode" in result.output


@patch("cookiecutter.cli.cookiecutter", side_effect=ContextDecodingException("JSON decode error"))
def test_main_context_decoding_exception(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test handling of ContextDecodingException."""
    result = runner.invoke(main, ["https://github.com/user/repo.git"])
    assert result.exit_code == 1
    assert "JSON decode error" in result.output


@patch("cookiecutter.cli.cookiecutter", side_effect=OutputDirExistsException("Output dir exists"))
def test_main_output_dir_exists_exception(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test handling of OutputDirExistsException."""
    result = runner.invoke(main, ["https://github.com/user/repo.git"])
    assert result.exit_code == 1
    assert "Output dir exists" in result.output


@patch("cookiecutter.cli.cookiecutter", side_effect=UndefinedVariableInTemplate(
    message="Undefined variable",
    error=MagicMock(message="Variable error"),
    context={"var": "value"}
))
def test_main_undefined_variable_in_template(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test handling of UndefinedVariableInTemplate exception."""
    result = runner.invoke(main, ["https://github.com/user/repo.git"])
    assert result.exit_code == 1
    assert "Undefined variable" in result.output
    assert "Variable error" in result.output
    assert '"var": "value"' in result.output


@patch("cookiecutter.cli.cookiecutter", side_effect=RepositoryNotFound("Repo not found"))
def test_main_repository_not_found_exception(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test handling of RepositoryNotFound exception."""
    result = runner.invoke(main, ["https://github.com/user/nonexistent.git"])
    assert result.exit_code == 1
    assert "Repo not found" in result.output


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_verbose_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with verbose option enables DEBUG logging."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--verbose"])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='DEBUG', debug_file=None)
    mock_cookiecutter.assert_called_once()


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_config_file(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with a custom configuration file."""
    custom_config = "/path/to/custom_config.yml"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--config-file", custom_config])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_once_with(config_file=custom_config, default_config=False)
    mock_cookiecutter.assert_called_once()


def test_version_msg():
    """Test the version message format."""
    expected_prefix = "Cookiecutter"
    version_output = version_msg()
    assert version_output.startswith(expected_prefix)
    assert "from" in version_output
    assert "Python" in version_output


@patch("cookiecutter.cli.sys.exit")
def test_list_installed_exit_code(mock_exit, runner, mock_list_installed_templates):
    """Test that list-installed exits with code 0."""
    runner.invoke(main, ["--list-installed"])
    mock_exit.assert_not_called()


@patch("cookiecutter.cli.cookiecutter", side_effect=Exception("General Error"))
@patch("cookiecutter.cli.sys.exit")
def test_main_general_exception(
    mock_exit, mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test handling of a general exception."""
    result = runner.invoke(main, ["https://github.com/user/repo.git"])
    assert result.exit_code == 1
    assert "General Error" in result.output


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_replay_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with replay option."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--replay"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
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


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_replay_file_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with a specific replay file."""
    replay_file = "/path/to/replay.json"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--replay-file", replay_file])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=replay_file,
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
def test_main_with_directory_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with directory option."""
    directory = "templates"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--directory", directory])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir=".",
        config_file=None,
        default_config=False,
        password=None,
        directory=directory,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_skip_if_file_exists_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with skip-if-file-exists option."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--skip-if-file-exists"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
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
def test_main_with_accept_hooks_no(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with accept-hooks set to 'no'."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--accept-hooks", "no"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
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
def test_main_with_keep_project_on_failure_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with keep-project-on-failure option."""
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--keep-project-on-failure"])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
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


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_debug_file_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with debug-file option."""
    debug_file = "/path/to/debug.log"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--debug-file", debug_file])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='INFO', debug_file=debug_file)
    mock_cookiecutter.assert_called_once()


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_output_dir_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with output-dir option."""
    output_dir = "/output/directory"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--output-dir", output_dir])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir=output_dir,
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_version_msg_content():
    """Test that version_msg contains expected information."""
    msg = version_msg()
    assert "Cookiecutter" in msg
    assert "from" in msg
    assert "Python" in msg


@patch("cookiecutter.cli.list_installed_templates")
def test_main_with_default_config(
    mock_list_installed_templates, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with --default-config option."""
    result = runner.invoke(main, ["--list-installed", "--default-config"])
    assert result.exit_code == 0
    mock_list_installed_templates.assert_called_once_with(
        True, None
    )


@patch("cookiecutter.cli.cookiecutter")
def test_main_with_abbreviations(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test that abbreviations are loaded from config and used."""
    with patch("cookiecutter.cli.get_user_config") as mock_config:
        mock_config.return_value = {
            'cookiecutters_dir': '/fake/cookiecutters',
            'replay_dir': '/fake/replay',
            'default_context': {},
            'abbreviations': {'gh': 'https://github.com/{0}.git'},
        }
        result = runner.invoke(main, ["gh:user/repo"])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            "https://github.com/user/repo.git",
            checkout=None,
            no_input=False,
            extra_context=None,
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
def test_main_with_checkout_option(
    mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger
):
    """Test invocation with checkout option."""
    checkout = "develop"
    result = runner.invoke(main, ["https://github.com/user/repo.git", "--checkout", checkout])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        "https://github.com/user/repo.git",
        checkout=checkout,
        no_input=False,
        extra_context=None,
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