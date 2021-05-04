from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK
import numpy as np
from construct.core import StreamError
from oct_converter.readers import E2E, FDA, FDS

from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.models import SimpleITKImage


def format_error(message: str) -> str:
    return f"OCT image builder: {message}"


def image_builder_oct(*, files: Set[Path]) -> Iterator[SimpleITKImage]:
    """
    Constructs OCT image objects by inspecting files in a directory by using
    OCT-converter PyPI library.

    Parameters
    ----------
    path
        Path to a directory that contains all images that were uploaded during
        an upload session.

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
            if file.suffix == ".fds":
                img = FDS(file)
            elif file.suffix == ".fda":
                img = FDA(file)
            elif file.suffix == ".e2e":
                img = E2E(file)
            else:
                raise ValueError

            oct_volume = img.read_oct_volume()
            if file.suffix == ".e2e":
                for volume in oct_volume:
                    np_array = volume.volume
                    img_array = np.array(np_array)
                    img = SimpleITK.GetImageFromArray(
                        img_array, isVector=False
                    )
                    yield SimpleITKImage(
                        image=img,
                        name=file.name,
                        consumed_files={file},
                        spacing_valid=False,
                    )
            else:
                np_array = oct_volume.volume
                img_array = np.array(np_array)
                img = SimpleITK.GetImageFromArray(img_array, isVector=False)
                yield SimpleITKImage(
                    image=img,
                    name=file.name,
                    consumed_files={file},
                    spacing_valid=False,
                )
        except (OSError, ValidationError, StreamError, ValueError, IndexError):
            file_errors[file].append(
                format_error(
                    "Not a valid OCT file "
                    "(supported formats: .fds,.fda,.e2e)"
                )
            )

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
