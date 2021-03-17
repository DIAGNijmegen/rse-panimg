import logging
from typing import Set

import pyvips

from panimg.models import (
    ImageType,
    PanImgFile,
    PanImgFolder,
    PostProcessorResult,
)
from panimg.settings import DZI_TILE_SIZE

logger = logging.getLogger(__name__)


def tiff_to_dzi(*, image_files: Set[PanImgFile]) -> PostProcessorResult:
    new_image_files: Set[PanImgFile] = set()
    new_folders: Set[PanImgFolder] = set()

    for tiff_file in image_files:
        if tiff_file.image_type == ImageType.TIFF:
            try:
                result = _create_dzi_image(tiff_file=tiff_file)
            except Exception as e:
                logger.warning(f"Could not create DZI for {tiff_file}: {e}")
                continue

            new_image_files |= result.new_image_files
            new_folders |= result.new_folders

    return PostProcessorResult(
        new_image_files=new_image_files, new_folders=new_folders
    )


def _create_dzi_image(*, tiff_file: PanImgFile) -> PostProcessorResult:
    # Creates a dzi file and corresponding tiles in folder {pk}_files
    dzi_output = tiff_file.file.parent / str(tiff_file.image_id)

    image = pyvips.Image.new_from_file(
        str(tiff_file.file.absolute()), access="sequential"
    )

    pyvips.Image.dzsave(image, str(dzi_output), tile_size=DZI_TILE_SIZE)

    new_file = PanImgFile(
        image_id=tiff_file.image_id,
        image_type=ImageType.DZI,
        file=dzi_output.parent / f"{dzi_output.name}.dzi",
    )

    new_folder = PanImgFolder(
        image_id=tiff_file.image_id,
        folder=dzi_output.parent / f"{dzi_output.name}_files",
    )

    return PostProcessorResult(
        new_image_files={new_file}, new_folders={new_folder}
    )
