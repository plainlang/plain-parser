"""Error classes raised by plain-parser."""


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
    pass


class ImportedModuleWithFunctionalitiesError(Exception):
    pass


class MissingTestPlainFileError(Exception):
    pass
