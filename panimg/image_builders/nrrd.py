import re
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK

from panimg.exceptions import UnconsumedFilesException
from panimg.models import SimpleITKImage

MAGIC_REGEX = re.compile("NRRD([0-9]{4})")
DATAFILE_REGEX = re.compile(r"data\s?file:", flags=re.IGNORECASE)

# Arbitrary maximum lengths to prevent overflow attacks
MAX_HEADER_LINES = 10000
MAX_HEADER_LINE_LENGTH = 10000


class InvalidNrrdFileError(Exception):
    def __init__(self, message: str = "Not a NRRD image file"):
        super().__init__(message)


def verify_single_file_nrrd(file: Path) -> bool:
    """
    Reads a file and raises an InvalidNrrdFileError if that file is not a NRRD file.
    Returns True if the file is a valid NRRD file without external data file (data
    embedded in the same file). Returns False if the file is valid NRRD file but
    has one or more external data files (detached header mode).
    """
    with file.open("rb") as fp:
        # Read first 8 characters to check whether this is a NRRD file
        try:
            preamble = fp.read(8).decode("ASCII")
        except UnicodeDecodeError as e:
            raise InvalidNrrdFileError from e

        match = MAGIC_REGEX.fullmatch(preamble)
        if match is None:
            raise InvalidNrrdFileError

        # Check whether we support this version of the NRRD format
        nrrd_version = int(match.group(1))
        if nrrd_version < 1 or nrrd_version > 5:
            raise InvalidNrrdFileError("File format not supported")

        # Discard rest of preamble line
        fp.readline(MAX_HEADER_LINE_LENGTH)

        # Read rest of the header, searching for external data files
        for _ in range(MAX_HEADER_LINES):
            try:
                line = (
                    fp.readline(MAX_HEADER_LINE_LENGTH).decode("ASCII").strip()
                )
            except UnicodeDecodeError:
                break  # header cannot contain non-ASCII content

            if len(line) == 0:
                break  # empty line marks the end of the file/header

            if DATAFILE_REGEX.match(line):
                return False
        else:
            raise InvalidNrrdFileError("Header too long")

    return True


def format_error(message: str) -> str:
    return f"NRRD image builder: {message}"


def image_builder_nrrd(*, files: Set[Path],) -> Iterator[SimpleITKImage]:
    """
    Constructs image objects from files in NRRD format (nrrd)

    The file format also supports detached headers, where header and data are
    stored in separate files (typically the file extension of the header is nhdr).
    This format is currently not supported since determining which files were
    consumed is complicated.

    Parameters
    ----------
    files
        Path to images that were uploaded during an upload session.

    Returns
    -------
    An `ImageBuilder` object consisting of:
     - a list of filenames for all files consumed by the image builder
     - a list of detected images
     - a list files associated with the detected images
     - path->error message map describing what is wrong with a given file
    """
    file_errors: DefaultDict[Path, List[str]] = defaultdict(list)

    for file in files:
        try:
            if verify_single_file_nrrd(file):
                reader = SimpleITK.ImageFileReader()
                reader.SetImageIO("NrrdImageIO")
                reader.SetFileName(str(file.absolute()))
                img: SimpleITK.Image = reader.Execute()
            else:
                raise InvalidNrrdFileError(
                    "NRRD files with detached headers are not supported"
                )
        except InvalidNrrdFileError as e:
            file_errors[file].append(format_error(str(e)))
        except RuntimeError:
            file_errors[file].append(
                format_error("Not a valid NRRD image file")
            )
        else:
            yield SimpleITKImage(
                image=img,
                name=file.name,
                consumed_files={file},
                spacing_valid=True,
            )

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
