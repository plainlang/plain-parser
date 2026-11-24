import os

import pytest


@pytest.fixture
def get_test_data_path():
    base = os.path.dirname(os.path.abspath(__file__))

    def resolve(relative: str) -> str:
        return os.path.join(base, relative)

    return resolve
