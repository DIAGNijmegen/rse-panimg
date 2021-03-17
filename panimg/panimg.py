from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, List, Optional, Set

from panimg.image_builders import DEFAULT_IMAGE_BUILDERS
from panimg.models import PanImg, PanImgFile, PanImgFolder, PanImgResult
from panimg.types import ImageBuilder, PostProcessor


def convert(
    *,
    input_directory: Path,
    output_directory: Path,
    builders: Optional[Iterable[ImageBuilder]] = None,
    post_processors: Optional[Iterable[PostProcessor]] = None,
    created_image_prefix: str = "",
) -> PanImgResult:
    new_images: Set[PanImg] = set()
    new_image_files: Set[PanImgFile] = set()
    new_folders: Set[PanImgFolder] = set()
    consumed_files: Set[Path] = set()
    file_errors: DefaultDict[Path, List[str]] = defaultdict(list)

    _convert_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        builders=builders if builders is not None else DEFAULT_IMAGE_BUILDERS,
        consumed_files=consumed_files,
        new_images=new_images,
        new_image_files=new_image_files,
        new_folders=new_folders,
        file_errors=file_errors,
        created_image_prefix=created_image_prefix,
    )

    if post_processors is not None:
        new_image_files |= _post_process(
            image_files=new_image_files, post_processors=post_processors
        )

    return PanImgResult(
        new_images=new_images,
        new_image_files=new_image_files,
        new_folders=new_folders,
        consumed_files=consumed_files,
        file_errors={**file_errors},
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
    created_image_prefix: str = "",
):
    input_directory = Path(input_directory).resolve()
    output_directory = Path(output_directory).resolve()

    output_directory.mkdir(exist_ok=True)

    files = set()
    for o in Path(input_directory).iterdir():
        if o.is_dir():
            _convert_directory(
                input_directory=input_directory / o,
                output_directory=output_directory / o,
                builders=builders,
                consumed_files=consumed_files,
                new_images=new_images,
                new_image_files=new_image_files,
                new_folders=new_folders,
                file_errors=file_errors,
                created_image_prefix=created_image_prefix,
            )
        elif o.is_file():
            files.add(o)

    for builder in builders:
        builder_result = builder(
            files=files - consumed_files,
            output_directory=output_directory,
            created_image_prefix=created_image_prefix,
        )

        new_images |= builder_result.new_images
        new_image_files |= builder_result.new_image_files
        new_folders |= builder_result.new_folders
        consumed_files |= builder_result.consumed_files

        for filepath, errors in builder_result.file_errors.items():
            file_errors[filepath].extend(errors)


def _post_process(
    *, image_files: Set[PanImgFile], post_processors: Iterable[PostProcessor]
) -> Set[PanImgFile]:
    new_image_files: Set[PanImgFile] = set()

    for processor in post_processors:
        new_image_files |= processor(image_files=image_files)

    return new_image_files
