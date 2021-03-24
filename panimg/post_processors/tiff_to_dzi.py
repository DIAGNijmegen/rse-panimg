import logging
from typing import Set

from panimg.models import (
    ImageType,
    PanImgFile,
    PanImgFolder,
    PostProcessorResult,
)
from panimg.settings import DZI_TILE_SIZE

try:
    import pyvips
except OSError:
    pyvips = False

logger = logging.getLogger(__name__)


def tiff_to_dzi(*, image_files: Set[PanImgFile]) -> PostProcessorResult:
    if pyvips is False:
        raise ImportError(
            f"Could not import pyvips, which is required for the "
            f"{__name__} post processor. Either ensure that libvips-dev "
            f"is installed or remove {__name__} from your list of post "
            f"processors."
        )

    new_image_files: Set[PanImgFile] = set()
    new_folders: Set[PanImgFolder] = set()

    for file in image_files:
        if file.image_type == ImageType.TIFF:
            try:
                result = _create_dzi_image(tiff_file=file)
            except Exception as e:
                logger.warning(f"Could not create DZI for {file}: {e}")
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
        file=(dzi_output.parent / f"{dzi_output.name}.dzi").absolute(),
    )

    new_folder = PanImgFolder(
        image_id=tiff_file.image_id,
        folder=(dzi_output.parent / f"{dzi_output.name}_files").absolute(),
    )

    return PostProcessorResult(
        new_image_files={new_file}, new_folders={new_folder}
    )
