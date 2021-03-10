from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import SimpleITK
import numpy as np
from PIL import Image
from PIL.Image import DecompressionBombError

from panimg.exceptions import ValidationError
from panimg.image_builders.utils import convert_itk_to_internal
from panimg.models import PanImgFile, PanImgResult


def format_error(message: str) -> str:
    return f"Fallback image builder: {message}"


def image_builder_fallback(
    *, files: Set[Path], output_directory: Path, **_
) -> PanImgResult:
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
    errors: Dict[Path, List[str]] = defaultdict(list)
    new_images = set()
    new_image_files: Set[PanImgFile] = set()
    consumed_files = set()
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
            n_image, n_image_files = convert_itk_to_internal(
                simple_itk_image=img,
                name=file.name,
                use_spacing=False,
                output_directory=output_directory,
            )
            new_images.add(n_image)
            new_image_files |= set(n_image_files)
            consumed_files.add(file)
        except (IOError, ValidationError, DecompressionBombError):
            errors[file].append(format_error("Not a valid image file"))

    return PanImgResult(
        consumed_files=consumed_files,
        file_errors=errors,
        new_images=new_images,
        new_image_files=new_image_files,
        new_folders=set(),
    )
