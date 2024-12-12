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
import click
from click.testing import CliRunner

from cookiecutter import __version__
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
from cookiecutter.config import get_user_config

@pytest.fixture
def runner():
    """Fixture for Click CLI runner."""
    return CliRunner()

@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock the cookiecutter.main.cookiecutter function."""
    with mock.patch("cookiecutter.cli.cookiecutter") as mock_func:
        yield mock_func

@pytest.fixture
def mock_get_user_config():
    """Fixture to mock the get_user_config function."""
    with mock.patch("cookiecutter.cli.get_user_config") as mock_func:
        mock_func.return_value = {
            'cookiecutters_dir': '/fake/cookiecutters',
            'replay_dir': '/fake/replay',
            'default_context': OrderedDict(),
            'abbreviations': {},
        }
        yield mock_func

@pytest.fixture
def mock_configure_logger():
    """Fixture to mock the configure_logger function."""
    with mock.patch("cookiecutter.cli.configure_logger") as mock_func:
        yield mock_func

@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock the list_installed_templates function."""
    with mock.patch("cookiecutter.cli.list_installed_templates") as mock_func:
        yield mock_func

def test_version_option(runner):
    """Test that the version option displays the correct version message."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert f"Cookiecutter {__version__}" in result.output

def test_help_option(runner):
    """Test that the help option displays the help message."""
    result = runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert "Create a project from a Cookiecutter project template" in result.output

def test_no_arguments_shows_help(runner):
    """Test that running without arguments shows the help message."""
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Create a project from a Cookiecutter project template" in result.output

def test_list_installed_templates(runner, mock_list_installed_templates):
    """Test the --list-installed option lists installed templates and exits."""
    result = runner.invoke(main, ['--list-installed'])
    mock_list_installed_templates.assert_called_once()
    assert result.exit_code == 0

def test_invalid_extra_context_format(runner):
    """Test that providing invalid extra_context format raises BadParameter."""
    result = runner.invoke(main, ['template', 'invalidcontext'])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output

def test_valid_extra_context(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that valid extra_context is passed correctly to cookiecutter."""
    result = runner.invoke(main, ['template', 'key1=value1', 'key2=value2'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == OrderedDict([('key1', 'value1'), ('key2', 'value2')])

def test_no_input_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --no-input flag is passed correctly."""
    result = runner.invoke(main, ['template', '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        True,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_replay_flag_with_no_input(runner):
    """Test that using --replay with --no-input raises InvalidModeException."""
    with mock.patch("cookiecutter.cli.cookiecutter") as mock_func:
        result = runner.invoke(main, ['template', '--replay', '--no-input'])
        assert result.exit_code != 0
        assert "You can not use both replay and no_input or extra_context" in result.output
        mock_func.assert_not_called()

def test_successful_cookiecutter_call(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test a successful run of cookiecutter."""
    mock_cookiecutter.return_value = 'output_dir'
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()

def test_cookiecutter_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that exceptions from cookiecutter are handled and exit with code 1."""
    exception = OutputDirExistsException("Output directory already exists.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Output directory already exists." in result.output

def test_undefined_variable_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of UndefinedVariableInTemplate exception."""
    template_error = mock.Mock(message="Undefined variable.")
    exception = UndefinedVariableInTemplate("A variable is undefined.", template_error, {"key": "value"})
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "A variable is undefined." in result.output
    assert "Error message: Undefined variable." in result.output
    assert 'Context: {\n    "key": "value"\n}' in result.output

def test_list_installed_with_nonexistent_directory(runner, mock_list_installed_templates, mock_get_user_config, mock_configure_logger):
    """Test --list-installed when the cookiecutters_dir does not exist."""
    with mock.patch("os.path.exists", return_value=False):
        result = runner.invoke(main, ['--list-installed'])
        assert "Error: Cannot list installed templates. Folder does not exist" in result.output
        assert result.exit_code == -1

def test_version_msg():
    """Test the version_msg function returns the correct format."""
    msg = version_msg()
    assert f"Cookiecutter {__version__}" in msg
    assert "from" in msg
    assert "Python" in msg

def test_output_dir_option(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --output-dir option is passed correctly."""
    result = runner.invoke(main, ['template', '--output-dir', '/fake/output'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='/fake/output',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_overwrite_if_exists_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --overwrite-if-exists flag is passed correctly."""
    result = runner.invoke(main, ['template', '--overwrite-if-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=True,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_skip_if_file_exists_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --skip-if-file-exists flag is passed correctly."""
    result = runner.invoke(main, ['template', '--skip-if-file-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=True,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_accept_hooks_option_yes(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --accept-hooks=yes sets accept_hooks to True."""
    result = runner.invoke(main, ['template', '--accept-hooks', 'yes'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_accept_hooks_option_no(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --accept-hooks=no sets accept_hooks to False."""
    result = runner.invoke(main, ['template', '--accept-hooks', 'no'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=False,
        keep_project_on_failure=False,
    )

def test_accept_hooks_option_ask_yes(monkeypatch, runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --accept-hooks=ask with user confirming sets accept_hooks to True."""
    monkeypatch.setattr('click.confirm', lambda _: True)
    result = runner.invoke(main, ['template', '--accept-hooks', 'ask'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_accept_hooks_option_ask_no(monkeypatch, runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --accept-hooks=ask with user denying sets accept_hooks to False."""
    monkeypatch.setattr('click.confirm', lambda _: False)
    result = runner.invoke(main, ['template', '--accept-hooks', 'ask'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=False,
        keep_project_on_failure=False,
    )

def test_replay_file_option(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --replay-file option correctly sets the replay parameter."""
    result = runner.invoke(main, ['template', '--replay-file', 'replay.json'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay='replay.json',
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_debug_file_option(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --debug-file option is passed correctly."""
    result = runner.invoke(main, ['template', '--debug-file', '/fake/debug.log'])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='INFO', debug_file='/fake/debug.log')
    mock_cookiecutter.assert_called_once()

def test_verbose_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --verbose flag sets the stream_level to DEBUG."""
    result = runner.invoke(main, ['template', '--verbose'])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='DEBUG', debug_file=None)
    mock_cookiecutter.assert_called_once()

def test_invalid_replay_combination(runner):
    """Test that invalid combination of --replay and --no-input raises error."""
    result = runner.invoke(main, ['template', '--replay', '--no-input'])
    assert result.exit_code != 0
    assert "Cannot be combined with the --replay flag" in result.output

def test_invalid_template_argument(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that an invalid template argument shows help and exits."""
    result = runner.invoke(main, ['help'])
    assert result.exit_code == 0
    assert "Usage:" in result.output

def test_directory_option(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --directory option is passed correctly."""
    result = runner.invoke(main, ['template', '--directory', 'subdir'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory='subdir',
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_config_file_option(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --config-file option is passed correctly."""
    result = runner.invoke(main, ['template', '--config-file', '/fake/config.yml'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file='/fake/config.yml',
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_default_config_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --default-config flag is passed correctly."""
    result = runner.invoke(main, ['template', '--default-config'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=True,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_keep_project_on_failure_flag(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that --keep-project-on-failure flag is passed correctly."""
    result = runner.invoke(main, ['template', '--keep-project-on-failure'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=True,
    )

def test_version_msg_format():
    """Test that version_msg includes Python version and correct path."""
    with mock.patch("sys.version", "3.8.10") as mock_version, \
         mock.patch("os.path.abspath", return_value="/fake/path/cli.py"):
        msg = version_msg()
        assert "Cookiecutter" in msg
        assert "from /fake/path" in msg
        assert "Python 3.8.10" in msg

def test_main_help_invocation(runner):
    """Test that 'help' argument shows help message."""
    result = runner.invoke(main, ['help'])
    assert result.exit_code == 0
    assert "Create a project from a Cookiecutter project template" in result.output

def test_main_help_invocation_with_template(runner):
    """Test that 'help' as a template argument shows help message."""
    result = runner.invoke(main, ['help'])
    assert result.exit_code == 0
    assert "Create a project from a Cookiecutter project template" in result.output

def test_empty_extra_context(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that empty extra_context results in None being passed."""
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'template',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )

def test_extra_context_empty_ordered_dict(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that empty extra_context converts to None."""
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] is None

def test_extra_context_with_multiple_values(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that multiple extra_context values are parsed correctly."""
    result = runner.invoke(main, ['template', 'key1=value1', 'key2=value2', 'key3=value3'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    expected_context = OrderedDict([
        ('key1', 'value1'),
        ('key2', 'value2'),
        ('key3', 'value3'),
    ])
    assert kwargs['extra_context'] == expected_context

def test_nonexistent_template_argument(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test that a nonexistent template argument still calls cookiecutter (assuming it handles it)."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Repository not found.")
    result = runner.invoke(main, ['nonexistent-template'])
    assert result.exit_code == 1
    assert "Repository not found." in result.output

def test_hook_failure_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of FailedHookException."""
    exception = FailedHookException("Hook execution failed.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Hook execution failed." in result.output

def test_invalid_zip_repository_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of InvalidZipRepository exception."""
    exception = InvalidZipRepository("Invalid zip repository.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Invalid zip repository." in result.output

def test_repository_clone_failed_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of RepositoryCloneFailed exception."""
    exception = RepositoryCloneFailed("Failed to clone repository.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Failed to clone repository." in result.output

def test_context_decoding_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of ContextDecodingException."""
    exception = ContextDecodingException("Failed to decode context.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Failed to decode context." in result.output

def test_invalid_mode_exception_handling(runner):
    """Test that InvalidModeException is raised correctly."""
    with mock.patch("cookiecutter.cli.cookiecutter") as mock_func:
        mock_func.side_effect = InvalidModeException("Invalid mode.")
        result = runner.invoke(main, ['template'])
        assert result.exit_code == 1
        assert "Invalid mode." in result.output

def test_unknown_extension_exception_handling(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger):
    """Test handling of UnknownExtension exception."""
    exception = UnknownExtension("Unknown extension.")
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['template'])
    assert result.exit_code == 1
    assert "Unknown extension." in result.output