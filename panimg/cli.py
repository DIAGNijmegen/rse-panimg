import logging
from collections.abc import Iterable
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import click
from pydantic import RootModel

from panimg import convert, logger, post_process
from panimg.image_builders import (
    DEFAULT_IMAGE_BUILDERS,
    IMAGE_BUILDER_OPTIONS_TO_IMPLEMENTATION,
    ImageBuilderOptions,
)
from panimg.models import (
    ImageType,
    PanImgFile,
    PanImgResult,
    PostProcessorResult,
)
from panimg.post_processors import (
    DEFAULT_POST_PROCESSORS,
    POST_PROCESSOR_OPTIONS_TO_IMPLEMENTATION,
    PostProcessorOptions,
)
from panimg.types import ImageBuilder

panimg_version = version("panimg")


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(panimg_version, "-v", "--version")
def cli():
    pass


@cli.command(name="convert", short_help="Convert a directory of image files")
@click.option("-v", "--verbose", count=True)
@click.option(
    "--input-dir",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=False,
        resolve_path=True,
        path_type=Path,
    ),
    required=True,
)
@click.option(
    "--output-dir",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
        path_type=Path,
    ),
    required=True,
)
@click.option(
    "--post-processor", type=click.Choice(PostProcessorOptions), multiple=True
)
@click.option("--no-post-processing", is_flag=True, default=False)
@click.option(
    "--image-builder", type=click.Choice(ImageBuilderOptions), multiple=True
)
def convert_cli(
    *,
    verbose: int,
    input_dir: Path,
    output_dir: Path,
    post_processor: tuple[PostProcessorOptions],
    no_post_processing: bool,
    image_builder: tuple[ImageBuilderOptions],
):
    _setup_verbosity(level=verbose)

    if output_dir.exists():
        raise click.exceptions.UsageError(
            f"Output directory {output_dir} already exists"
        )
    else:
        output_dir.mkdir(parents=True)

    if post_processor and no_post_processing:
        raise click.ClickException(
            "--no-post-processing and --post-processor cannot be used together"
        )
    elif no_post_processing:
        processors = []
    elif post_processor:
        processors = [
            POST_PROCESSOR_OPTIONS_TO_IMPLEMENTATION[processor]
            for processor in post_processor
        ]
    else:
        processors = DEFAULT_POST_PROCESSORS

    if image_builder:
        builders: Iterable[ImageBuilder] = [
            IMAGE_BUILDER_OPTIONS_TO_IMPLEMENTATION[builder]
            for builder in image_builder
        ]
    else:
        builders = DEFAULT_IMAGE_BUILDERS

    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        builders=builders,
        post_processors=processors,
    )

    print(RootModel[PanImgResult](result).model_dump_json())


@cli.command(name="post-process", short_help="Post process image files")
@click.option("-v", "--verbose", count=True)
@click.option("--image-id", type=UUID, required=True)
@click.option("--image-type", type=click.Choice(ImageType), required=True)
@click.option(
    "--input-file",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=False,
        resolve_path=True,
        path_type=Path,
    ),
    required=True,
)
@click.option(
    "--post-processor", type=click.Choice(PostProcessorOptions), multiple=True
)
def post_process_cli(
    *,
    verbose: int,
    image_id: UUID,
    image_type: ImageType,
    input_file: Path,
    post_processor: tuple[PostProcessorOptions],
):
    _setup_verbosity(level=verbose)

    if post_processor:
        processors = [
            POST_PROCESSOR_OPTIONS_TO_IMPLEMENTATION[processor]
            for processor in post_processor
        ]
    else:
        processors = DEFAULT_POST_PROCESSORS

    result = post_process(
        image_files={
            PanImgFile(
                image_id=image_id, image_type=image_type, file=input_file
            )
        },
        post_processors=processors,
    )

    print(RootModel[PostProcessorResult](result).model_dump_json())


def _setup_verbosity(*, level: int):
    handler = logging.StreamHandler()

    if level == 0:
        logger.setLevel(logging.WARNING)
        handler.setLevel(logging.WARNING)
    elif level == 1:
        logger.setLevel(logging.INFO)
        handler.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)

    logger.addHandler(handler)
