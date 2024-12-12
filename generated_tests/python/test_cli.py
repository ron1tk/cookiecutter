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


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_cookiecutter():
    with patch('cookiecutter.cli.cookiecutter') as mock:
        yield mock


@pytest.fixture
def mock_get_user_config():
    with patch('cookiecutter.cli.get_user_config') as mock:
        yield mock


@pytest.fixture
def mock_configure_logger():
    with patch('cookiecutter.cli.configure_logger') as mock:
        yield mock


@pytest.fixture
def mock_list_installed_templates():
    with patch('cookiecutter.cli.list_installed_templates') as mock:
        yield mock


@pytest.fixture
def mock_sys_exit():
    with patch('sys.exit') as mock:
        yield mock


@pytest.fixture
def mock_click_echo():
    with patch('cookiecutter.cli.click.echo') as mock:
        yield mock


@pytest.fixture
def mock_os_path_exists():
    with patch('cookiecutter.cli.os.path.exists') as mock:
        yield mock


@pytest.fixture
def mock_os_listdir():
    with patch('cookiecutter.cli.os.listdir') as mock:
        yield mock


@pytest.fixture
def mock_os_path_join():
    with patch('cookiecutter.cli.os.path.join', side_effect=lambda *args: '/'.join(args)) as mock:
        yield mock


@pytest.fixture
def mock_sys_version():
    with patch('cookiecutter.cli.sys.version', '3.8.5') as mock:
        yield mock


@pytest.fixture
def mock_os_path_abspath():
    with patch('cookiecutter.cli.os.path.abspath', side_effect=lambda x: f"/abs/{x}") as mock:
        yield mock


def test_version_option(runner, mock_cookiecutter, mock_sys_version, mock_os_path_abspath):
    result = runner.invoke(cli.main, ['--version'])
    location = f"/abs/{os.path.dirname(os.path.dirname(__file__))}"
    assert result.exit_code == 0
    assert f"Cookiecutter {cli.__version__} from {location} (Python {mock_sys_version})" in result.output


def test_list_installed_templates_success(runner, mock_list_installed_templates, mock_get_user_config, mock_sys_exit):
    result = runner.invoke(cli.main, ['--list-installed'])
    mock_list_installed_templates.assert_called_once()
    mock_sys_exit.assert_called_once_with(0)
    assert result.exit_code == 0


def test_list_installed_templates_folder_not_exists(runner, mock_list_installed_templates, mock_get_user_config, mock_sys_exit, mock_click_echo, mock_os_path_exists):
    mock_os_path_exists.return_value = False
    result = runner.invoke(cli.main, ['--list-installed'])
    mock_click_echo.assert_called_once()
    mock_sys_exit.assert_called_once_with(-1)
    assert result.exit_code == -1


def test_no_template_provided(runner, mock_click_echo, mock_sys_exit):
    result = runner.invoke(cli.main, [])
    assert cli.main.params['template'].required
    mock_click_echo.assert_called()
    mock_sys_exit.assert_called_once_with(0)
    assert result.exit_code == 0


def test_main_success(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    result = runner.invoke(cli.main, ['dummy-template'])
    mock_configure_logger.assert_called()
    mock_cookiecutter.assert_called_once()
    assert result.exit_code == 0


@pytest.mark.parametrize("exception", [
    ContextDecodingException("Decoding failed"),
    OutputDirExistsException("Output dir exists"),
    EmptyDirNameException("Empty dir name"),
    InvalidModeException("Invalid mode"),
    FailedHookException("Hook failed"),
    UnknownExtension("Unknown extension"),
    InvalidZipRepository("Invalid zip"),
    RepositoryNotFound("Repo not found"),
    RepositoryCloneFailed("Clone failed"),
])
def test_main_exceptions(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit, exception):
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(cli.main, ['dummy-template'])
    mock_click_echo.assert_called_with(exception)
    mock_sys_exit.assert_called_once_with(1)
    assert result.exit_code == 1


def test_undefined_variable_in_template(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    undefined_err = UndefinedVariableInTemplate("Undefined variable", MagicMock(message="Error message"), {"key": "value"})
    mock_cookiecutter.side_effect = undefined_err
    result = runner.invoke(cli.main, ['dummy-template'])
    mock_click_echo.assert_any_call('Undefined variable')
    mock_click_echo.assert_any_call('Error message: Error message')
    mock_click_echo.assert_any_call('Context: {\n    "key": "value"\n}')
    mock_sys_exit.assert_called_once_with(1)
    assert result.exit_code == 1


def test_validate_extra_context_valid():
    context = cli.validate_extra_context(None, None, ['key1=value1', 'key2=value2'])
    assert isinstance(context, OrderedDict)
    assert context['key1'] == 'value1'
    assert context['key2'] == 'value2'


def test_validate_extra_context_invalid():
    runner = CliRunner()
    result = runner.invoke(cli.main, ['dummy-template', 'invalidcontext'])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value; 'invalidcontext' doesn't match that form" in result.output


def test_overlapping_no_input_and_replay(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    result = runner.invoke(cli.main, ['dummy-template', '--no-input', '--replay'])
    assert "Usage:" in result.output
    mock_sys_exit.assert_not_called()


def test_replay_file(runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    result = runner.invoke(cli.main, ['dummy-template', '--replay-file', 'replay.json'])
    mock_cookiecutter.assert_called_once()
    assert result.exit_code == 0


def test_accept_hooks_ask_yes(monkeypatch, runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    with patch('cookiecutter.cli.click.confirm', return_value=True):
        result = runner.invoke(cli.main, ['dummy-template', '--accept-hooks', 'ask'])
        mock_cookiecutter.assert_called_once()
        assert result.exit_code == 0


def test_accept_hooks_ask_no(monkeypatch, runner, mock_cookiecutter, mock_get_user_config, mock_configure_logger, mock_click_echo, mock_sys_exit):
    with patch('cookiecutter.cli.click.confirm', return_value=False):
        result = runner.invoke(cli.main, ['dummy-template', '--accept-hooks', 'ask'])
        mock_cookiecutter.assert_called_once()
        assert result.exit_code == 0


def test_version_msg():
    expected = f"Cookiecutter {cli.__version__} from /abs/cookiecutter/cli.py (Python {sys.version})"
    assert cli.version_msg() == expected


@patch('cookiecutter.cli.cookiecutter', return_value=None)
def test_main_with_extra_context(mock_cookiecutter, runner, mock_get_user_config, mock_configure_logger):
    result = runner.invoke(cli.main, ['dummy-template', 'key=value'])
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == OrderedDict({'key': 'value'})
    assert result.exit_code == 0