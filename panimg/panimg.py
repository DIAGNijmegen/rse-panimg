import logging
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Set

from panimg.exceptions import UnconsumedFilesException
from panimg.image_builders import DEFAULT_IMAGE_BUILDERS
from panimg.models import (
    PanImg,
    PanImgFile,
    PanImgFolder,
    PanImgResult,
    PostProcessorResult,
)
from panimg.post_processors import DEFAULT_POST_PROCESSORS
from panimg.types import ImageBuilder, PostProcessor

logger = logging.getLogger(__name__)


def convert(
    *,
    input_directory: Path,
    output_directory: Path,
    builders: Optional[Iterable[ImageBuilder]] = None,
    post_processors: Optional[Iterable[PostProcessor]] = None,
    recurse_subdirectories: bool = True,
) -> PanImgResult:
    new_images: Set[PanImg] = set()
    new_image_files: Set[PanImgFile] = set()
    new_folders: Set[PanImgFolder] = set()
    consumed_files: Set[Path] = set()
    file_errors: DefaultDict[Path, List[str]] = defaultdict(list)

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
        new_folders=new_folders,
        file_errors=file_errors,
        recurse_subdirectories=recurse_subdirectories,
    )

    result = _post_process(
        image_files=new_image_files,
        post_processors=post_processors
        if post_processors is not None
        else DEFAULT_POST_PROCESSORS,
    )
    new_image_files |= result.new_image_files
    new_folders |= result.new_folders

    return PanImgResult(
        new_images=new_images,
        new_image_files=new_image_files,
        new_folders=new_folders,
        consumed_files=consumed_files,
        file_errors=file_errors,
    )


def _convert_directory(
    *,
    input_directory: Path,
    output_directory: Path,
    builders: Iterable[ImageBuilder],
    consumed_files: Set[Path],
    new_images: Set[PanImg],
    new_image_files: Set[PanImgFile],
    new_folders: Set[PanImgFolder],
    file_errors: DefaultDict[Path, List[str]],
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
                new_folders=new_folders,
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
        new_folders |= builder_result.new_folders
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
    *, builder: ImageBuilder, files: Set[Path], output_directory: Path,
) -> PanImgResult:
    new_images = set()
    new_image_files: Set[PanImgFile] = set()
    consumed_files: Set[Path] = set()
    file_errors: Dict[Path, List[str]] = {}

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
        new_folders=set(),
        consumed_files=consumed_files,
        file_errors=file_errors,
    )


def _post_process(
    *, image_files: Set[PanImgFile], post_processors: Iterable[PostProcessor]
) -> PostProcessorResult:
    new_image_files: Set[PanImgFile] = set()
    new_folders: Set[PanImgFolder] = set()

    logger.info(f"Post processing {len(image_files)} image(s)")

    for processor in post_processors:
        result = processor(image_files=image_files)
        new_image_files |= result.new_image_files
        new_folders |= result.new_folders

    return PostProcessorResult(
        new_image_files=new_image_files, new_folders=new_folders
    )
