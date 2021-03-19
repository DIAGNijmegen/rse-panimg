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
