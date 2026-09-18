import pytest

from plain_parser import exceptions


@pytest.mark.parametrize(
    "name",
    [
        "PlainSyntaxError",
        "UnsupportedBase64Content",
        "UnsupportedResourceType",
        "InvalidFridArgument",
        "InvalidLiquidVariableName",
        "ModuleDoesNotExistError",
        "MissingFunctionalitiesError",
        "ImportedModuleWithFunctionalitiesError",
    ],
)
def test_parser_exceptions_exist_and_are_exceptions(name):
    cls = getattr(exceptions, name)
    assert issubclass(cls, Exception)
