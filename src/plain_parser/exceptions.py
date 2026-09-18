class PlainSyntaxError(Exception):
    pass


class UnsupportedBase64Content(Exception):
    pass


class UnsupportedResourceType(Exception):
    pass


class InvalidFridArgument(Exception):
    pass


class InvalidLiquidVariableName(Exception):
    pass


class ModuleDoesNotExistError(Exception):
    pass


class MissingFunctionalitiesError(Exception):
    """Raised when a module to be rendered has no functionalities specified at all."""

    pass


class ImportedModuleWithFunctionalitiesError(Exception):
    """Raised when a module brought in via ``import`` contains functional specs.

    This is a usage error, not a syntax error: the module is syntactically valid
    and would be fine as a render target, but functionalities are not allowed in
    the import role.
    """

    pass
