import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import os
from collections import OrderedDict
from unittest.mock import patch, MagicMock

import pytest
from click.exceptions import BadParameter
from click.testing import CliRunner

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


@pytest.fixture
def runner():
    """Fixture for Click's CliRunner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Fixture to mock get_user_config."""
    with patch('cookiecutter.cli.get_user_config') as mock:
        yield mock


@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock cookiecutter.main.cookiecutter."""
    with patch('cookiecutter.cli.cookiecutter') as mock:
        yield mock


def test_version_msg():
    """Test that version_msg returns the correct version string."""
    with patch('cookiecutter.cli.__version__', '1.2.3'), \
         patch('cookiecutter.cli.sys.version', '3.8.10'), \
         patch('cookiecutter.cli.os.path.abspath', return_value='/path/to/cookiecutter/cli.py'), \
         patch('cookiecutter.cli.os.path.dirname', side_effect=lambda x: os.path.dirname(x)):
        expected = "Cookiecutter 1.2.3 from /path/to/cookiecutter (Python 3.8.10)"
        assert version_msg() == expected


def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    ctx = MagicMock()
    param = MagicMock()
    value = ['key1=value1', 'key2=value2']
    expected = OrderedDict([('key1', 'value1'), ('key2', 'value2')])
    result = validate_extra_context(ctx, param, value)
    assert result == expected


def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter for invalid input."""
    ctx = MagicMock()
    param = MagicMock()
    value = ['key1value1', 'key2=value2']
    with pytest.raises(BadParameter) as exc_info:
        validate_extra_context(ctx, param, value)
    assert "EXTRA_CONTEXT should contain items of the form key=value; 'key1value1' doesn't match that form" in str(exc_info.value)


@patch('cookiecutter.cli.click.echo')
@patch('cookiecutter.cli.os.path.exists')
@patch('cookiecutter.cli.os.listdir')
def test_list_installed_templates_success(mock_listdir, mock_exists, mock_echo):
    """Test list_installed_templates when cookiecutters_dir exists with templates."""
    mock_exists.return_value = True
    mock_listdir.return_value = ['template1', 'template2', 'not_a_template']
    with patch('cookiecutter.cli.os.path.join', side_effect=lambda a, b, c=None: f"/path/{a}/{b}"):
        with patch('cookiecutter.cli.os.path.exists', side_effect=lambda x: x.endswith('cookiecutter.json')):
            list_installed_templates(default_config=False, passed_config_file=None)
            mock_echo.assert_any_call('2 installed templates: ')
            mock_echo.assert_any_call(' * template1')
            mock_echo.assert_any_call(' * template2')


@patch('cookiecutter.cli.click.echo')
@patch('cookiecutter.cli.os.path.exists')
def test_list_installed_templates_no_dir(mock_exists, mock_echo):
    """Test list_installed_templates when cookiecutters_dir does not exist."""
    mock_exists.return_value = False
    list_installed_templates(default_config=False, passed_config_file=None)
    mock_echo.assert_called_with("Error: Cannot list installed templates. Folder does not exist: ")


def test_main_no_arguments_help_output(runner):
    """Test main command with no arguments shows help and exits."""
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert 'Usage' in result.output


@patch('cookiecutter.cli.list_installed_templates')
def test_main_list_installed(mock_list, runner):
    """Test main command with --list-installed option."""
    mock_list.return_value = None
    result = runner.invoke(main, ['--list-installed'])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_success(mock_cookiecutter, runner, mock_config):
    """Test main command with valid template and no_input."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_with_extra_context(mock_cookiecutter, runner, mock_config):
    """Test main command with extra_context provided."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', 'key1=value1', 'key2=value2'])
        assert result.exit_code == 0
        expected_context = OrderedDict([('key1', 'value1'), ('key2', 'value2')])
        mock_cookiecutter.assert_called_once_with(
            'template',
            None,
            False,
            extra_context=expected_context,
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


def test_main_version_option(runner):
    """Test main command with --version option."""
    with patch('cookiecutter.cli.version_msg', return_value='Cookiecutter 1.2.3'):
        result = runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        assert 'Cookiecutter 1.2.3' in result.output


@patch('cookiecutter.cli.cookiecutter')
def test_main_invalid_template(mock_cookiecutter, runner, mock_config):
    """Test main command with invalid template causing RepositoryNotFound."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Repository not found.")

    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}
    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['invalid-template', '--no-input'])
        assert result.exit_code == 1
        assert "Repository not found." in result.output


@patch('cookiecutter.cli.cookiecutter')
def test_main_undefined_variable_in_template(mock_cookiecutter, runner, mock_config):
    """Test main command handling UndefinedVariableInTemplate exception."""
    mock_error = MagicMock()
    mock_error.message = "Undefined variable 'var'."
    undefined_err = UndefinedVariableInTemplate(
        message="Undefined variable in template.",
        error=mock_error,
        context={'key': 'value'}
    )
    mock_cookiecutter.side_effect = undefined_err

    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}
    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--no-input'])
        assert result.exit_code == 1
        assert "Undefined variable in template." in result.output
        assert "Error message: Undefined variable 'var'." in result.output
        assert "Context: {\n    \"key\": \"value\"\n}" in result.output


@patch('cookiecutter.cli.cookiecutter')
def test_main_invalid_mode(mock_cookiecutter, runner, mock_config):
    """Test main command with invalid mode combination of --no-input and --replay."""
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--no-input', '--replay'])
        assert result.exit_code == 1
        assert "Usage: " in result.output


@patch('cookiecutter.cli.cookiecutter')
def test_main_accept_hooks_ask_yes(mock_cookiecutter, runner, mock_config):
    """Test main command with --accept-hooks set to 'ask' and user confirms."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'), \
         patch('cookiecutter.cli.click.confirm', return_value=True):
        result = runner.invoke(main, ['template', '--accept-hooks', 'ask', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_accept_hooks_ask_no(mock_cookiecutter, runner, mock_config):
    """Test main command with --accept-hooks set to 'ask' and user declines."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'), \
         patch('cookiecutter.cli.click.confirm', return_value=False):
        result = runner.invoke(main, ['template', '--accept-hooks', 'ask', '--no-input'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_overwrite_if_exists(mock_cookiecutter, runner, mock_config):
    """Test main command with --overwrite-if-exists option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
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


@patch('cookiecutter.cli.cookiecutter')
def test_main_output_dir(mock_cookiecutter, runner, mock_config):
    """Test main command with --output-dir option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--output-dir', '/custom/output'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'template',
            None,
            False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir='/custom/output',
            config_file=None,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )


@patch('cookiecutter.cli.cookiecutter')
def test_main_replay_file(mock_cookiecutter, runner, mock_config):
    """Test main command with --replay-file option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--replay-file', '/path/to/replay.json'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'template',
            None,
            False,
            extra_context=None,
            replay='/path/to/replay.json',
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


@patch('cookiecutter.cli.cookiecutter')
def test_main_keep_project_on_failure(mock_cookiecutter, runner, mock_config):
    """Test main command with --keep-project-on-failure option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
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


@patch('cookiecutter.cli.cookiecutter')
def test_main_debug_file(mock_cookiecutter, runner, mock_config):
    """Test main command with --debug-file option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger') as mock_logger:
        result = runner.invoke(main, ['template', '--debug-file', '/path/to/debug.log'])
        assert result.exit_code == 0
        mock_logger.assert_called_with(stream_level='INFO', debug_file='/path/to/debug.log')
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_default_config(mock_cookiecutter, runner, mock_config):
    """Test main command with --default-config option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {
        'cookiecutters_dir': '/cookies',
        'replay_dir': '/replay',
        'default_context': {},
        'abbreviations': {},
    }

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--default-config'])
        assert result.exit_code == 0
        mock_config.assert_called_with(config_file=None, default_config=True)
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_config_file(mock_cookiecutter, runner, mock_config):
    """Test main command with --config-file option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {
        'cookiecutters_dir': '/custom/cookies',
        'replay_dir': '/custom/replay',
        'default_context': {},
        'abbreviations': {},
    }

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--config-file', '/path/to/config.yaml'])
        assert result.exit_code == 0
        mock_config.assert_called_with(config_file='/path/to/config.yaml', default_config=False)
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_skip_if_file_exists(mock_cookiecutter, runner, mock_config):
    """Test main command with --skip-if-file-exists option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
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


@patch('cookiecutter.cli.cookiecutter')
def test_main_verbose(mock_cookiecutter, runner, mock_config):
    """Test main command with --verbose option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger') as mock_logger:
        result = runner.invoke(main, ['template', '--verbose'])
        assert result.exit_code == 0
        mock_logger.assert_called_with(stream_level='DEBUG', debug_file=None)
        mock_cookiecutter.assert_called_once()


@patch('cookiecutter.cli.cookiecutter')
def test_main_checkout_option(mock_cookiecutter, runner, mock_config):
    """Test main command with --checkout option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
        result = runner.invoke(main, ['template', '--checkout', 'develop'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'template',
            'develop',
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


@patch('cookiecutter.cli.cookiecutter')
def test_main_directory_option(mock_cookiecutter, runner, mock_config):
    """Test main command with --directory option."""
    mock_cookiecutter.return_value = '/output/project'
    mock_config.return_value = {'cookiecutters_dir': '/cookies', 'replay_dir': '/replay'}

    with patch('cookiecutter.cli.configure_logger'):
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