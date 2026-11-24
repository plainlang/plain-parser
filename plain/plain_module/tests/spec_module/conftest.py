import pytest
from spec_module_helpers import Project


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path)
