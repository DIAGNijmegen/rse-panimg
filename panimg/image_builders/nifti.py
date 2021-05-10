from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK

from panimg.exceptions import UnconsumedFilesException
from panimg.models import SimpleITKImage


def format_error(message: str) -> str:
    return f"NifTI image builder: {message}"


def image_builder_nifti(*, files: Set[Path],) -> Iterator[SimpleITKImage]:
    """
    Constructs image objects from files in NifTI format (nii/nii.gz)

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
        if not (file.name.endswith(".nii") or file.name.endswith(".nii.gz")):
            file_errors[file].append(format_error("Not a NifTI image file"))
            continue

        try:
            reader = SimpleITK.ImageFileReader()
            reader.SetImageIO("NiftiImageIO")
            reader.SetFileName(str(file.absolute()))
            img: SimpleITK.Image = reader.Execute()
        except RuntimeError:
            file_errors[file].append(
                format_error("Not a valid NifTI image file")
            )
            continue

        yield SimpleITKImage(
            image=img,
            name=file.name,
            consumed_files={file},
            spacing_valid=True,
        )

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
