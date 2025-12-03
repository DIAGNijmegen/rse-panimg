from pathlib import Path


class ValidationError(Exception):
    pass


class UnconsumedFilesException(Exception):  # noqa: N818
    """
    Raised on completion of an image builder and there are unconsumed files.
    Contains a dictionary with a map of the errors encountered when loading
    the unconsumed file.
    """

    def __init__(  # noqa: B042
        self, *args, file_errors: dict[Path, list[str]]
    ):
        super().__init__(*args)
        self.file_errors = file_errors
