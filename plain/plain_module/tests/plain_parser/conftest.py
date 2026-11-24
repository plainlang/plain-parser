import pytest
from plain_parser_helpers import Workspace


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path)
