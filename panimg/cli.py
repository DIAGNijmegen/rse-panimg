import logging
from importlib.metadata import version
from pathlib import Path

import click

from panimg import convert, logger, post_process
from panimg.image_builders import (
    DEFAULT_IMAGE_BUILDERS,
    image_builder_mhd,
    image_builder_tiff,
)
from panimg.post_processors import DEFAULT_POST_PROCESSORS

panimg_version = version("panimg")


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(panimg_version, "-v", "--version")
def cli():
    pass


@cli.command(name="convert", short_help="Convert a directory of image files")
@click.option("-v", "--verbose", count=True)
@click.argument(
    "input",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=False,
        resolve_path=True,
    ),
)
@click.argument(
    "output",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
    ),
)
# TODO implement these options
@click.option("--skip-post-processing")
@click.option("--only-metaio-tiff-builders")
def convert_cli(*, input: str, output: str, verbose: int):
    input_directory = Path(input)
    output_directory = Path(output)

    _setup_verbosity(level=verbose)

    if output_directory.exists():
        raise click.exceptions.UsageError(
            f"Output directory {output_directory} already exists"
        )
    else:
        output_directory.mkdir(parents=True)

    if skip_post_processing:
        post_processors = []
    else:
        post_processors = DEFAULT_POST_PROCESSORS

    if only_metaio_tiff_builders:
        builders = [image_builder_mhd, image_builder_tiff]
    else:
        builders = DEFAULT_IMAGE_BUILDERS

    result = convert(
        input_directory=input_directory,
        output_directory=output_directory,
        builders=builders,
        post_processors=post_processors,
    )

    # TODO dump the result as JSON


@cli.command(name="post-process", short_help="Post process image files")
@click.option("-v", "--verbose", count=True)
@click.argument(
    "input",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=False,
        resolve_path=True,
    ),
)
@click.argument(
    "output",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
    ),
)
def post_process_cli(input: str, output: str, verbose: int):
    input_file = Path(input)
    output_directory = Path(output)

    _setup_verbosity(level=verbose)

    # TODO Load the input file as panimg_files

    if output_directory.exists():
        raise click.exceptions.UsageError(
            f"Output directory {output_directory} already exists"
        )
    else:
        output_directory.mkdir(parents=True)

    result = post_process(
        image_files=panimg_files, post_processors=DEFAULT_POST_PROCESSORS
    )

    # TODO dump the result as JSON


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
