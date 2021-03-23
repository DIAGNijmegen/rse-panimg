from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK
import numpy as np
from PIL import Image
from PIL.Image import DecompressionBombError

from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.models import SimpleITKImage


def format_error(message: str) -> str:
    return f"Fallback image builder: {message}"


def image_builder_fallback(*, files: Set[Path]) -> Iterator[SimpleITKImage]:
    """
    Constructs image objects by inspecting files in a directory.

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
            img = Image.open(file)

            if img.format.lower() not in ["jpeg", "png"]:
                raise ValidationError(
                    f"Unsupported image format: {img.format}"
                )

            img_array = np.array(img)
            is_vector = img.mode != "L"
            img = SimpleITK.GetImageFromArray(img_array, isVector=is_vector)

            yield SimpleITKImage(
                image=img,
                name=file.name,
                consumed_files={file},
                spacing_valid=False,
            )
        except (OSError, ValidationError, DecompressionBombError):
            file_errors[file].append(format_error("Not a valid image file"))

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
