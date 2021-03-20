import shutil
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Set
from uuid import uuid4

from panimg.exceptions import UnconsumedFilesException
from panimg.image_builders import DEFAULT_IMAGE_BUILDERS
from panimg.image_builders.utils import convert_itk_to_internal
from panimg.models import (
    ImageType,
    PanImg,
    PanImgFile,
    PanImgFolder,
    PanImgResult,
    PostProcessorResult,
    SimpleITKImage,
    TIFFImage,
)
from panimg.post_processors import DEFAULT_POST_PROCESSORS
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
        builder_result = _build_files(
            builder=builder,
            files=files - consumed_files,
            created_image_prefix=created_image_prefix,
            output_directory=output_directory,
        )

        new_images |= builder_result.new_images
        new_image_files |= builder_result.new_image_files
        new_folders |= builder_result.new_folders
        consumed_files |= builder_result.consumed_files

        for filepath, errors in builder_result.file_errors.items():
            file_errors[filepath].extend(errors)


def _build_files(
    *,
    builder: ImageBuilder,
    files: Set[Path],
    output_directory: Path,
    created_image_prefix: str = "",
) -> PanImgResult:
    new_images = set()
    new_image_files: Set[PanImgFile] = set()
    consumed_files: Set[Path] = set()
    file_errors: Dict[Path, List[str]] = {}

    try:
        for result in builder(files=files):
            if created_image_prefix:
                name = f"{created_image_prefix}-{result.name}"
            else:
                name = result.name

            if isinstance(result, SimpleITKImage):
                n_image, n_image_files = convert_itk_to_internal(
                    simple_itk_image=result.image,
                    name=name,
                    use_spacing=result.use_spacing,
                    output_directory=output_directory,
                )
            elif isinstance(result, TIFFImage):
                pk = uuid4()

                output_file = (
                    output_directory
                    / result.name
                    / f"{pk}{result.file.suffix}"
                )
                output_file.parent.mkdir()

                shutil.copy(src=result.file, dst=output_file)

                n_image = PanImg(
                    pk=pk,
                    name=result.name,
                    width=result.width,
                    height=result.height,
                    depth=1,
                    resolution_levels=result.resolution_levels,
                    color_space=result.color_space,
                    voxel_width_mm=result.voxel_width_mm,
                    voxel_height_mm=result.voxel_height_mm,
                    voxel_depth_mm=result.voxel_depth_mm,
                    timepoints=None,
                    window_center=None,
                    window_width=None,
                )
                n_image_files = {
                    PanImgFile(
                        image_id=n_image.pk,
                        image_type=ImageType.TIFF,
                        file=output_file.absolute(),
                    )
                }
            else:
                raise TypeError(
                    f"Unknown result type {type(result)} from {builder}"
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

    for processor in post_processors:
        result = processor(image_files=image_files)
        new_image_files |= result.new_image_files
        new_folders |= result.new_folders

    return PostProcessorResult(
        new_image_files=new_image_files, new_folders=new_folders
    )
