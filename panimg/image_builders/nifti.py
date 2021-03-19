from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK

from panimg.models import FileLoaderResult


def format_error(message: str) -> str:
    return f"NifTI image builder: {message}"


def image_builder_nifti(
    *, files: Set[Path], file_errors: DefaultDict[Path, List[str]]
) -> Iterator[FileLoaderResult]:
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
    for file in files:
        if not (file.name.endswith(".nii") or file.name.endswith(".nii.gz")):
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

        yield FileLoaderResult(
            image=img, name=file.name, consumed_files={file}, use_spacing=True
        )
