import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# test_cli.py

import json
import os
import sys
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cookiecutter.cli import main, validate_extra_context
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
    """Fixture for Click CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock the main cookiecutter function."""
    with patch("cookiecutter.cli.cookiecutter") as mock:
        yield mock


@pytest.fixture
def mock_get_user_config():
    """Fixture to mock get_user_config."""
    with patch("cookiecutter.cli.get_user_config", return_value={
        'cookiecutters_dir': '/fake/cookiecutters',
    }) as mock:
        yield mock


@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock list_installed_templates."""
    with patch("cookiecutter.cli.list_installed_templates") as mock:
        yield mock


def test_version_option(runner):
    """Test that the version option displays the correct version message."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output
    assert "Python" in result.output


def test_list_installed_templates(runner, mock_list_installed_templates):
    """Test listing installed templates with --list-installed option."""
    mock_list_installed_templates.return_value = None
    result = runner.invoke(main, ['--list-installed'])
    assert result.exit_code == 0
    mock_list_installed_templates.assert_called_once()


def test_main_no_arguments_shows_help(runner):
    """Test that running main without arguments shows help and exits."""
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Options:" in result.output


def test_main_with_template_no_input(runner, mock_cookiecutter):
    """Test running main with a template and --no-input option."""
    result = runner.invoke(main, ['fake-template', '--no-input'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=True,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_extra_context(runner, mock_cookiecutter):
    """Test running main with extra_context key=value pairs."""
    extra = ['key1=value1', 'key2=value2']
    result = runner.invoke(main, ['fake-template'] + extra)
    assert result.exit_code == 0
    expected_context = OrderedDict([('key1', 'value1'), ('key2', 'value2')])
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == expected_context


def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    ctx = MagicMock()
    param = MagicMock()
    value = ['key=value', 'another=123']
    result = validate_extra_context(ctx, param, value)
    assert isinstance(result, OrderedDict)
    assert result == OrderedDict([('key', 'value'), ('another', '123')])


def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter for invalid input."""
    ctx = MagicMock()
    param = MagicMock()
    value = ['invalid']
    with pytest.raises(SystemExit):
        validate_extra_context(ctx, param, value)


def test_main_with_checkout_option(runner, mock_cookiecutter):
    """Test running main with --checkout option."""
    result = runner.invoke(main, ['fake-template', '--checkout', 'develop'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout='develop',
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_directory_option(runner, mock_cookiecutter):
    """Test running main with --directory option."""
    result = runner.invoke(main, ['fake-template', '--directory', 'subdir'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory='subdir',
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_verbose_option(runner, mock_cookiecutter):
    """Test running main with --verbose option."""
    result = runner.invoke(main, ['fake-template', '--verbose'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_replay_option(runner, mock_cookiecutter):
    """Test running main with --replay option."""
    result = runner.invoke(main, ['fake-template', '--replay'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    assert mock_cookiecutter.call_args[1]['replay'] is True


def test_main_conflicting_no_input_and_replay(runner):
    """Test that using --no-input and --replay together raises an error."""
    result = runner.invoke(main, ['fake-template', '--no-input', '--replay'])
    assert result.exit_code != 0
    assert "Cannot combine" in result.output


def test_main_with_replay_file(runner, mock_cookiecutter):
    """Test running main with --replay-file option."""
    replay_file = 'replay.json'
    result = runner.invoke(main, ['fake-template', '--replay-file', replay_file])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=replay_file,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_overwrite_if_exists(runner, mock_cookiecutter):
    """Test running main with --overwrite-if-exists option."""
    result = runner.invoke(main, ['fake-template', '--overwrite-if-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=True,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_skip_if_file_exists(runner, mock_cookiecutter):
    """Test running main with --skip-if-file-exists option."""
    result = runner.invoke(main, ['fake-template', '--skip-if-file-exists'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=True,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_output_dir(runner, mock_cookiecutter):
    """Test running main with --output-dir option."""
    output_dir = '/path/to/output'
    result = runner.invoke(main, ['fake-template', '--output-dir', output_dir])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir=output_dir,
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )


def test_main_with_config_file(runner, mock_cookiecutter, mock_get_user_config):
    """Test running main with --config-file option."""
    config_file = '/path/to/config.yml'
    result = runner.invoke(main, ['fake-template', '--config-file', config_file])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_once_with(config_file=config_file, default_config=False)
    mock_cookiecutter.assert_called_once()


def test_main_with_default_config(runner, mock_cookiecutter, mock_get_user_config):
    """Test running main with --default-config option."""
    result = runner.invoke(main, ['fake-template', '--default-config'])
    assert result.exit_code == 0
    mock_get_user_config.assert_called_once_with(config_file=None, default_config=False)
    mock_cookiecutter.assert_called_once()


def test_main_with_debug_file(runner, mock_cookiecutter):
    """Test running main with --debug-file option."""
    debug_file = '/path/to/debug.log'
    result = runner.invoke(main, ['fake-template', '--debug-file', debug_file])
    assert result.exit_code == 0
    with patch("cookiecutter.cli.configure_logger") as mock_logger:
        mock_logger.assert_called_with(stream_level='INFO', debug_file=debug_file)


@pytest.mark.parametrize("accept_hooks, expected", [
    ('yes', True),
    ('no', False),
    ('ask', True),  # Assuming user accepts hooks in tests
])
def test_main_with_accept_hooks(runner, mock_cookiecutter, accept_hooks, expected):
    """Test running main with --accept-hooks option."""
    with patch("cookiecutter.cli.click.confirm", return_value=True) as mock_confirm:
        result = runner.invoke(main, ['fake-template', '--accept-hooks', accept_hooks])
        assert result.exit_code == 0
        if accept_hooks == 'ask':
            mock_confirm.assert_called_once()
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir='.',
            config_file=None,
            default_config=False,
            password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=expected,
            keep_project_on_failure=False,
        )


def test_main_keep_project_on_failure(runner, mock_cookiecutter):
    """Test running main with --keep-project-on-failure option."""
    result = runner.invoke(main, ['fake-template', '--keep-project-on-failure'])
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        checkout=None,
        no_input=False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file=None,
        default_config=False,
        password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=True,
    )


def test_main_cookiecutter_exceptions(runner, mock_cookiecutter):
    """Test handling of various Cookiecutter exceptions."""
    exceptions = [
        ContextDecodingException("Context decoding failed."),
        OutputDirExistsException("Output directory exists."),
        EmptyDirNameException("Empty directory name."),
        InvalidModeException("Invalid mode."),
        FailedHookException("Hook failed."),
        UnknownExtension("Unknown extension."),
        InvalidZipRepository("Invalid zip repository."),
        RepositoryNotFound("Repository not found."),
        RepositoryCloneFailed("Repository clone failed."),
    ]

    for exc in exceptions:
        mock_cookiecutter.side_effect = exc
        result = runner.invoke(main, ['fake-template'])
        assert result.exit_code == 1
        assert str(exc) in result.output
        mock_cookiecutter.reset_mock()


def test_main_undefined_variable_exception(runner, mock_cookiecutter):
    """Test handling of UndefinedVariableInTemplate exception."""
    undefined_err = UndefinedVariableInTemplate(
        message="Undefined variable.",
        error=MagicMock(message="Template error message."),
        context={"key": "value"}
    )
    mock_cookiecutter.side_effect = undefined_err
    result = runner.invoke(main, ['fake-template'])
    assert result.exit_code == 1
    assert undefined_err.message in result.output
    assert undefined_err.error.message in result.output
    assert json.dumps(undefined_err.context, indent=4, sort_keys=True) in result.output


def test_main_invalid_template(runner, mock_cookiecutter):
    """Test running main with an invalid template raises RepositoryNotFound."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Invalid template repository.")
    result = runner.invoke(main, ['invalid-template'])
    assert result.exit_code == 1
    assert "Invalid template repository." in result.output


def test_main_with_unknown_accept_hooks_option(runner):
    """Test that providing an invalid choice to --accept-hooks raises an error."""
    result = runner.invoke(main, ['fake-template', '--accept-hooks', 'maybe'])
    assert result.exit_code != 0
    assert "invalid choice" in result.output


def test_main_with_invalid_extra_context(runner):
    """Test that providing invalid extra_context raises a BadParameter error."""
    result = runner.invoke(main, ['fake-template', 'invalidcontext'])
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output


def test_main_with_existing_output_dir(runner, mock_cookiecutter):
    """Test running main when output directory already exists without overwrite."""
    with patch("os.path.exists", return_value=True):
        mock_cookiecutter.side_effect = OutputDirExistsException("Output directory exists.")
        result = runner.invoke(main, ['fake-template', '--output-dir', '/existing/dir'])
        assert result.exit_code == 1
        assert "Output directory exists." in result.output


def test_main_with_empty_directory_name(runner, mock_cookiecutter):
    """Test running main with an empty directory name."""
    mock_cookiecutter.side_effect = EmptyDirNameException("Empty directory name provided.")
    result = runner.invoke(main, ['fake-template', '--directory', ''])
    assert result.exit_code == 1
    assert "Empty directory name provided." in result.output


def test_main_with_invalid_yml_config(runner, mock_get_user_config):
    """Test running main with invalid YAML in config file."""
    with patch("cookiecutter.cli.get_config", side_effect=InvalidZipRepository("Invalid YAML")):
        result = runner.invoke(main, ['fake-template', '--config-file', 'invalid.yml'])
        assert result.exit_code == 1
        assert "Invalid YAML" in result.output


def test_main_with_unknown_extension(runner, mock_cookiecutter):
    """Test running main with an unknown extension."""
    mock_cookiecutter.side_effect = UnknownExtension("Unknown extension encountered.")
    result = runner.invoke(main, ['fake-template', '--accept-hooks', 'yes'])
    assert result.exit_code == 1
    assert "Unknown extension encountered." in result.output


def test_main_with_password(runner, mock_cookiecutter):
    """Test running main with a repository password."""
    with patch.dict(os.environ, {"COOKIECUTTER_REPO_PASSWORD": "secret"}):
        result = runner.invoke(main, ['fake-template'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir='.',
            config_file=None,
            default_config=False,
            password="secret",
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )


def test_main_with_nested_templates(runner, mock_cookiecutter):
    """Test running main with nested templates selection."""
    with patch("cookiecutter.cli.choose_nested_template", return_value='nested-template'):
        result = runner.invoke(main, ['fake-template'])
        assert result.exit_code == 0
        assert mock_cookiecutter.call_count == 2


def test_main_with_hooks_ask_yes(runner, mock_cookiecutter):
    """Test running main with --accept-hooks=ask and user agrees."""
    with patch("cookiecutter.cli.click.confirm", return_value=True):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir='.',
            config_file=None,
            default_config=False,
            password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )


def test_main_with_hooks_ask_no(runner, mock_cookiecutter):
    """Test running main with --accept-hooks=ask and user declines."""
    with patch("cookiecutter.cli.click.confirm", return_value=False):
        result = runner.invoke(main, ['fake-template', '--accept-hooks', 'ask'])
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir='.',
            config_file=None,
            default_config=False,
            password=os.environ.get('COOKIECUTTER_REPO_PASSWORD'),
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=False,
            keep_project_on_failure=False,
        )