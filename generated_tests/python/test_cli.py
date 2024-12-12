import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import os
import sys
from collections import OrderedDict
from unittest.mock import Mock, patch

import pytest
import click
from click.testing import CliRunner

from cookiecutter.cli import main
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
    """Fixture for Click's CliRunner."""
    return CliRunner()


@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock the cookiecutter.main.cookiecutter function."""
    with patch('cookiecutter.cli.cookiecutter') as mock:
        yield mock


@pytest.fixture
def mock_get_user_config():
    """Fixture to mock the get_user_config function."""
    with patch('cookiecutter.cli.get_user_config') as mock:
        mock.return_value = {
            'cookiecutters_dir': '/fake/cookiecutters',
            'replay_dir': '/fake/replay',
            'default_context': OrderedDict(),
            'abbreviations': {},
        }
        yield mock


@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock the list_installed_templates function."""
    with patch('cookiecutter.cli.list_installed_templates') as mock:
        yield mock


@pytest.fixture
def mock_configure_logger():
    """Fixture to mock the configure_logger function."""
    with patch('cookiecutter.cli.configure_logger') as mock:
        yield mock


@pytest.fixture
def mock_sys_exit():
    """Fixture to mock sys.exit."""
    with patch('cookiecutter.cli.sys.exit') as mock:
        yield mock


@pytest.fixture
def mock_click_echo():
    """Fixture to mock click.echo."""
    with patch('cookiecutter.cli.click.echo') as mock:
        yield mock


@pytest.fixture
def mock_os_path_exists():
    """Fixture to mock os.path.exists."""
    with patch('cookiecutter.cli.os.path.exists') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_os_listdir():
    """Fixture to mock os.listdir."""
    with patch('cookiecutter.cli.os.listdir') as mock:
        mock.return_value = ['template1', 'template2']
        yield mock


@pytest.fixture
def mock_os_path_join():
    """Fixture to mock os.path.join."""
    with patch('cookiecutter.cli.os.path.join', side_effect=lambda a, b, c=None: f"{a}/{b}"):
        yield


@pytest.fixture
def mock_os_path_dirname():
    """Fixture to mock os.path.dirname."""
    with patch('cookiecutter.cli.os.path.dirname', side_effect=lambda x: '/fake'):
        yield


@pytest.fixture
def mock_os_path_abspath():
    """Fixture to mock os.path.abspath."""
    with patch('cookiecutter.cli.os.path.abspath', side_effect=lambda x: f"/abs/{x}"):
        yield


@pytest.fixture
def mock_sys_version():
    """Fixture to mock sys.version."""
    with patch('cookiecutter.cli.sys.version', '3.8.10'):
        yield


def test_main_version_option(runner, mock_sys_exit, mock_click_echo):
    """Test the version option displays the correct version information."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output
    mock_sys_exit.assert_not_called()


def test_main_list_installed_templates(
    runner,
    mock_get_user_config,
    mock_os_path_exists,
    mock_os_listdir,
    mock_click_echo,
    mock_sys_exit,
    mock_list_installed_templates,
):
    """Test listing installed templates when the --list-installed flag is used."""
    result = runner.invoke(main, ['--list-installed'])
    assert result.exit_code == 0
    mock_list_installed_templates.assert_called_once_with(False, None)


def test_main_no_template_provided(runner, mock_click_echo, mock_sys_exit):
    """Test behavior when no template argument is provided."""
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    mock_sys_exit.assert_called_once_with(0)


def test_main_help_command(runner, mock_sys_exit):
    """Test displaying help when 'help' is passed as the template."""
    result = runner.invoke(main, ['help'])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    mock_sys_exit.assert_called_once_with(0)


def test_main_successful_invocation(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test a successful invocation of the main command with required arguments."""
    result = runner.invoke(main, ['fake-template'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        'yes',
        None,
        False,
    )


def test_main_with_extra_context(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test passing extra context via command-line arguments."""
    extra = ['key1=value1', 'key2=value2']
    result = runner.invoke(main, ['fake-template'] + extra)
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    called_args = mock_cookiecutter.call_args[1]
    assert called_args['extra_context'] == OrderedDict([('key1', 'value1'), ('key2', 'value2')])


def test_main_invalid_extra_context(
    runner,
):
    """Test handling of invalid extra_context format."""
    result = runner.invoke(main, ['fake-template', 'invalidcontext'])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output


def test_main_conflicting_options_no_input_and_replay(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that using --no-input and --replay together raises an error."""
    result = runner.invoke(main, ['fake-template', '--no-input', '--replay'])
    assert result.exit_code != 0
    assert "InvalidModeException" in result.output


@patch('cookiecutter.cli.cookiecutter', side_effect=ContextDecodingException("Failed to decode context"))
def test_main_context_decoding_exception(
    mock_cookiecutter_exception,
    runner,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test handling of ContextDecodingException during cookiecutter execution."""
    result = runner.invoke(main, ['fake-template'])
    assert result.exit_code == 1
    assert "Failed to decode context" in result.output
    mock_sys_exit.assert_called_once_with(1)


@patch('cookiecutter.cli.cookiecutter', side_effect=OutputDirExistsException("Output directory exists"))
def test_main_output_dir_exists_exception(
    mock_cookiecutter_exception,
    runner,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test handling of OutputDirExistsException during cookiecutter execution."""
    result = runner.invoke(main, ['fake-template', '--overwrite-if-exists'])
    assert result.exit_code == 1
    assert "Output directory exists" in result.output
    mock_sys_exit.assert_called_once_with(1)


@patch('cookiecutter.cli.cookiecutter', side_effect=UndefinedVariableInTemplate(
    message="Undefined variable", error=Mock(message="Variable x not defined"), context={'var': 'x'}
))
def test_main_undefined_variable_in_template_exception(
    mock_cookiecutter_exception,
    runner,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test handling of UndefinedVariableInTemplate during cookiecutter execution."""
    result = runner.invoke(main, ['fake-template'])
    assert result.exit_code == 1
    assert "Undefined variable" in result.output
    assert "Variable x not defined" in result.output
    assert '"var": "x"' in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_validate_extra_context_success():
    """Test validate_extra_context callback with valid key=value pairs."""
    from cookiecutter.cli import validate_extra_context
    ctx = Mock()
    param = Mock()
    value = ['key1=value1', 'key2=value2']
    result = validate_extra_context(ctx, param, value)
    assert isinstance(result, OrderedDict)
    assert result == OrderedDict([('key1', 'value1'), ('key2', 'value2')])


def test_validate_extra_context_invalid_format():
    """Test validate_extra_context callback with invalid key=value pair."""
    from cookiecutter.cli import validate_extra_context
    ctx = Mock()
    param = Mock()
    value = ['invalidcontext']
    with pytest.raises(click.BadParameter) as exc_info:
        validate_extra_context(ctx, param, value)
    assert "EXTRA_CONTEXT should contain items of the form key=value" in str(exc_info.value)


def test_version_msg():
    """Test the version_msg function returns the correct format."""
    from cookiecutter.cli import version_msg
    with patch('cookiecutter.cli.__version__', '1.2.3'), \
         patch('cookiecutter.cli.os.path.abspath', return_value='/path/to/cli.py'), \
         patch('cookiecutter.cli.sys.version', '3.8.10'):
        msg = version_msg()
        assert "Cookiecutter 1.2.3 from /path/to (Python 3.8.10)" == msg


def test_main_with_verbose_logging(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that verbose flag sets the logger to DEBUG level."""
    result = runner.invoke(main, ['fake-template', '--verbose'])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='DEBUG', debug_file=None)


def test_main_with_debug_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that debug_file option is passed correctly to the logger."""
    result = runner.invoke(main, ['fake-template', '--debug-file', 'debug.log'])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(stream_level='INFO', debug_file='debug.log')


def test_main_with_accept_hooks_yes(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that accept_hooks='yes' is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--accept-hooks', 'yes'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        True,
        None,
        False,
    )


def test_main_with_accept_hooks_no(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that accept_hooks='no' is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--accept-hooks', 'no'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        False,
        None,
        False,
    )


def test_main_with_accept_hooks_ask_yes(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that accept_hooks='ask' and user confirms is handled correctly."""
    with patch('cookiecutter.cli.click.confirm', return_value=True):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            None,
            False,
            {},
            None,
            False,
            '.',
            None,
            False,
            None,
            None,
            None,
            False,
            True,
            None,
            False,
        )


def test_main_with_accept_hooks_ask_no(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that accept_hooks='ask' and user declines is handled correctly."""
    with patch('cookiecutter.cli.click.confirm', return_value=False):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            None,
            False,
            {},
            None,
            False,
            '.',
            None,
            False,
            None,
            None,
            None,
            False,
            False,
            None,
            False,
        )


def test_main_with_overwrite_if_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that overwrite_if_exists flag is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--overwrite-if-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        True,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        True,
        None,
        False,
    )


def test_main_with_output_dir(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that output_dir option is passed correctly."""
    result = runner.invoke(main, ['fake-template', '--output-dir', '/output/path'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '/output/path',
        None,
        False,
        None,
        None,
        None,
        False,
        True,
        None,
        False,
    )


def test_main_with_checkout(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that checkout option is passed correctly."""
    result = runner.invoke(main, ['fake-template', '--checkout', 'develop'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        'develop',
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        True,
        None,
        False,
    )


def test_main_with_replay_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that replay_file option is passed correctly."""
    result = runner.invoke(main, ['fake-template', '--replay-file', 'replay.json'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        'replay.json',
        False,
        '.',
        None,
        False,
        'replay.json',
        None,
        None,
        False,
        True,
        'replay.json',
        False,
    )


def test_main_with_default_config(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that default_config flag is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--default-config'])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_once_with(None, True)
    mock_cookiecutter.assert_called_once()


def test_main_with_config_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that config_file option is passed correctly."""
    result = runner.invoke(main, ['fake-template', '--config-file', '/path/to/config.yml'])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_once_with('/path/to/config.yml', False)
    mock_cookiecutter.assert_called_once()


def test_main_with_skip_if_file_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that skip_if_file_exists flag is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--skip-if-file-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        True,
        True,
        None,
        False,
    )


def test_main_with_keep_project_on_failure(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that keep_project_on_failure flag is handled correctly."""
    result = runner.invoke(main, ['fake-template', '--keep-project-on-failure'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        True,
        None,
        True,
    )


def test_main_with_directory_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test that directory option is passed correctly."""
    result = runner.invoke(main, ['fake-template', '--directory', 'subdir'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        None,
        False,
        '.',
        None,
        False,
        'subdir',
        None,
        None,
        False,
        True,
        None,
        False,
    )


def test_main_repository_not_found_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of RepositoryNotFound exception during cookiecutter execution."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Repository not found")
    result = runner.invoke(main, ['nonexistent-template'])
    assert result.exit_code == 1
    assert "Repository not found" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_invalid_zip_repository_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of InvalidZipRepository exception during cookiecutter execution."""
    mock_cookiecutter.side_effect = InvalidZipRepository("Invalid zip archive")
    result = runner.invoke(main, ['invalid-zip-template'])
    assert result.exit_code == 1
    assert "Invalid zip archive" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_failed_hook_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of FailedHookException during cookiecutter execution."""
    mock_cookiecutter.side_effect = FailedHookException("Hook failed")
    result = runner.invoke(main, ['template-with-failed-hook'])
    assert result.exit_code == 1
    assert "Hook failed" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_unknown_extension_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of UnknownExtension exception during cookiecutter execution."""
    mock_cookiecutter.side_effect = UnknownExtension("Unknown extension")
    result = runner.invoke(main, ['template-with-unknown-extension'])
    assert result.exit_code == 1
    assert "Unknown extension" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_empty_dir_name_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of EmptyDirNameException during cookiecutter execution."""
    mock_cookiecutter.side_effect = EmptyDirNameException("Empty directory name")
    result = runner.invoke(main, ['template-with-empty-dir'])
    assert result.exit_code == 1
    assert "Empty directory name" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_invalid_mode_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of InvalidModeException during cookiecutter execution."""
    mock_cookiecutter.side_effect = InvalidModeException("Invalid mode")
    result = runner.invoke(main, ['invalid-mode-template'])
    assert result.exit_code == 1
    assert "Invalid mode" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_repository_clone_failed_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_echo,
    mock_sys_exit,
):
    """Test handling of RepositoryCloneFailed exception during cookiecutter execution."""
    mock_cookiecutter.side_effect = RepositoryCloneFailed("Clone failed")
    result = runner.invoke(main, ['template-clone-failed'])
    assert result.exit_code == 1
    assert "Clone failed" in result.output
    mock_sys_exit.assert_called_once_with(1)