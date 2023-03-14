# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for code actions over LSP.
"""

import os
from threading import Event

import pytest
from hamcrest import assert_that, greater_than, is_

from .lsp_test_client import constants, session, utils

TEST_FILE_PATH = constants.TEST_DATA / "sample1" / "sample.py"
TEST_FILE_URI = utils.as_uri(str(TEST_FILE_PATH))
LINTER = utils.get_server_info_defaults()["name"]
TIMEOUT = 10  # 10 seconds


def _expected_format_command():
    return {
        "title": f"{LINTER}: Run document formatting",
        "command": "editor.action.formatDocument",
    }


def _expected_organize_imports_command():
    return {
        "title": f"{LINTER}: Run organize imports",
        "command": "editor.action.organizeImports",
    }


@pytest.mark.parametrize(
    ("code", "contents", "command"),
    [
        (
            "C0301:line-too-long",
            # pylint: disable=line-too-long
            "FRUIT = ['apricot', 'blackcurrant', 'cantaloupe', 'dragon fruit', 'elderberry', 'fig', 'grapefruit', 'honeydew melon', 'jackfruit', 'kiwi', 'lemon', 'mango', 'nectarine', 'orange', 'papaya', 'quince', 'raspberry', 'strawberry', 'tangerine', 'watermelon']\n",
            _expected_format_command(),
        ),
        (
            "C0303:trailing-whitespace",
            "x =  1    \ny = 1\n",
            _expected_format_command(),
        ),
        (
            "C0304:missing-final-newline",
            "print('hello')",
            _expected_format_command(),
        ),
        (
            "C0305:trailing-newlines",
            "VEGGIE = ['carrot', 'radish', 'cucumber', 'potato']\n\n\n",
            _expected_format_command(),
        ),
        (
            "C0321:multiple-statements",
            "import sys; print(sys.executable)\n",
            _expected_format_command(),
        ),
        (
            "C0410:multiple-imports",
            "import os, sys\n",
            _expected_organize_imports_command(),
        ),
        (
            "C0411:wrong-import-order",
            "import os\nfrom . import utils\nimport pylint\nimport sys\n",
            _expected_organize_imports_command(),
        ),
        (
            "C0412:ungrouped-imports",
            # pylint: disable=line-too-long
            "import logging\nimport os\nimport sys\nimport logging.config\nfrom logging.handlers import WatchedFileHandler\n",
            _expected_organize_imports_command(),
        ),
    ],
)
def test_command_code_action(code, contents, command):
    """Tests for code actions which run a command."""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
        uri = utils.as_uri(os.fspath(temp_file))

        actual = {}
        with session.LspSession() as ls_session:
            ls_session.initialize()

            done = Event()

            def _handler(params):
                nonlocal actual
                actual = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

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

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            diagnostics = [d for d in actual["diagnostics"] if d["code"] == code]

            assert_that(len(diagnostics), is_(greater_than(0)))

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "context": {"diagnostics": diagnostics},
                }
            )

            expected = [
                {
                    "title": command["title"],
                    "kind": "quickfix",
                    "diagnostics": [d],
                    "command": command,
                }
                for d in diagnostics
            ]

        assert_that(actual_code_actions, is_(expected))

# These have some issues
#         (
#             "W1406:redundant-u-string-prefix",
#             """
# def print_fruit():
#     print(u"Apple")""",
#             """
# def print_fruit():
#     print("Apple")"""    
#         ),
#         (
#             "W1402:anomalous-unicode-escape-in-string",
#             """
# print(b"\u%b" % b"0394")""",
#             """
# print(b"\\u%b" % b"0394")""",
#         ),
#         (
#             "E1128:assignment-from-none",
#             """
# def function():
#     return None


# f = function()""",
#             """
# def function():
#     return None


# f = function() if function() else 1""",
#         ),

@pytest.mark.parametrize(
    ("code", "contents", "new_text"),
    [
        (
            "W1401:anomalous-backslash-in-string",
            "string = '\z'",
            "string = r'\z'",
        ),
        (
            "I0021:useless-suppression",
            "# pylint: disable-next=redefined-outer-name",
            "",
        ),
        (
            "I0021:useless-suppression",
            """
fruit_counter = 0


# pylint: disable-next=redefined-outer-name
def eat(fruit_name: str):
    print(fruit_name)""",
            """
fruit_counter = 0


def eat(fruit_name: str):
    print(fruit_name)""",
        ),
        (
            "I0011:locally-disabled",
            "# pylint: disable=maybe-no-member",
            "",            
        ),
        (
            "I0011:locally-disabled",
            """
def wizard_spells(spell_book):
    # pylint: disable=maybe-no-member
    for spell in spell_book:
        print(f"Abracadabra! {spell}.")

spell_list = ["Levitation", "Invisibility", "Fireball", "Teleportation"]
wizard_spells(spell_list)""",
            """
def wizard_spells(spell_book):
    for spell in spell_book:
        print(f"Abracadabra! {spell}.")

spell_list = ["Levitation", "Invisibility", "Fireball", "Teleportation"]
wizard_spells(spell_list)""",            
        ),
        (
            "I0023:use-symbolic-message-instead",
            "# pylint: disable-next=W0621",
            "",
        ),
        (
            "I0023:use-symbolic-message-instead",
            """
fruit_name = "plum"


# pylint: disable-next=W0621
def eat(fruit_name: str):
    ...""",
            """
fruit_name = "plum"


# pylint: disable-next=redefined-outer-name
def eat(fruit_name: str):
    ...""",
        ),
        
        (
            "R0205:useless-object-inheritance",
            """
class Banana(object):
    pass""",
            """
class Banana:
    pass""",
        ),
        (
            "R0205:useless-object-inheritance",
            "class Banana(object):",
            "class Banana:",
        ),
        (
            "R1707:trailing-comma-tuple",
            "COMPASS = 'north', 'south', 'east', 'west',",
            "COMPASS = ('north', 'south', 'east', 'west')",
        ),
        (
            "R1711:useless-return",
            "return None",
            "",
        ),
        (
            "R1711:useless-return",
            """
import sys


def print_python_version():
    print(sys.version)
    return None""",
            """
import sys


def print_python_version():
    print(sys.version)""",
        ),
        (
            "R1721:unnecessary-comprehension",
            """
NUMBERS = [1, 1, 2, 2, 3, 3]

UNIQUE_NUMBERS = {number for number in NUMBERS}
""",
            """
NUMBERS = [1, 1, 2, 2, 3, 3]

UNIQUE_NUMBERS = set(NUMBERS)
""",
        ),
        (
            "R1736:unnecessary-list-index-lookup",
            """
letters = ['a', 'b', 'c']

for index, letter in enumerate(letters):
    print(letters[index])
""",
            """
letters = ['a', 'b', 'c']

for index, letter in enumerate(letters):
    print(letter)
""",
        ),
        (
            "R1729:use-a-generator",
            """
from random import randint

all([randint(-5, 5) > 0 for _ in range(10)])
any([randint(-5, 5) > 0 for _ in range(10)])
""",
            """
from random import randint

all(randint(-5, 5) > 0 for _ in range(10))
any(randint(-5, 5) > 0 for _ in range(10))
""",
        ),
        (
            "R1729:use-a-generator",
            "all([randint(-5, 5) > 0 for _ in range(10)])",
            "all(randint(-5, 5) > 0 for _ in range(10))",
        ),
        (
            "R1729:use-a-generator",
            "any([randint(-5, 5) > 0 for _ in range(10)])",
            "any(randint(-5, 5) > 0 for _ in range(10))",
        ),
        (
            "R1735:use-dict-literal",
            "empty_dict = dict()",
            "empty_dict = {}",
        ),
        (
            "R1735:use-dict-literal",
            "new_dict = dict(foo='bar')",
            "new_dict = {'foo': 'bar'}",
        ),
        (
            "R1735:use-dict-literal",
            "new_dict = dict(**another_dict)",
            "new_dict = {**another_dict}",
        ),
        (
            "E1141:dict-iter-missing-items",
            "for city, population in data:",
            "for city, population in data.items():",
        ),
        (
            "E1141:dict-iter-missing-items",
            """
data = {'Paris': 2_165_423, 'New York City': 8_804_190, 'Tokyo': 13_988_129}
for city, population in data:
    print(f"{city} has population {population}.")
""",
            """
data = {'Paris': 2_165_423, 'New York City': 8_804_190, 'Tokyo': 13_988_129}
for city, population in data.items():
    print(f"{city} has population {population}.")
""",
        ),
        (
            "E1310:bad-str-strip-call",
            "'Hello World'.strip('Hello')",
            "'Hello World'.strip('Helo')",
        ),
        (
            "E1310:bad-str-strip-call",
            "'abcbc def bacabc'.strip('abcbc ')",
            "'abcbc def bacabc'.strip('abc ')",
        ),
    ],
)
def test_edit_code_action(code, contents, new_text):
    """Tests for code actions which run a command."""
    with utils.python_file(contents, TEST_FILE_PATH.parent) as temp_file:
        uri = utils.as_uri(os.fspath(temp_file))

        actual = {}
        with session.LspSession() as ls_session:
            ls_session.initialize()

            done = Event()

            def _handler(params):
                nonlocal actual
                actual = params
                done.set()

            ls_session.set_notification_callback(session.PUBLISH_DIAGNOSTICS, _handler)

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

            # wait for some time to receive all notifications
            done.wait(TIMEOUT)

            diagnostics = [d for d in actual["diagnostics"] if d["code"] == code]

            assert_that(len(diagnostics), is_(greater_than(0)))

            actual_code_actions = ls_session.text_document_code_action(
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 1, "character": 0},
                    },
                    "context": {"diagnostics": diagnostics},
                }
            )

            expected = [
                {
                    "title": f"{LINTER}: Run string replacement",
                    "kind": "quickfix",
                    "diagnostics": [d],
                    "edit": {
                        "documentChanges": [
                            {
                                "textDocument": actual_code_actions[0]['edit']['documentChanges'][0]['textDocument'],
                                "edits": [
                                    {
                                        "range": actual_code_actions[0]['edit']['documentChanges'][0]['edits'][0]['range'],
                                        "newText": new_text,
                                    }
                                ]
                            }
                        ]
                    }
                }
                for d in diagnostics
            ]

        assert_that(actual_code_actions, is_(expected))
