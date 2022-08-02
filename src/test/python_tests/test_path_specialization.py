"""
Test for argv duplicaiton over LSP.
"""
import copy

from hamcrest import assert_that, is_

from .lsp_test_client import constants, defaults, session, utils

FORMATTER = utils.get_server_info_defaults()
TIMEOUT = 10  # 10 seconds


class CallbackObject:
    """Object that holds results for WINDOW_LOG_MESSAGE to capture argv"""

    def __init__(self):
        self.result = False

    def check_result(self):
        """returns Boolean result"""
        return self.result

    def check_for_argv_duplication(self, argv):
        """checks if argv duplication exists and sets result boolean"""
        if argv["type"] == 4 and argv["message"].split().count("--stdin-filename") > 1:
            self.result = True
            return None


def test_path():
    """Test linting using pylint bin path set."""
    FORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
    VSCODE_DEFAULT_INITIALIZE = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    VSCODE_DEFAULT_INITIALIZE["initializationOptions"]["settings"][0]["path"] = [
        "pylint"
    ]
    EXPECTED = False

    argv_callback_object = CallbackObject()
    contents = FORMATTED_TEST_FILE_PATH.read_text()

    actual = []
    with utils.python_file(contents, FORMATTED_TEST_FILE_PATH.parent) as pf:
        uri = utils.as_uri(str(pf))

        with session.LspSession() as ls_session:
            ls_session.set_notification_callback(
                session.WINDOW_LOG_MESSAGE,
                argv_callback_object.check_for_argv_duplication,
            )

            ls_session.initialize(VSCODE_DEFAULT_INITIALIZE)
            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            actual = argv_callback_object.check_result()

    assert_that(actual, is_(EXPECTED))


def test_interpreter():
    """Test linting using specific python path."""
    FORMATTED_TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
    VSCODE_DEFAULT_INITIALIZE = copy.deepcopy(defaults.VSCODE_DEFAULT_INITIALIZE)
    VSCODE_DEFAULT_INITIALIZE["initializationOptions"]["settings"][0]["interpreter"] = [
        "python"
    ]
    EXPECTED = False

    argv_callback_object = CallbackObject()
    contents = FORMATTED_TEST_FILE_PATH.read_text()

    actual = []
    with utils.python_file(contents, FORMATTED_TEST_FILE_PATH.parent) as pf:
        uri = utils.as_uri(str(pf))

        with session.LspSession() as ls_session:
            ls_session.set_notification_callback(
                session.WINDOW_LOG_MESSAGE,
                argv_callback_object.check_for_argv_duplication,
            )

            ls_session.initialize(VSCODE_DEFAULT_INITIALIZE)
            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            ls_session.notify_did_open(
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": "python",
                        "version": 1,
                        "text": contents,
                    }
                }
            )

            actual = argv_callback_object.check_result()

    assert_that(actual, is_(EXPECTED))
