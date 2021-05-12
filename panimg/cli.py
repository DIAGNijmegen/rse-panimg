from pathlib import Path

import click

from panimg import __version__, convert


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, "-v", "--version")
def cli():
    pass


@cli.command(name="convert", short_help="Convert a directory")
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
def convert_cli(input: str, output: str):
    input_directory = Path(input)
    output_directory = Path(output)

    if output_directory.exists():
        raise click.exceptions.UsageError(
            f"Output directory {output_directory} already exists"
        )
    else:
        output_directory.mkdir(parents=True)

    convert(input_directory=input_directory, output_directory=output_directory)
