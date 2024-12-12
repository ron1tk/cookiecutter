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
from cookiecutter.log import configure_logger
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
    """Fixture to mock the config.get_user_config function."""
    with patch('cookiecutter.cli.get_user_config') as mock:
        mock.return_value = {
            'cookiecutters_dir': '/fake/cookiecutters/',
            'replay_dir': '/fake/replay/',
            'default_context': {},
            'abbreviations': {},
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
def mock_os_path_exists():
    """Fixture to mock os.path.exists."""
    with patch('cookiecutter.cli.os.path.exists') as mock:
        yield mock


@pytest.fixture
def mock_os_listdir():
    """Fixture to mock os.listdir."""
    with patch('cookiecutter.cli.os.listdir') as mock:
        mock.return_value = ['template1', 'template2']
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
def mock_click_confirm():
    """Fixture to mock click.confirm."""
    with patch('cookiecutter.cli.click.confirm') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_click_get_current_context():
    """Fixture to mock click.get_current_context().get_help()."""
    with patch('cookiecutter.cli.click.get_current_context') as mock_context:
        mock_ctx = MagicMock()
        mock_ctx.get_help.return_value = 'Help Message'
        mock_context.return_value = mock_ctx
        yield mock_context


def test_version_msg():
    """Test that version_msg returns the correct version string."""
    expected = f"Cookiecutter {__import__('cookiecutter').__version__} from {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))} (Python {sys.version})"
    assert version_msg().startswith("Cookiecutter ")


@pytest.mark.parametrize(
    "extra_context,expected",
    [
        (['key=value'], OrderedDict({'key': 'value'})),
        (['a=1', 'b=2'], OrderedDict({'a': '1', 'b': '2'})),
        ([], None),
    ],
)
def test_validate_extra_context(extra_context, expected):
    """Test validate_extra_context with various inputs."""
    from click import Context, BadParameter
    from click.testing import CliRunner

    ctx = Context(main)
    param = MagicMock()
    if extra_context:
        result = main.validate_extra_context(ctx, param, extra_context)
        assert result == expected
    else:
        result = main.validate_extra_context(ctx, param, [])
        assert result is None


def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter for invalid input."""
    from click import Context, BadParameter

    ctx = Context(main)
    param = MagicMock()
    with pytest.raises(BadParameter):
        main.validate_extra_context(ctx, param, ['invalid'])


def test_main_no_arguments(runner, mock_click_get_current_context, mock_sys_exit, mock_click_echo):
    """Test running main without arguments shows help and exits."""
    result = runner.invoke(main, [])
    mock_click_echo.assert_called_with('Help Message')
    mock_sys_exit.assert_called_with(0)


def test_main_help_argument(runner, mock_click_get_current_context, mock_sys_exit, mock_click_echo):
    """Test running main with 'help' argument shows help and exits."""
    result = runner.invoke(main, ['help'])
    mock_click_echo.assert_called_with('Help Message')
    mock_sys_exit.assert_called_with(0)


def test_main_list_installed(
    runner,
    mock_list_installed_templates,
    mock_get_user_config,
    mock_os_path_exists,
    mock_os_listdir,
    mock_sys_exit,
):
    """Test the --list-installed option when the directory exists."""
    mock_os_path_exists.return_value = True
    result = runner.invoke(main, ['--list-installed'])
    mock_list_installed_templates.assert_called_once_with(False, None)
    mock_sys_exit.assert_called_with(0)
    assert result.exit_code == 0


def test_main_list_installed_no_dir(
    runner,
    mock_list_installed_templates,
    mock_click_echo,
    mock_os_path_exists,
    mock_sys_exit,
):
    """Test the --list-installed option when the directory does not exist."""
    mock_os_path_exists.return_value = False
    result = runner.invoke(main, ['--list-installed'])
    mock_click_echo.assert_called_with(
        "Error: Cannot list installed templates. Folder does not exist: /fake/cookiecutters/"
    )
    mock_sys_exit.assert_called_with(-1)
    assert result.exit_code == -1


def test_main_with_template_success(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_confirm,
):
    """Test running main with a valid template and --no-input."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--no-input', '--output-dir', '/fake/output']
    )
    mock_configure_logger.assert_called_once()
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
        None,
        True,
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
    assert result.exit_code == 0


def test_main_with_extra_context(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with extra context provided."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', 'key1=value1', 'key2=value2']
    )
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == OrderedDict({'key1': 'value1', 'key2': 'value2'})
    assert result.exit_code == 0


def test_main_invalid_extra_context(
    runner,
):
    """Test running main with invalid extra context."""
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', 'invalid']
    )
    assert result.exit_code != 0
    assert "EXTRA_CONTEXT should contain items of the form key=value; 'invalid' doesn't match that form" in result.output


def test_main_no_input_and_replay(
    runner,
):
    """Test running main with both --no-input and --replay flags."""
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--no-input', '--replay']
    )
    assert result.exit_code != 0
    assert "Cannot be combined with the --replay flag" in result.output


@pytest.mark.parametrize("exception", [
    ContextDecodingException("Decoding failed"),
    OutputDirExistsException("Output directory exists"),
    EmptyDirNameException("Empty directory name"),
    InvalidModeException("Invalid mode"),
    FailedHookException("Hook failed"),
    UnknownExtension("Unknown extension"),
    InvalidZipRepository("Invalid zip"),
    RepositoryNotFound("Repository not found"),
    RepositoryCloneFailed("Clone failed"),
])
def test_main_cookiecutter_exceptions(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    exception
):
    """Test main handles various cookiecutter exceptions."""
    mock_cookiecutter.side_effect = exception
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--no-input']
    )
    assert exception.args[0] in result.output
    assert result.exit_code == 1


def test_main_undefined_variable_exception(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test main handles UndefinedVariableInTemplate exception."""
    undefined_error = UndefinedVariableInTemplate("Undefined variable", MagicMock(message="Missing var"), {"var": "value"})
    mock_cookiecutter.side_effect = undefined_error
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--no-input']
    )
    assert "Undefined variable" in result.output
    assert "Missing var" in result.output
    assert "Context" in result.output
    assert result.exit_code == 1


def test_main_version_option(runner):
    """Test the --version option displays the version message."""
    result = runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert "Cookiecutter" in result.output


def test_main_list_installed_templates_call(
    runner,
    mock_list_installed_templates,
    mock_get_user_config,
):
    """Test that list_installed_templates is called with correct parameters."""
    runner.invoke(main, ['--list-installed', '--config-file', '/fake/config.yaml', '--default-config'])
    mock_list_installed_templates.assert_called_once_with(True, '/fake/config.yaml')


def test_main_accept_hooks_yes(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_click_confirm,
):
    """Test running main with --accept-hooks set to 'yes'."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--accept-hooks', 'yes']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_accept_hooks_ask_yes(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_click_confirm,
):
    """Test running main with --accept-hooks set to 'ask' and user confirms."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--accept-hooks', 'ask']
    )
    mock_click_confirm.assert_called_once_with("Do you want to execute hooks?")
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_accept_hooks_ask_no(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_click_confirm,
):
    """Test running main with --accept-hooks set to 'ask' and user declines."""
    mock_click_confirm.return_value = False
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--accept-hooks', 'ask']
    )
    mock_click_confirm.assert_called_once_with("Do you want to execute hooks?")
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_overwrite_if_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --overwrite-if-exists flag."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--overwrite-if-exists']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_skip_if_file_exists(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --skip-if-file-exists flag."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--skip-if-file-exists']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_debug_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with --debug-file option."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--debug-file', '/fake/debug.log']
    )
    mock_configure_logger.assert_called_once_with(stream_level='INFO', debug_file='/fake/debug.log')
    mock_cookiecutter.assert_called_once()
    assert result.exit_code == 0


def test_main_with_replay_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with --replay-file option."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--replay-file', '/fake/replay.json']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
        None,
        False,
        extra_context=None,
        replay='/fake/replay.json',
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


def test_main_with_directory_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --directory option."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--directory', 'subdir']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_checkout_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --checkout option."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--checkout', 'develop']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_password_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with environment variable for password."""
    with patch.dict(os.environ, {"COOKIECUTTER_REPO_PASSWORD": "secret"}):
        mock_cookiecutter.return_value = '/fake/output/project'
        result = runner.invoke(
            main,
            ['tests/fake-repo-tmpl']
        )
        mock_cookiecutter.assert_called_once_with(
            'tests/fake-repo-tmpl',
            None,
            False,
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
        assert result.exit_code == 0


def test_main_with_keep_project_on_failure(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --keep-project-on-failure flag."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--keep-project-on-failure']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_config_file(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --config-file option."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--config-file', '/fake/config.yaml']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
        None,
        False,
        extra_context=None,
        replay=False,
        overwrite_if_exists=False,
        output_dir='.',
        config_file='/fake/config.yaml',
        default_config=False,
        password=None,
        directory=None,
        skip_if_file_exists=False,
        accept_hooks=True,
        keep_project_on_failure=False,
    )
    assert result.exit_code == 0


def test_main_with_default_config(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --default-config flag."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--default-config']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_unknown_accept_hooks_option(
    runner,
):
    """Test running main with an invalid --accept-hooks option."""
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--accept-hooks', 'maybe']
    )
    assert result.exit_code != 0
    assert "invalid choice: maybe. (choose from yes, ask, no)" in result.output


def test_main_unknown_template(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with a non-existent template."""
    mock_cookiecutter.side_effect = RepositoryNotFound("Repository not found")
    result = runner.invoke(
        main,
        ['nonexistent-template', '--no-input']
    )
    assert "Repository not found" in result.output
    assert result.exit_code == 1


def test_main_with_verbose(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with --verbose flag."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--verbose']
    )
    mock_configure_logger.assert_called_once_with(stream_level='DEBUG', debug_file=None)
    mock_cookiecutter.assert_called_once()
    assert result.exit_code == 0


def test_main_with_abbreviations(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
):
    """Test running main with template abbreviations."""
    mock_get_user_config.return_value['abbreviations'] = {'gh': 'https://github.com/{0}.git'}
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['gh:user/repo']
    )
    mock_cookiecutter.assert_called_once_with(
        'https://github.com/user/repo.git',
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
    assert result.exit_code == 0


def test_main_with_nested_template(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
    mock_configure_logger,
    mock_click_confirm,
    mock_os_path_exists,
    mock_os_listdir,
):
    """Test running main with a nested template selection."""
    # Mock the repository to have nested templates
    with patch('cookiecutter.cli.generate_context') as mock_generate_context:
        mock_generate_context.return_value = {
            'cookiecutter': {
                'template': 'nested-template',
                'name': 'Test Project'
            }
        }
        mock_cookiecutter.return_value = '/fake/output/nested-project'
        result = runner.invoke(
            main,
            ['tests/fake-repo-tmpl', '--no-input']
        )
        assert result.exit_code == 0
        mock_cookiecutter.assert_called()


def test_main_keep_project_on_failure(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test the --keep-project-on-failure flag."""
    mock_cookiecutter.side_effect = FailedHookException("Hook failed")
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--keep-project-on-failure']
    )
    assert "Hook failed" in result.output
    assert result.exit_code == 1


def test_version_msg_content():
    """Test that version_msg contains correct version and Python info."""
    msg = version_msg()
    assert "Cookiecutter" in msg
    assert "Python" in msg


def test_main_with_unknown_hook_option(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with an unknown hook acceptance option."""
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--accept-hooks', 'maybe']
    )
    assert result.exit_code != 0
    assert "invalid choice: maybe. (choose from yes, ask, no)" in result.output


def test_main_with_nonexistent_config_file(
    runner,
    mock_get_user_config,
):
    """Test running main with a non-existent config file."""
    from cookiecutter.exceptions import ConfigDoesNotExistException
    with patch('cookiecutter.cli.get_config', side_effect=ConfigDoesNotExistException("Config not found")):
        result = runner.invoke(
            main,
            ['tests/fake-repo-tmpl', '--config-file', '/nonexistent/config.yaml']
        )
        assert "Config not found" in result.output
        assert result.exit_code == 1


def test_main_with_invalid_yaml_config(
    runner,
    mock_get_user_config,
):
    """Test running main with an invalid YAML config file."""
    from cookiecutter.exceptions import InvalidConfiguration
    with patch('cookiecutter.cli.get_config', side_effect=InvalidConfiguration("Invalid YAML")):
        result = runner.invoke(
            main,
            ['tests/fake-repo-tmpl', '--config-file', '/invalid/config.yaml']
        )
        assert "Invalid YAML" in result.output
        assert result.exit_code == 1


def test_main_with_replay_true(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with --replay flag set to True."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--replay']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
        None,
        False,
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


def test_main_with_multiple_exceptions(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test main handling multiple types of exceptions."""
    exceptions = [
        ContextDecodingException("Decoding failed"),
        OutputDirExistsException("Output directory exists"),
        EmptyDirNameException("Empty directory name"),
        InvalidModeException("Invalid mode"),
        FailedHookException("Hook failed"),
        UnknownExtension("Unknown extension"),
        InvalidZipRepository("Invalid zip"),
        RepositoryNotFound("Repository not found"),
        RepositoryCloneFailed("Clone failed"),
    ]
    for exc in exceptions:
        mock_cookiecutter.side_effect = exc
        result = runner.invoke(
            main,
            ['tests/fake-repo-tmpl', '--no-input']
        )
        assert exc.args[0] in result.output
        assert result.exit_code == 1
        mock_cookiecutter.reset_mock()


def test_main_with_empty_extra_context(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with empty extra_context."""
    mock_cookiecutter.return_value = '/fake/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_custom_output_dir(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with a custom output directory."""
    mock_cookiecutter.return_value = '/custom/output/project'
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl', '--output-dir', '/custom/output']
    )
    mock_cookiecutter.assert_called_once_with(
        'tests/fake-repo-tmpl',
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
    assert result.exit_code == 0


def test_main_with_multiple_extra_contexts(
    runner,
    mock_cookiecutter,
    mock_get_user_config,
):
    """Test running main with multiple extra_context arguments."""
    mock_cookiecutter.return_value = '/fake/output/project'
    extra_context = ['key1=value1', 'key2=value2', 'key3=value3']
    result = runner.invoke(
        main,
        ['tests/fake-repo-tmpl'] + extra_context
    )
    mock_cookiecutter.assert_called_once()
    args, kwargs = mock_cookiecutter.call_args
    assert kwargs['extra_context'] == OrderedDict({
        'key1': 'value1',
        'key2': 'value2',
        'key3': 'value3',
    })
    assert result.exit_code == 0