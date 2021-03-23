from pathlib import Path
from typing import Dict, List


class ValidationError(Exception):
    pass


class UnconsumedFilesException(Exception):
    """
    Raised on completion of an image builder and there are unconsumed files.
    Contains a dictionary with a map of the errors encountered when loading
    the unconsumed file.
    """

    def __init__(self, *args, file_errors: Dict[Path, List[str]]):
        super().__init__(*args)
        self.file_errors = file_errors


class MissingLibraryException(RuntimeError):
    pass


class DeferredMissingLibraryException:
    """
    Replaces a module that is not working due to a missing external
    dependency (such as OpenSlide) and raises an exception as soon as
    the module is used for the first time (i.e., when an object in the
    module is accessed).
    """

    def __init__(self, *args):
        self.args = args

    def __getattr__(self, item):
        raise MissingLibraryException(*self.args)
