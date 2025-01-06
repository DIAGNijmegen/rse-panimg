import logging
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import DefaultDict

from panimg.exceptions import UnconsumedFilesException
from panimg.image_builders import DEFAULT_IMAGE_BUILDERS
from panimg.models import PanImg, PanImgFile, PanImgResult, PostProcessorResult
from panimg.post_processors import DEFAULT_POST_PROCESSORS
from panimg.types import ImageBuilder, PostProcessor

logger = logging.getLogger(__name__)


def convert(
    *,
    input_directory: Path,
    output_directory: Path,
    builders: Iterable[ImageBuilder] | None = None,
    post_processors: Iterable[PostProcessor] | None = None,
    recurse_subdirectories: bool = True,
) -> PanImgResult:
    new_images: set[PanImg] = set()
    new_image_files: set[PanImgFile] = set()
    consumed_files: set[Path] = set()
    file_errors: DefaultDict[Path, list[str]] = defaultdict(list)

    builders = builders if builders is not None else DEFAULT_IMAGE_BUILDERS

    builder_names = ", ".join(str(b) for b in builders)
    logger.info(f"Using builders {builder_names}")

    _convert_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        builders=builders,
        consumed_files=consumed_files,
        new_images=new_images,
        new_image_files=new_image_files,
        file_errors=file_errors,
        recurse_subdirectories=recurse_subdirectories,
    )

    result = post_process(
        image_files=new_image_files,
        post_processors=(
            post_processors
            if post_processors is not None
            else DEFAULT_POST_PROCESSORS
        ),
    )
    new_image_files |= result.new_image_files

    return PanImgResult(
        new_images=new_images,
        new_image_files=new_image_files,
        consumed_files=consumed_files,
        file_errors=file_errors,
    )


def _convert_directory(
    *,
    input_directory: Path,
    output_directory: Path,
    builders: Iterable[ImageBuilder],
    consumed_files: set[Path],
    new_images: set[PanImg],
    new_image_files: set[PanImgFile],
    file_errors: DefaultDict[Path, list[str]],
    recurse_subdirectories: bool = True,
):
    input_directory = Path(input_directory).resolve()
    output_directory = Path(output_directory).resolve()

    output_directory.mkdir(exist_ok=True)

    files = set()
    for o in Path(input_directory).iterdir():
        if o.is_dir() and recurse_subdirectories:
            _convert_directory(
                input_directory=input_directory
                / o.relative_to(input_directory),
                output_directory=output_directory
                / o.relative_to(input_directory),
                builders=builders,
                consumed_files=consumed_files,
                new_images=new_images,
                new_image_files=new_image_files,
                file_errors=file_errors,
                recurse_subdirectories=recurse_subdirectories,
            )
        elif o.is_file():
            files.add(o)

    logger.info(f"Converting directory {input_directory}")

    for builder in builders:
        builder_files = files - consumed_files

        if len(builder_files) == 0:
            return

        logger.debug(f"Processing {len(builder_files)} file(s) with {builder}")

        builder_result = _build_files(
            builder=builder,
            files=builder_files,
            output_directory=output_directory,
        )

        new_images |= builder_result.new_images
        new_image_files |= builder_result.new_image_files
        consumed_files |= builder_result.consumed_files

        if builder_result.consumed_files:
            logger.info(
                f"{builder} created {len(builder_result.new_images)} "
                f"new images(s) from {len(builder_result.consumed_files)} file(s)"
            )
        else:
            logger.debug(f"No files consumed by {builder}")

        for filepath, errors in builder_result.file_errors.items():
            file_errors[filepath].extend(errors)


def _build_files(
    *, builder: ImageBuilder, files: set[Path], output_directory: Path
) -> PanImgResult:
    new_images = set()
    new_image_files: set[PanImgFile] = set()
    consumed_files: set[Path] = set()
    file_errors: dict[Path, list[str]] = {}

    try:
        for result in builder(files=files):
            n_image, n_image_files = result.save(
                output_directory=output_directory
            )

            new_images.add(n_image)
            new_image_files |= n_image_files
            consumed_files |= result.consumed_files

    except UnconsumedFilesException as e:
        file_errors = e.file_errors

    return PanImgResult(
        new_images=new_images,
        new_image_files=new_image_files,
        consumed_files=consumed_files,
        file_errors=file_errors,
    )


def post_process(
    *, image_files: set[PanImgFile], post_processors: Iterable[PostProcessor]
) -> PostProcessorResult:
    """
    Run a set of post processors on a set of image files

    Post processors add new files and directories to existing images,
    such as DZI creation for TIFF images, or thumbnail generation.
    They do not produce new image entities.
    """
    new_image_files: set[PanImgFile] = set()

    logger.info(f"Post processing {len(image_files)} image(s)")

    existing_ids = {f.image_id for f in image_files}

    for processor in post_processors:
        result = processor(image_files=image_files)

        # Filter out any new image ids
        filtered_files = {
            f for f in result.new_image_files if f.image_id in existing_ids
        }

        excluded_files = result.new_image_files - filtered_files

        if excluded_files:
            logger.warning(f"Ignoring: {excluded_files}")

        new_image_files |= filtered_files

    return PostProcessorResult(new_image_files=new_image_files)
