import logging

from panimg.models import ImageType, PanImgFile, PostProcessorResult
from panimg.settings import DZI_TILE_SIZE

logger = logging.getLogger(__name__)


def tiff_to_dzi(*, image_files: set[PanImgFile]) -> PostProcessorResult:
    new_image_files: set[PanImgFile] = set()

    for file in image_files:
        if file.image_type == ImageType.TIFF:
            try:
                result = _create_dzi_image(tiff_file=file)
            except Exception:
                logger.warning(f"Could not create DZI for {file}")
                continue

            new_image_files |= result.new_image_files

    return PostProcessorResult(new_image_files=new_image_files)


def _create_dzi_image(*, tiff_file: PanImgFile) -> PostProcessorResult:
    import pyvips

    # Creates a dzi file and corresponding tiles in directory {pk}_files
    dzi_output = tiff_file.file.parent / str(tiff_file.image_id)

    image = pyvips.Image.new_from_file(
        str(tiff_file.file.absolute()), access="sequential"
    )

    pyvips.Image.dzsave(image, str(dzi_output), tile_size=DZI_TILE_SIZE)

    new_file = PanImgFile(
        image_id=tiff_file.image_id,
        image_type=ImageType.DZI,
        file=(dzi_output.parent / f"{dzi_output.name}.dzi").absolute(),
        directory=(dzi_output.parent / f"{dzi_output.name}_files").absolute(),
    )

    return PostProcessorResult(new_image_files={new_file})
