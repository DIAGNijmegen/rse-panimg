import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from panimg.image_builders.metaio_nrrd import image_builder_nrrd
from panimg.models import ColorSpace
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "srcfile",
    (
        RESOURCE_PATH / "nrrd" / "image10x11x12.nrrd",
        RESOURCE_PATH / "nrrd" / "image10x11x12_compressed.nrrd",
    ),
)
def test_image_builder_nrrd(tmpdir_factory, srcfile: Path):
    dest = Path(tmpdir_factory.mktemp("input"))

    # Copy files into an empty temporary directory
    shutil.copy(srcfile, dest)
    files = {dest / srcfile.name}

    # Run image builder
    result = _build_files(
        builder=image_builder_nrrd,
        files=files,
        output_directory=tmpdir_factory.mktemp("output"),
    )

    # Verify results
    assert result.consumed_files == files
    assert len(result.new_images) == 1

    image = result.new_images.pop()
    assert image.color_space == ColorSpace.GRAY.value
    assert image.width == 10
    assert image.height == 11
    assert image.depth == 12
    assert image.voxel_width_mm == pytest.approx(1.0)
    assert image.voxel_height_mm == pytest.approx(2.0)
    assert image.voxel_depth_mm == pytest.approx(3.0)


@pytest.mark.parametrize(
    "srcfiles",
    (
        [
            RESOURCE_PATH / "nrrd" / "image10x11x12.nhdr",
            RESOURCE_PATH / "nrrd" / "image10x11x12.raw",
        ],
        [
            RESOURCE_PATH / "nrrd" / "image10x11x12_compressed.nhdr",
            RESOURCE_PATH / "nrrd" / "image10x11x12_compressed.raw.gz",
        ],
    ),
)
def test_image_builder_nrrd_detached_header(
    tmpdir_factory, srcfiles: list[Path]
):
    dest = Path(tmpdir_factory.mktemp("input"))

    # Copy files into an empty temporary directory
    files = set()
    for srcfile in srcfiles:
        shutil.copy(srcfile, dest)
        files.add(dest / srcfile.name)

    # Run image builder
    result = _build_files(
        builder=image_builder_nrrd,
        files=files,
        output_directory=tmpdir_factory.mktemp("output"),
    )

    # Verify results (should not read anything)
    assert result.consumed_files == set()
    assert len(result.new_images) == 0


def test_image_builder_with_unsupported_version(tmpdir):
    dest = Path(tmpdir) / "image10x11x12_unsupported_version.nrrd"
    shutil.copy(RESOURCE_PATH / "nrrd" / dest.name, dest)
    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_nrrd, files=files, output_directory=output
        )
    assert result.consumed_files == set()
    assert len(result.new_images) == 0


def test_image_builder_with_other_file_extension(tmpdir):
    dest = Path(tmpdir) / "image10x10x10.mha"
    shutil.copy(RESOURCE_PATH / dest.name, dest)
    files = {Path(d[0]).joinpath(f) for d in os.walk(tmpdir) for f in d[2]}
    with TemporaryDirectory() as output:
        result = _build_files(
            builder=image_builder_nrrd, files=files, output_directory=output
        )
    assert result.consumed_files == set()
    assert len(result.new_images) == 0
