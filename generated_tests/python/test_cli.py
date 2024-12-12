import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import os
import sys
from collections import OrderedDict
from unittest import mock

import pytest
from click.testing import CliRunner

from cookiecutter import __version__
from cookiecutter.cli import main, list_installed_templates, validate_extra_context
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
    """Fixture to create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Fixture to mock get_user_config."""
    with mock.patch("cookiecutter.cli.get_user_config") as mocked:
        mocked.return_value = {
            "cookiecutters_dir": "/fake/cookiecutters",
        }
        yield mocked


@pytest.fixture
def mock_cookiecutter():
    """Fixture to mock the main cookiecutter function."""
    with mock.patch("cookiecutter.cli.cookiecutter") as mocked:
        yield mocked


@pytest.fixture
def mock_logger():
    """Fixture to mock the configure_logger function."""
    with mock.patch("cookiecutter.cli.configure_logger") as mocked:
        mocked.return_value = mock.Mock()
        yield mocked


def test_version_option(runner):
    """Test the version option displays the correct version message."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    python_version = sys.version
    location = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    expected_output = f"Cookiecutter {__version__} from {location} (Python {python_version})"
    assert expected_output in result.output


def test_validate_extra_context_valid():
    """Test validate_extra_context with valid key=value pairs."""
    ctx = mock.Mock()
    param = mock.Mock()
    value = ("key1=value1", "key2=value2")
    result = validate_extra_context(ctx, param, value)
    assert isinstance(result, OrderedDict)
    assert result == OrderedDict([("key1", "value1"), ("key2", "value2")])


def test_validate_extra_context_invalid():
    """Test validate_extra_context raises BadParameter for invalid input."""
    ctx = mock.Mock()
    param = mock.Mock()
    value = ("invalidpair", "key2=value2")
    with pytest.raises(SystemExit) as exc_info:
        validate_extra_context(ctx, param, value)
    assert exc_info.type is SystemExit


def test_list_installed_templates_nonexistent_dir(runner, mock_config):
    """Test listing installed templates when the directory does not exist."""
    mock_config.return_value = {"cookiecutters_dir": "/non/existent/dir"}
    with mock.patch("os.path.exists", return_value=False):
        with mock.patch("click.echo") as mock_echo, \
             pytest.raises(SystemExit) as exc_info:
            list_installed_templates(default_config=False, passed_config_file=None)
        mock_echo.assert_called_with(
            "Error: Cannot list installed templates. Folder does not exist: /non/existent/dir"
        )
        assert exc_info.value.code == -1


def test_list_installed_templates_empty(runner, mock_config):
    """Test listing installed templates when no templates are installed."""
    mock_config.return_value = {"cookiecutters_dir": "/fake/cookiecutters"}
    with mock.patch("os.path.exists", return_value=True), \
         mock.patch("os.listdir", return_value=[]), \
         mock.patch("click.echo") as mock_echo:
        list_installed_templates(default_config=False, passed_config_file=None)
        mock_echo.assert_called_with("0 installed templates: ")


def test_list_installed_templates_with_templates(runner, mock_config):
    """Test listing installed templates with existing templates."""
    mock_config.return_value = {"cookiecutters_dir": "/fake/cookiecutters"}
    templates = ["template1", "template2"]
    with mock.patch("os.path.exists", return_value=True), \
         mock.patch("os.listdir", return_value=templates), \
         mock.patch("os.path.exists", side_effect=lambda path: path.endswith("cookiecutter.json")), \
         mock.patch("click.echo") as mock_echo:
        list_installed_templates(default_config=False, passed_config_file=None)
        mock_echo.assert_any_call("2 installed templates: ")
        for template in templates:
            mock_echo.assert_any_call(f" * {template}")


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["help"],
        ["--help"],
    ],
)
def test_main_no_template_shows_help(runner, args):
    """Test that running main without a template shows the help message."""
    result = runner.invoke(main, args)
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_main_list_installed(runner, mock_config, mock_cookiecutter):
    """Test the --list-installed option successfully lists templates."""
    with mock.patch("cookiecutter.cli.list_installed_templates") as mocked_list:
        result = runner.invoke(main, ["--list-installed"])
        mocked_list.assert_called_once_with(default_config=False, passed_config_file=None)
        assert result.exit_code == 0


def test_main_success(runner, mock_cookiecutter, mock_logger):
    """Test a successful invocation of the main command."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        result = runner.invoke(main, ["template-repo", "key=value", "--no-input"])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
            checkout=None,
            no_input=True,
            extra_context=OrderedDict([("key", "value")]),
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)
        assert result.exit_code == 0


def test_main_verbose(runner, mock_cookiecutter, mock_logger):
    """Test the --verbose flag sets the logger to DEBUG level."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--verbose"])
        mock_logger.assert_called_once_with(stream_level="DEBUG", debug_file=None)


def test_main_overwrite_if_exists(runner, mock_cookiecutter, mock_logger):
    """Test the --overwrite-if-exists flag."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--overwrite-if-exists"])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_replay_with_replay_file(runner, mock_cookiecutter, mock_logger):
    """Test the --replay and --replay-file options."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--replay", "--replay-file", "replay.json"])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
            checkout=None,
            no_input=False,
            extra_context=None,
            replay="replay.json",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_invalid_mode(runner):
    """Test that using --replay with --no-input raises an InvalidModeException."""
    with mock.patch("cookiecutter.cli.click.BadParameter") as mock_bad_param:
        result = runner.invoke(main, ["template-repo", "--replay", "--no-input"])
        assert result.exit_code != 0


def test_main_accept_hooks_yes(runner, mock_cookiecutter, mock_logger):
    """Test the --accept-hooks option set to yes."""
    with mock.patch("cookiecutter.cli.click.confirm", return_value=True):
        with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            runner.invoke(main, ["template-repo", "--accept-hooks", "yes"])
            mock_cookiecutter.assert_called_once()
            mock_logger.assert_called_once()
            mock_exit.assert_called_with(0)


def test_main_accept_hooks_no(runner, mock_cookiecutter, mock_logger):
    """Test the --accept-hooks option set to no."""
    with mock.patch("cookiecutter.cli.click.confirm", return_value=False):
        with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            runner.invoke(main, ["template-repo", "--accept-hooks", "no"])
            mock_cookiecutter.assert_called_once()
            mock_logger.assert_called_once()
            mock_exit.assert_called_with(0)


def test_main_accept_hooks_ask_confirm_yes(runner, mock_cookiecutter, mock_logger):
    """Test the --accept-hooks option set to ask and user confirms."""
    with mock.patch("cookiecutter.cli.click.confirm", return_value=True):
        with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            runner.invoke(main, ["template-repo", "--accept-hooks", "ask"])
            mock_cookiecutter.assert_called_once()
            mock_logger.assert_called_once()
            mock_exit.assert_called_with(0)


def test_main_accept_hooks_ask_confirm_no(runner, mock_cookiecutter, mock_logger):
    """Test the --accept-hooks option set to ask and user declines."""
    with mock.patch("cookiecutter.cli.click.confirm", return_value=False):
        with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            runner.invoke(main, ["template-repo", "--accept-hooks", "ask"])
            mock_cookiecutter.assert_called_once()
            mock_logger.assert_called_once()
            mock_exit.assert_called_with(0)


@pytest.mark.parametrize(
    "exception",
    [
        ContextDecodingException("Decoding failed"),
        OutputDirExistsException("Output dir exists"),
        EmptyDirNameException("Empty dir name"),
        InvalidModeException("Invalid mode"),
        FailedHookException("Hook failed"),
        UnknownExtension("Unknown extension"),
        InvalidZipRepository("Invalid zip"),
        RepositoryNotFound("Repo not found"),
        RepositoryCloneFailed("Clone failed"),
    ],
)
def test_main_exceptions(runner, mock_cookiecutter, mock_logger, exception):
    """Test that exceptions are handled and the program exits with code 1."""
    mock_cookiecutter.side_effect = exception
    with mock.patch("cookiecutter.cli.click.echo") as mock_echo:
        with pytest.raises(SystemExit) as exc_info:
            runner.invoke(main, ["template-repo"])
        mock_echo.assert_called_with(str(exception))
        assert exc_info.value.code == 1


def test_main_undefined_variable_exception(runner, mock_cookiecutter, mock_logger):
    """Test handling of UndefinedVariableInTemplate exception."""
    undefined_error = mock.Mock(message="Undefined variable error")
    exception = UndefinedVariableInTemplate(
        message="Undefined variable",
        error=undefined_error,
        context={"key": "value"},
    )
    mock_cookiecutter.side_effect = exception
    with mock.patch("cookiecutter.cli.click.echo") as mock_echo:
        with pytest.raises(SystemExit) as exc_info:
            runner.invoke(main, ["template-repo"])
        mock_echo.assert_any_call("Undefined variable")
        mock_echo.assert_any_call("Error message: Undefined variable error")
        mock_echo.assert_any_call(
            'Context: {\n    "key": "value"\n}'
        )
        assert exc_info.value.code == 1


def test_main_with_extra_context(runner, mock_cookiecutter, mock_logger):
    """Test passing extra context to the cookiecutter function."""
    extra_context = ["key1=value1", "key2=value2"]
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo"] + extra_context)
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
            checkout=None,
            no_input=False,
            extra_context=OrderedDict([("key1", "value1"), ("key2", "value2")]),
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_with_output_dir(runner, mock_cookiecutter, mock_logger):
    """Test specifying a custom output directory."""
    output_dir = "/custom/output"
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--output-dir", output_dir])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_with_config_file(runner, mock_cookiecutter, mock_logger, mock_config):
    """Test specifying a custom config file."""
    config_file = "/path/to/config.yaml"
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--config-file", config_file])
        mock_config.assert_called_once_with(
            config_file, default_config=False
        )
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=config_file,
            default_config=False,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_with_default_config(runner, mock_cookiecutter, mock_logger, mock_config):
    """Test using the --default-config flag."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--default-config"])
        mock_config.assert_called_once_with(
            config_file=None, default_config=True
        )
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
            checkout=None,
            no_input=False,
            extra_context=None,
            replay=False,
            overwrite_if_exists=False,
            output_dir=".",
            config_file=None,
            default_config=True,
            password=None,
            directory=None,
            skip_if_file_exists=False,
            accept_hooks=True,
            keep_project_on_failure=False,
        )
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_with_debug_file(runner, mock_cookiecutter, mock_logger):
    """Test specifying a debug file for logging."""
    debug_file = "/path/to/debug.log"
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--debug-file", debug_file])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once_with(stream_level="INFO", debug_file=debug_file)
        mock_exit.assert_called_with(0)


def test_main_keep_project_on_failure(runner, mock_cookiecutter, mock_logger):
    """Test the --keep-project-on-failure flag."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--keep-project-on-failure"])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_skip_if_file_exists(runner, mock_cookiecutter, mock_logger):
    """Test the --skip-if-file-exists flag."""
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--skip-if-file-exists"])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_with_directory(runner, mock_cookiecutter, mock_logger):
    """Test specifying a directory within the repository."""
    directory = "subdir"
    with mock.patch("cookiecutter.cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        runner.invoke(main, ["template-repo", "--directory", directory])
        mock_cookiecutter.assert_called_once_with(
            "template-repo",
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
        mock_logger.assert_called_once()
        mock_exit.assert_called_with(0)