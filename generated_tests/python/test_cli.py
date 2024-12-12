import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import os
import sys
from collections import OrderedDict
from unittest.mock import Mock, patch

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
from cookiecutter.main import cookiecutter


@pytest.fixture
def runner():
    """Fixture for Click CLI runner."""
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
        }
        yield mock


@pytest.fixture
def mock_configure_logger():
    """Fixture to mock the configure_logger function."""
    with patch('cookiecutter.cli.configure_logger') as mock:
        yield mock


@pytest.fixture
def mock_list_installed_templates():
    """Fixture to mock the list_installed_templates function."""
    with patch('cookiecutter.cli.list_installed_templates') as mock:
        yield mock


@pytest.fixture
def mock_sys_exit():
    """Fixture to mock sys.exit."""
    with patch('sys.exit') as mock:
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
    with patch('cookiecutter.cli.os.path.join') as mock:
        mock.side_effect = lambda a, b, c=None: f"{a}/{b}/{c}" if c else f"{a}/{b}"
        yield mock


def test_version_option(runner):
    """Test that the version option outputs the correct version message."""
    result = runner.invoke(cli.main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output
    assert "__version__" in result.output  # Replace with actual version if needed


def test_list_installed_templates_success(
    runner,
    mock_list_installed_templates,
    mock_sys_exit,
    mock_click_echo,
    mock_os_path_exists,
    mock_os_listdir,
    mock_os_path_join,
    mock_get_user_config,
):
    """Test listing installed templates successfully."""
    result = runner.invoke(cli.main, ['--list-installed'])
    assert result.exit_code == 0
    mock_list_installed_templates.assert_called_once_with(False, None)
    mock_sys_exit.assert_called_once_with(0)


def test_list_installed_templates_folder_not_exist(
    runner,
    mock_cookiecutter,
    mock_sys_exit,
    mock_click_echo,
    mock_os_path_exists,
    mock_get_user_config,
):
    """Test listing installed templates when folder does not exist."""
    mock_os_path_exists.return_value = False
    result = runner.invoke(cli.main, ['--list-installed'])
    assert result.exit_code == 1
    mock_click_echo.assert_called_with(
        "Error: Cannot list installed templates. Folder does not exist: /fake/cookiecutters"
    )
    mock_sys_exit.assert_called_once_with(-1)


def test_main_no_arguments_help(
    runner,
    mock_click_echo,
    mock_sys_exit,
):
    """Test main command with no arguments displays help."""
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "Usage" in result.output
    mock_sys_exit.assert_called_once_with(0)


def test_main_help_argument(
    runner,
    mock_click_echo,
    mock_sys_exit,
):
    """Test main command with 'help' argument displays help."""
    result = runner.invoke(cli.main, ['help'])
    assert result.exit_code == 0
    assert "Usage" in result.output
    mock_sys_exit.assert_called_once_with(0)


def test_validate_extra_context_valid(runner):
    """Test validate_extra_context with valid key=value pairs."""
    ctx = Mock()
    param = Mock()
    value = ('key1=value1', 'key2=value2')
    result = cli.validate_extra_context(ctx, param, value)
    assert isinstance(result, OrderedDict)
    assert result == OrderedDict([('key1', 'value1'), ('key2', 'value2')])


def test_validate_extra_context_invalid(runner):
    """Test validate_extra_context with invalid key=value pair."""
    ctx = Mock()
    param = Mock()
    value = ('key1value1', 'key2=value2')
    with pytest.raises(SystemExit):
        cli.validate_extra_context(ctx, param, value)


def test_main_successful_execution(
    runner,
    mock_cookiecutter,
    mock_configure_logger,
    mock_get_user_config,
):
    """Test successful execution of main with template and no extra context."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(cli.main, ['fake-template'])
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once()
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
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
    mock_configure_logger,
    mock_get_user_config,
):
    """Test main with extra_context provided."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            'key1=value1',
            'key2=value2',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {'key1': 'value1', 'key2': 'value2'},
        False,
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


def test_main_no_input_and_replay_flags_conflict(
    runner,
    mock_click_echo,
    mock_sys_exit,
):
    """Test that using --no-input with --replay raises an error."""
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--no-input',
            '--replay',
        ],
    )
    assert result.exit_code == 1
    assert "You can not use both replay and no_input or extra_context" in result.output
    mock_sys_exit.assert_called_once_with(1)


@patch('cookiecutter.cli.click.confirm', return_value=True)
def test_main_accept_hooks_ask_yes(
    mock_confirm,
    runner,
    mock_cookiecutter,
    mock_configure_logger,
    mock_get_user_config,
):
    """Test that hooks are accepted when 'ask' and user confirms."""
    mock_cookiecutter.return_value = "/fake/output/project"
    with patch('cookiecutter.cli.run_pre_prompt_hook', return_value='/fake/repo'):
        result = runner.invoke(
            cli.main,
            [
                'fake-template',
                '--accept-hooks',
                'ask',
            ],
        )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once()
    mock_confirm.assert_called_once_with("Do you want to execute hooks?")


@patch('cookiecutter.cli.run_pre_prompt_hook', side_effect=FailedHookException("Hook failed"))
def test_main_hook_failure(
    mock_run_hook,
    runner,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test that hook failure is handled properly."""
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Hook failed" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_cookiecutter_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test that Cookiecutter exceptions are handled and exit with error."""
    mock_cookiecutter.side_effect = OutputDirExistsException("Output directory exists")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Output directory exists" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_undefined_variable_in_template(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of UndefinedVariableInTemplate exception."""
    template_error = Mock()
    template_error.message = "Undefined variable"
    mock_cookiecutter.side_effect = UndefinedVariableInTemplate(
        "Undefined variable in template",
        template_error,
        {"key": "value"},
    )
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Undefined variable in template" in result.output
    assert "Error message: Undefined variable" in result.output
    assert '"key": "value"' in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_version_option_short(runner):
    """Test that the short version option outputs the version."""
    result = runner.invoke(cli.main, ['-V'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output


def test_main_version_option_long(runner):
    """Test that the long version option outputs the version."""
    result = runner.invoke(cli.main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output


def test_main_overwrite_if_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test the overwrite-if-exists flag."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--overwrite-if-exists',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        True,
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


def test_main_skip_if_file_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test the skip-if-file-exists flag."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--skip-if-file-exists',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        True,
        'yes',
        None,
        False,
    )


def test_main_output_dir(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test specifying the output directory."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--output-dir',
            '/custom/output',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '/custom/output',
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


def test_main_config_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test specifying a custom config file."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--config-file',
            '/path/to/config.yaml',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        '/path/to/config.yaml',
        False,
        None,
        None,
        None,
        False,
        'yes',
        None,
        False,
    )


def test_main_default_config(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test using the default config instead of a config file."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--default-config',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        None,
        True,
        None,
        None,
        None,
        False,
        'yes',
        None,
        False,
    )


def test_main_debug_file(
    runner,
    mock_cookiecutter,
    mock_configure_logger,
    mock_get_user_config,
):
    """Test specifying a debug file for logging."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--debug-file',
            '/path/to/debug.log',
        ],
    )
    assert result.exit_code == 0
    mock_configure_logger.assert_called_once_with(
        stream_level='INFO',
        debug_file='/path/to/debug.log',
    )
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        None,
        False,
        '/path/to/debug.log',
        None,
        None,
        False,
        'yes',
        None,
        False,
    )


def test_main_accept_hooks_no(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test setting accept_hooks to 'no'."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--accept-hooks',
            'no',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        'no',
        None,
        False,
    )


def test_main_accept_hooks_yes(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test setting accept_hooks to 'yes'."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--accept-hooks',
            'yes',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
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


def test_main_replay_flag(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test using the --replay flag."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--replay',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        True,
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


def test_main_replay_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test using the --replay-file option."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--replay-file',
            '/path/to/replay.json',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        '/path/to/replay.json',
        False,
        '.',
        None,
        False,
        None,
        None,
        None,
        False,
        'yes',
        '/path/to/replay.json',
        False,
    )


def test_main_directory_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test specifying the --directory option."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--directory',
            'subdir/template',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
        False,
        '.',
        None,
        False,
        None,
        None,
        'subdir/template',
        False,
        'yes',
        None,
        False,
    )


def test_main_checkout_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test specifying the --checkout option."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--checkout',
            'develop',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        'develop',
        False,
        {},
        False,
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


def test_main_password_environment_variable(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test that COOKIECUTTER_REPO_PASSWORD environment variable is used."""
    with patch.dict(os.environ, {'COOKIECUTTER_REPO_PASSWORD': 'secret'}):
        mock_cookiecutter.return_value = "/fake/output/project"
        result = runner.invoke(
            cli.main,
            [
                'fake-template',
            ],
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called_once_with(
            'fake-template',
            None,
            False,
            {},
            False,
            False,
            '.',
            None,
            False,
            None,
            'secret',
            None,
            False,
            'yes',
            None,
            False,
        )


def test_main_keep_project_on_failure(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test the --keep-project-on-failure flag."""
    mock_cookiecutter.return_value = "/fake/output/project"
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            '--keep-project-on-failure',
        ],
    )
    assert result.exit_code == 0
    mock_cookiecutter.assert_called_once_with(
        'fake-template',
        None,
        False,
        {},
        False,
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
        True,
    )


def test_main_invalid_extra_context_format(
    runner,
    mock_click_echo,
    mock_sys_exit,
):
    """Test main with invalid extra_context format."""
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
            'invalidcontext',
        ],
    )
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_unknown_extension_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of UnknownExtension exception."""
    mock_cookiecutter.side_effect = UnknownExtension("Unknown extension")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Unknown extension" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_repository_not_found_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of RepositoryNotFound exception."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Repository not found")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Repository not found" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_invalid_zip_repository_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of InvalidZipRepository exception."""
    mock_cookiecutter.side_effect = InvalidZipRepository("Invalid zip repository")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Invalid zip repository" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_repository_clone_failed_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of RepositoryCloneFailed exception."""
    mock_cookiecutter.side_effect = RepositoryCloneFailed("Clone failed")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Clone failed" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_invalid_mode_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of InvalidModeException."""
    mock_cookiecutter.side_effect = InvalidModeException("Invalid mode")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Invalid mode" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_context_decoding_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of ContextDecodingException."""
    mock_cookiecutter.side_effect = ContextDecodingException("Decoding failed")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Decoding failed" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_empty_dir_name_exception(
    runner,
    mock_cookiecutter,
    mock_click_echo,
    mock_sys_exit,
    mock_get_user_config,
):
    """Test handling of EmptyDirNameException."""
    mock_cookiecutter.side_effect = EmptyDirNameException("Empty directory name")
    result = runner.invoke(
        cli.main,
        [
            'fake-template',
        ],
    )
    assert result.exit_code == 1
    assert "Empty directory name" in result.output
    mock_sys_exit.assert_called_once_with(1)


def test_main_invalid_parameters(
    runner,
):
    """Test main with invalid parameters."""
    result = runner.invoke(
        cli.main,
        [
            '--unknown-option',
        ],
    )
    assert result.exit_code != 0
    assert "No such option" in result.output


def test_main_help_option(
    runner,
):
    """Test that --help option displays help."""
    result = runner.invoke(cli.main, ['--help'])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_main_version_message(
    runner,
):
    """Test the custom version message."""
    with patch('cookiecutter.cli.__version__', '1.2.3'):
        result = runner.invoke(cli.main, ['--version'])
        assert result.exit_code == 0
        assert "Cookiecutter 1.2.3" in result.output
        assert "Python" in result.output