import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import patch, MagicMock
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
import sys
import json
import os

@pytest.fixture
def runner():
    """Fixture for Click CLI runner."""
    return CliRunner()

@pytest.fixture
def mock_get_user_config():
    """Fixture to mock get_user_config."""
    with patch('cookiecutter.cli.get_user_config') as mock:
        yield mock

@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock cookiecutter.main.cookiecutter."""
    with patch('cookiecutter.cli.cookiecutter') as mock:
        yield mock

@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock list_installed_templates."""
    with patch('cookiecutter.cli.list_installed_templates') as mock:
        yield mock

@pytest.fixture
def mock_configure_logger():
    """Fixture to mock configure_logger."""
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
def mock_validate_extra_context():
    """Fixture to mock validate_extra_context."""
    with patch('cookiecutter.cli.validate_extra_context') as mock:
        yield mock

def test_version_msg():
    """Test that version_msg returns the correct version string."""
    expected_start = "Cookiecutter "
    version_output = version_msg()
    assert version_output.startswith(expected_start)
    assert "Python" in version_output

def test_main_no_arguments(runner, mock_cookiecutter, mock_configure_logger, mock_click_echo, mock_sys_exit):
    """Test running main without arguments displays help and exits."""
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert 'Usage' in result.output

def test_main_list_installed(runner, mock_list_installed_templates, mock_sys_exit):
    """Test the --list-installed option lists templates and exits."""
    mock_list_installed_templates.return_value = None
    result = runner.invoke(main, ['--list-installed'])
    mock_list_installed_templates.assert_called_once()
    mock_sys_exit.assert_called_with(0)
    assert result.exit_code == 0

def test_main_version_option(runner):
    """Test the --version option outputs the version message."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert version_msg() in result.output

def test_main_with_template_and_no_input(runner, mock_cookiecutter, mock_configure_logger):
    """Test main executes cookiecutter with template and --no-input."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--no-input'])
    mock_configure_logger.assert_called_once()
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=True,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_extra_context_parsing(runner, mock_cookiecutter, mock_configure_logger):
    """Test main parses extra_context correctly."""
    extra = ('key1=value1', 'key2=value2')
    result = runner.invoke(main, ['fake-template'] + list(extra))
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == {'key1': 'value1', 'key2': 'value2'}
    assert result.exit_code == 0

def test_main_invalid_extra_context(runner, mock_validate_extra_context):
    """Test main raises error on invalid extra_context format."""
    mock_validate_extra_context.side_effect = click.BadParameter("Invalid format")
    result = runner.invoke(main, ['fake-template', 'invalidcontext'])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output

@pytest.mark.parametrize("exception", [
    ContextDecodingException("Decoding failed"),
    OutputDirExistsException("Output directory exists"),
    EmptyDirNameException("Empty directory name"),
    InvalidModeException("Invalid mode"),
    FailedHookException("Hook failed"),
    UnknownExtension("Unknown extension"),
    InvalidZipRepository("Invalid zip repository"),
    RepositoryNotFound("Repository not found"),
    RepositoryCloneFailed("Clone failed"),
])
def test_main_handled_exceptions(runner, exception, mock_click_echo, mock_sys_exit, mock_cookiecutter, mock_configure_logger):
    """Test main handles known exceptions and exits with code 1."""
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(main, ['fake-template', '--no-input'])
    mock_click_echo.assert_called_with(str(exception))
    mock_sys_exit.assert_called_with(1)
    assert result.exit_code == 1

def test_main_undefined_variable_in_template(runner, mock_click_echo, mock_sys_exit, mock_cookiecutter, mock_configure_logger):
    """Test main handles UndefinedVariableInTemplate exception."""
    error = MagicMock()
    error.message = "Undefined variable error"
    undefined_exception = UndefinedVariableInTemplate("Undefined variable", error, {"key": "value"})
    mock_cookiecutter.side_effect = undefined_exception
    result = runner.invoke(main, ['fake-template'])
    expected_output = (
        f"{undefined_exception.message}\n"
        f"Error message: {error.message}\n"
        f"Context: {json.dumps(undefined_exception.context, indent=4, sort_keys=True)}"
    )
    mock_click_echo.assert_any_call(expected_output)
    mock_sys_exit.assert_called_with(1)
    assert result.exit_code == 1

def test_main_accept_hooks_ask_yes(runner, mock_cookiecutter, mock_configure_logger):
    """Test main when accept_hooks is set to 'ask' and user confirms."""
    with patch('cookiecutter.cli.click.confirm', return_value=True):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        mock_cookiecutter.assert_called_once()
        assert result.exit_code == 0

def test_main_accept_hooks_ask_no(runner, mock_cookiecutter, mock_configure_logger):
    """Test main when accept_hooks is set to 'ask' and user declines."""
    with patch('cookiecutter.cli.click.confirm', return_value=False):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        mock_cookiecutter.assert_called_once()
        assert result.exit_code == 0

def test_main_conflicting_options(runner):
    """Test main fails when --no-input and --replay are used together."""
    result = runner.invoke(main, ['fake-template', '--no-input', '--replay'])
    assert result.exit_code != 0
    assert "You can not use both replay and no_input or extra_context at the same time." in result.output

def test_main_overwrite_if_exists(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --overwrite-if-exists option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--overwrite-if-exists'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_output_dir(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --output-dir option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--output-dir', 'output/path'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
        overwrite_if_exists=False,
        output_dir='output/path',
        config_file=None,
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )
    assert result.exit_code == 0

def test_main_config_file(runner, mock_cookiecutter, mock_configure_logger, mock_get_user_config):
    """Test main with --config-file option."""
    mock_get_user_config.return_value = {}
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--config-file', 'config.yaml'])
    mock_get_user_config.assert_called_once_with(config_file='config.yaml', default_config=False)
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
        overwrite_if_exists=False,
        output_dir='.',
        config_file='config.yaml',
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )
    assert result.exit_code == 0

def test_main_default_config_true(runner, mock_cookiecutter, mock_configure_logger, mock_get_user_config):
    """Test main with --default-config option."""
    mock_get_user_config.return_value = {}
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--default-config'])
    mock_get_user_config.assert_called_once_with(config_file=None, default_config=True)
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_replay_flag(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --replay flag."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--replay'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=True,
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
    assert result.exit_code == 0

def test_main_replay_file(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --replay-file option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--replay-file', 'replay.json'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
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
    assert result.exit_code == 0

def test_main_keep_project_on_failure(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --keep-project-on-failure option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--keep-project-on-failure'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    from cookiecutter.cli import validate_extra_context
    ctx = MagicMock()
    param = MagicMock()
    value = ['key1=value1', 'key2=value2']
    result = validate_extra_context(ctx, param, value)
    assert result == {'key1': 'value1', 'key2': 'value2'}

def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter on invalid input."""
    from cookiecutter.cli import validate_extra_context
    ctx = MagicMock()
    param = MagicMock()
    value = ['invalid']
    with pytest.raises(click.BadParameter) as excinfo:
        validate_extra_context(ctx, param, value)
    assert "EXTRA_CONTEXT should contain items of the form key=value; 'invalid' doesn't match that form" in str(excinfo.value)

def test_main_verbose_flag(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --verbose flag sets logger to DEBUG."""
    mock_cookiecutter.return_value = "project_dir"
    runner.invoke(main, ['fake-template', '--verbose'])
    mock_configure_logger.assert_called_once_with(stream_level='DEBUG', debug_file=None)

def test_main_debug_file(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --debug-file option."""
    mock_cookiecutter.return_value = "project_dir"
    runner.invoke(main, ['fake-template', '--debug-file', 'debug.log'])
    mock_configure_logger.assert_called_once_with(stream_level='INFO', debug_file='debug.log')

def test_main_accept_hooks_no(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --accept-hooks set to 'no'."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--accept-hooks', 'no'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_skip_if_file_exists(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --skip-if-file-exists option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--skip-if-file-exists'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_directory_option(runner, mock_cookiecutter, mock_configure_logger):
    """Test main with --directory option."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template', '--directory', 'subdir'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_password_env(runner, mock_cookiecutter, mock_configure_logger):
    """Test main uses COOKIECUTTER_REPO_PASSWORD environment variable."""
    with patch.dict(os.environ, {"COOKIECUTTER_REPO_PASSWORD": "secret"}):
        mock_cookiecutter.return_value = "project_dir"
        result = runner.invoke(main, ['fake-template'])
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=None,
            overwrite_if_exists=False,
            output_dir='.',
            config_file=None,
            default_config=False,
            password='secret',
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )
        assert result.exit_code == 0

def test_main_output_dir_default(runner, mock_cookiecutter, mock_configure_logger):
    """Test main uses default output_dir when not specified."""
    mock_cookiecutter.return_value = "project_dir"
    result = runner.invoke(main, ['fake-template'])
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=None,
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
    assert result.exit_code == 0

def test_main_no_template_provided(runner, mock_click_echo, mock_sys_exit):
    """Test main exits with help message when no template is provided."""
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert 'Usage' in result.output
    mock_sys_exit.assert_called_with(0)

def test_main_template_help(runner, mock_click_echo, mock_sys_exit):
    """Test main exits with help message when template is 'help'."""
    result = runner.invoke(main, ['help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output
    mock_sys_exit.assert_called_with(0)