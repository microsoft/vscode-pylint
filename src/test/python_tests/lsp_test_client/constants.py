# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

TEST_ROOT = os.path.dirname(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TEST_ROOT)))
TEST_DATA = os.path.join(TEST_ROOT, "test_data")
