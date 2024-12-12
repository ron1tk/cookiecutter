import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import os
import sys
from unittest import mock

import pytest
from click.testing import CliRunner

from cookiecutter import cli
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
    """Fixture to mock the main cookiecutter function."""
    with mock.patch('cookiecutter.cli.cookiecutter') as mock_func:
        yield mock_func


@pytest.fixture
def mock_get_user_config():
    """Fixture to mock get_user_config."""
    with mock.patch('cookiecutter.cli.get_user_config') as mock_func:
        mock_func.return_value = {
            'cookiecutters_dir': '/path/to/cookiecutters',
            'replay_dir': '/path/to/replay',
            'default_context': {},
            'abbreviations': {},
        }
        yield mock_func


@pytest.fixture
def mock_listdir():
    """Fixture to mock os.listdir."""
    with mock.patch('cookiecutter.cli.os.listdir') as mock_func:
        mock_func.return_value = ['template1', 'template2']
        yield mock_func


@pytest.fixture
def mock_isdir():
    """Fixture to mock os.path.isdir."""
    with mock.patch('cookiecutter.cli.os.path.isdir') as mock_func:
        mock_func.return_value = True
        yield mock_func


@pytest.fixture
def mock_os_exit():
    """Fixture to mock sys.exit."""
    with mock.patch('cookiecutter.cli.sys.exit') as mock_func:
        yield mock_func


def test_version_option(runner):
    """Test the version option displays the correct version message."""
    result = runner.invoke(cli.main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output


def test_list_installed_templates_success(
    runner, mock_get_user_config, mock_listdir, mock_isdir, mock_os_exit
):
    """Test listing installed templates when cookiecutters_dir exists."""
    result = runner.invoke(cli.main, ['--list-installed'])
    assert result.exit_code == 0
    assert "2 installed templates:" in result.output
    assert " * template1" in result.output
    assert " * template2" in result.output
    mock_os_exit.assert_called_once_with(0)


def test_list_installed_templates_no_dir(
    runner, mock_get_user_config, mock_isdir, mock_os_exit
):
    """Test listing installed templates when cookiecutters_dir does not exist."""
    mock_isdir.return_value = False
    result = runner.invoke(cli.main, ['--list-installed'])
    assert result.exit_code == 0
    assert "Error: Cannot list installed templates. Folder does not exist" in result.output
    mock_os_exit.assert_called_once_with(-1)


@pytest.mark.parametrize(
    "template,args",
    [
        ("tests/fake-repo-tmpl", ["tests/fake-repo-tmpl", "--no-input"]),
        ("https://github.com/user/repo.git", ["https://github.com/user/repo.git"]),
    ],
)
def test_main_success(runner, mock_cookiecutter, mock_get_user_config, template, args):
    """Test main command executes successfully with valid template and options."""
    result = runner.invoke(cli.main, args)
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['template'] == template
    assert call_args['no_input'] is True if "--no-input" in args else False


def test_main_with_extra_context(runner, mock_cookiecutter, mock_get_user_config):
    """Test main command with valid extra_context."""
    extra_context = ['key1=value1', 'key2=value2']
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl'] + extra_context)
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['extra_context'] == {'key1': 'value1', 'key2': 'value2'}


def test_main_with_invalid_extra_context(runner):
    """Test main command with invalid extra_context format."""
    extra_context = ['key1value1', 'key2=value2']
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl'] + extra_context)
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output


def test_main_conflicting_options(runner):
    """Test main command with conflicting --no-input and --replay options."""
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--no-input', '--replay'])
    assert result.exit_code != 0
    assert "You can not use both replay and no_input or extra_context" in result.output


def test_main_no_template(runner):
    """Test main command without providing a template."""
    result = runner.invoke(cli.main, [])
    assert result.exit_code != 0
    assert "Usage" in result.output


def test_main_help_argument(runner):
    """Test main command with 'help' as template argument."""
    result = runner.invoke(cli.main, ['help'])
    assert result.exit_code != 0
    assert "Usage" in result.output


@pytest.mark.parametrize(
    "exception",
    [
        ContextDecodingException("JSON Decode Error"),
        OutputDirExistsException("Output directory exists"),
        EmptyDirNameException("Empty directory name"),
        InvalidModeException("Invalid mode"),
        FailedHookException("Hook failed"),
        UnknownExtension("Unknown extension"),
        InvalidZipRepository("Invalid zip repository"),
        RepositoryNotFound("Repository not found"),
        RepositoryCloneFailed("Clone failed"),
    ],
)
def test_main_handling_exceptions(
    runner, mock_cookiecutter, mock_get_user_config, mock_os_exit, exception
):
    """Test main command handles various exceptions properly."""
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--no-input'])
    assert result.exit_code == 1
    assert str(exception) in result.output
    mock_os_exit.assert_called_once_with(1)


def test_main_undefined_variable_exception(
    runner, mock_cookiecutter, mock_get_user_config, mock_os_exit
):
    """Test main command handles UndefinedVariableInTemplate exception."""
    undefined_error = UndefinedVariableInTemplate(
        message="Undefined variable",
        error=mock.Mock(message="Template error message"),
        context={"key": "value"},
    )
    mock_cookiecutter.side_effect = undefined_error
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--no-input'])
    assert result.exit_code == 1
    assert "Undefined variable" in result.output
    assert "Error message: Template error message" in result.output
    assert 'Context: {\n    "key": "value"\n}' in result.output
    mock_os_exit.assert_called_once_with(1)


def test_main_verbose_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --verbose option sets the correct log level."""
    with mock.patch('cookiecutter.cli.configure_logger') as mock_logger:
        result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--verbose', '--no-input'])
        assert result.exit_code == 0
        mock_logger.assert_called_with(stream_level='DEBUG', debug_file=None)


def test_main_replay_file_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --replay-file option."""
    replay_file = 'replay.json'
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--replay-file', replay_file])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['replay'] == replay_file


def test_main_overwrite_if_exists_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --overwrite-if-exists option."""
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--overwrite-if-exists', '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['overwrite_if_exists'] is True


def test_main_skip_if_file_exists_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --skip-if-file-exists option."""
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--skip-if-file-exists', '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['skip_if_file_exists'] is True


def test_main_output_dir_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --output-dir option."""
    output_dir = '/output/dir'
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--output-dir', output_dir, '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['output_dir'] == output_dir


def test_main_config_file_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --config-file option."""
    config_file = '/path/to/config.yml'
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--config-file', config_file, '--no-input'])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_with(config_file=config_file, default_config=False)
    mock_cookiecutter.assert_called_once()


def test_main_default_config_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --default-config option."""
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--default-config', '--no-input'])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_with(config_file=None, default_config=True)
    mock_cookiecutter.assert_called_once()


def test_main_debug_file_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --debug-file option."""
    debug_file = '/path/to/debug.log'
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--debug-file', debug_file, '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['debug_file'] == debug_file


def test_main_accept_hooks_option_yes(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --accept-hooks set to 'yes'."""
    with mock.patch('cookiecutter.cli.click.confirm') as mock_confirm:
        result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--accept-hooks', 'yes', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()
        call_args = mock_cookiecutter.call_args[1]
        assert call_args['accept_hooks'] is True


def test_main_accept_hooks_option_no(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --accept-hooks set to 'no'."""
    with mock.patch('cookiecutter.cli.click.confirm') as mock_confirm:
        result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--accept-hooks', 'no', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()
        call_args = mock_cookiecutter.call_args[1]
        assert call_args['accept_hooks'] is False


def test_main_accept_hooks_option_ask_yes(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --accept-hooks set to 'ask' and user confirms."""
    with mock.patch('cookiecutter.cli.click.confirm', return_value=True):
        result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--accept-hooks', 'ask', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()
        call_args = mock_cookiecutter.call_args[1]
        assert call_args['accept_hooks'] is True


def test_main_accept_hooks_option_ask_no(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --accept-hooks set to 'ask' and user declines."""
    with mock.patch('cookiecutter.cli.click.confirm', return_value=False):
        result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--accept-hooks', 'ask', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()
        call_args = mock_cookiecutter.call_args[1]
        assert call_args['accept_hooks'] is False


def test_main_keep_project_on_failure_option(
    runner, mock_cookiecutter, mock_get_user_config, mock_os_exit
):
    """Test main command with --keep-project-on-failure option."""
    mock_cookiecutter.side_effect = FailedHookException("Hook failed")
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--keep-project-on-failure', '--no-input'])
    assert result.exit_code == 1
    assert "Hook failed" in result.output
    mock_os_exit.assert_called_once_with(1)


def test_main_directory_option(
    runner, mock_cookiecutter, mock_get_user_config
):
    """Test main command with --directory option."""
    directory = 'subdir/templates'
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--directory', directory, '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    call_args = mock_cookiecutter.call_args[1]
    assert call_args['directory'] == directory


def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    ctx = mock.Mock()
    param = mock.Mock()
    value = ['key1=value1', 'key2=value2']
    result = cli.validate_extra_context(ctx, param, value)
    assert result == {'key1': 'value1', 'key2': 'value2'}


def test_validate_extra_context_invalid():
    """Test validate_extra_context with an invalid key=value pair."""
    ctx = mock.Mock()
    param = mock.Mock()
    value = ['key1value1', 'key2=value2']
    with pytest.raises(click.BadParameter) as exc_info:
        cli.validate_extra_context(ctx, param, value)
    assert "EXTRA_CONTEXT should contain items of the form key=value" in str(exc_info.value)


def test_version_msg():
    """Test the version message format."""
    expected_substring = "Cookiecutter"
    version_output = cli.version_msg()
    assert expected_substring in version_output
    assert "Python" in version_output


def test_main_help_option(runner):
    """Test the help option displays the help message."""
    result = runner.invoke(cli.main, ['--help'])
    assert result.exit_code == 0
    assert "Create a project from a Cookiecutter project template" in result.output


def test_list_installed_empty_templates(
    runner, mock_get_user_config, mock_listdir, mock_isdir, mock_os_exit
):
    """Test listing installed templates when no templates are present."""
    mock_listdir.return_value = []
    result = runner.invoke(cli.main, ['--list-installed'])
    assert result.exit_code == 0
    assert "0 installed templates:" in result.output
    mock_os_exit.assert_called_once_with(0)


def test_main_unknown_accept_hooks_option(runner):
    """Test main command with an unknown value for --accept-hooks."""
    result = runner.invoke(cli.main, ['tests/fake-repo-tmpl', '--accept-hooks', 'maybe', '--no-input'])
    assert result.exit_code != 0
    assert "invalid choice: maybe" in result.output