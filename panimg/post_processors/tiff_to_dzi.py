from typing import Set

import pyvips

from panimg.models import ImageType, PanImgFile
from panimg.settings import DZI_TILE_SIZE


def tiff_to_dzi(*, image_files: Set[PanImgFile]) -> Set[PanImgFile]:
    new_image_files = set()

    for tiff_file in image_files:
        try:
            new_image_files.add(_create_dzi_image(tiff_file=tiff_file))
        except RuntimeError:
            continue

    return new_image_files


def _create_dzi_image(*, tiff_file: PanImgFile) -> PanImgFile:
    # Creates a dzi file and corresponding tiles in folder {pk}_files
    dzi_output = tiff_file.file.parent / str(tiff_file.image_id)

    try:
        image = pyvips.Image.new_from_file(
            str(tiff_file.file.absolute()), access="sequential"
        )
        pyvips.Image.dzsave(image, str(dzi_output), tile_size=DZI_TILE_SIZE)
    except Exception as e:
        raise RuntimeError(f"Image can't be converted to dzi: {e}")

    return PanImgFile(
        image_id=tiff_file.image_id,
        image_type=ImageType.DZI,
        file=dzi_output.parent / (dzi_output.name + ".dzi"),
    )
