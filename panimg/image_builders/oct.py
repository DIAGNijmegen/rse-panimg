from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set, Tuple, Union

import SimpleITK
import numpy as np
from construct.core import (
    Float64l,
    Int8ul,
    PaddedString,
    StreamError,
    Struct,
)
from pydantic import BaseModel

from panimg.contrib.oct_converter.readers import E2E, FDA, FDS
from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.models import EyeChoice, SimpleITKImage


def format_error(message: str) -> str:
    return f"OCT image builder: {message}"


LATERALITY_TO_EYE_CHOICE = defaultdict(
    lambda: EyeChoice.UNKNOWN,
    {"L": EyeChoice.OCULUS_SINISTER, "R": EyeChoice.OCULUS_DEXTER},
)

OCT_CONVERTER_TYPE = Union[FDS, FDA, E2E]


class OctSliceSpacing(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


def create_itk_images(
    *, file, oct_volume, fundus_image, oct_slice_size,
):
    if file.suffix == ".e2e":
        for volume in oct_volume:
            eye_choice = LATERALITY_TO_EYE_CHOICE[volume.laterality]
            itk_oct = create_itk_oct_volume(
                file=file,
                volume=volume.volume,
                oct_slice_size=oct_slice_size,
                eye_choice=eye_choice,
            )
        for image in fundus_image:
            eye_choice = LATERALITY_TO_EYE_CHOICE[image.laterality]
            itk_fundus = create_itk_fundus_image(
                file=file,
                image=image.image,
                eye_choice=eye_choice,
                is_vector=False,
            )
    else:
        eye_choice = LATERALITY_TO_EYE_CHOICE[oct_volume.laterality]
        img_array = fundus_image.image.astype(np.uint8)
        img_array = img_array[:, :, ::-1]
        itk_oct = create_itk_oct_volume(
            file=file,
            volume=oct_volume.volume,
            oct_slice_size=oct_slice_size,
            eye_choice=eye_choice,
        )
        itk_fundus = create_itk_fundus_image(
            file=file, image=img_array, eye_choice=eye_choice, is_vector=True
        )
    return itk_oct, itk_fundus


def create_itk_oct_volume(*, file, volume, oct_slice_size, eye_choice):
    img_array = np.array(volume)
    img = SimpleITK.GetImageFromArray(img_array, isVector=False)
    [st, _, sl] = img_array.shape
    img.SetSpacing(
        [
            oct_slice_size.x_mm / sl,
            oct_slice_size.y_mm,
            oct_slice_size.z_mm / st,
        ]
    )
    return SimpleITKImage(
        image=img,
        name=file.name,
        consumed_files={file},
        spacing_valid=True,
        eye_choice=eye_choice,
    )


def create_itk_fundus_image(*, file, image, eye_choice, is_vector):
    img = SimpleITK.GetImageFromArray(image, isVector=is_vector)
    return SimpleITKImage(
        image=img,
        name=file.stem + "_fundus" + file.suffix,
        consumed_files={file},
        spacing_valid=False,
        eye_choice=eye_choice,
    )


def extract_slice_size(*, img: Union[FDS, FDA]) -> OctSliceSpacing:
    slice_size_meta_data = Struct(
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
        spacing = slice_size_meta_data.parse(raw)
        return OctSliceSpacing(
            x_mm=spacing.xmm, y_mm=spacing.y / 1000.0, z_mm=spacing.zmm
        )


def _get_image(*, file: Path) -> Tuple[OCT_CONVERTER_TYPE, OctSliceSpacing]:
    if file.suffix == ".fds":
        fds_img = FDS(file)
        oct_slice_size = extract_slice_size(img=fds_img)
        return fds_img, oct_slice_size
    elif file.suffix == ".fda":
        fda_img = FDA(file)
        oct_slice_size = extract_slice_size(img=fda_img)
        return fda_img, oct_slice_size
    elif file.suffix == ".e2e":
        e2e_img = E2E(file)
        # TODO Document these size choices
        oct_slice_size = OctSliceSpacing(x_mm=6, y_mm=0.0039, z_mm=4.5)
        return e2e_img, oct_slice_size
    else:
        raise ValueError


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
            img, oct_slice_size = _get_image(file=file)

            oct_volume = img.read_oct_volume()
            fundus_image = img.read_fundus_image()

            itk_images = create_itk_images(
                file=file,
                oct_volume=oct_volume,
                fundus_image=fundus_image,
                oct_slice_size=oct_slice_size,
            )

            yield from itk_images

        except (OSError, ValidationError, StreamError, ValueError, IndexError):
            file_errors[file].append(
                format_error(
                    "Not a valid OCT file (supported formats: .fds,.fda,.e2e)"
                )
            )

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
