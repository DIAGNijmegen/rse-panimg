from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import SimpleITK
import numpy as np
from construct.core import (
    Float64l,
    Int8ul,
    PaddedString,
    StreamError,
    Struct,
)
from oct_converter.readers import E2E, FDA, FDS

from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.models import SimpleITKImage


def format_error(message: str) -> str:
    return f"OCT image builder: {message}"


def create_itk_oct_volume(file, volume, oct_voxel_spacing, eye_choice):
    img_array = np.array(volume)
    img = SimpleITK.GetImageFromArray(img_array, isVector=False)
    [st, _, sl] = img_array.shape
    img.SetSpacing(
        [
            oct_voxel_spacing["xmm"] / st,
            oct_voxel_spacing["ymm"],
            oct_voxel_spacing["zmm"] / sl,
        ]
    )
    if eye_choice == "L":
        img.eye_choice = "OS"
    elif eye_choice == "R":
        img.eye_choice = "OD"
    else:
        img.eye_choice = "U"
    return SimpleITKImage(
        image=img,
        name=file.name,
        consumed_files={file},
        spacing_valid=True,
        oct_image=True,
    )


def extract_voxel_spacing(img):
    voxel_spacing_meta_data = Struct(
        "unknown" / PaddedString(12, "utf16"),
        "xmm" / Float64l,
        "zmm" / Float64l,
        "y" / Float64l,
        "unknown6" / Float64l,
        "unknown7" / Float64l,
        "unknown8" / Int8ul,
    )
    with open(img.filepath, "rb") as f:
        chunk_location, chunk_size = img.chunk_dict[b"@PARAM_SCAN_04"]
        f.seek(chunk_location)
        raw = f.read(chunk_size)
        spacing = voxel_spacing_meta_data.parse(raw)
        oct_voxel_spacing = dict.fromkeys(["xmm", "zmm", "ymm"], None)
        oct_voxel_spacing["xmm"] = spacing.xmm
        oct_voxel_spacing["zmm"] = spacing.zmm
        oct_voxel_spacing["ymm"] = spacing.y / 1000

    return oct_voxel_spacing


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
                oct_voxel_spacing = extract_voxel_spacing(img)
            elif file.suffix == ".fda":
                img = FDA(file)
                oct_voxel_spacing = extract_voxel_spacing(img)
            elif file.suffix == ".e2e":
                img = E2E(file)
                oct_voxel_spacing = dict.fromkeys(["xmm", "zmm", "ymm"], None)
                oct_voxel_spacing["xmm"] = 6
                oct_voxel_spacing["zmm"] = 4.5
                oct_voxel_spacing["ymm"] = 0.0039
            else:
                raise ValueError

            oct_volume = img.read_oct_volume()

            if file.suffix == ".e2e":
                for volume in oct_volume:
                    eye_choice = volume.laterality
                    yield create_itk_oct_volume(
                        file, volume.volume, oct_voxel_spacing, eye_choice
                    )
            else:
                eye_choice = None
                yield create_itk_oct_volume(
                    file, oct_volume.volume, oct_voxel_spacing, eye_choice
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
