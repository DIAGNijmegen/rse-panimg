import os
import shutil
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
import pyvips
import tifffile as tiff_lib
from pytest import approx
from tifffile import tifffile

from panimg.exceptions import ValidationError
from panimg.image_builders.tiff import (
    GrandChallengeTiffFile,
    _convert,
    _create_tiff_image_entry,
    _extract_tags,
    _get_color_space,
    _get_mrxs_files,
    _load_with_tiff,
    image_builder_tiff,
)
from panimg.models import ColorSpace
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "color_space_string, expected",
    [
        ("TEST.GRAY", ColorSpace.GRAY),
        ("TEST.MINISBLACK", ColorSpace.GRAY),
        ("TEST.minisblack", ColorSpace.GRAY),
        ("TEST.RGB", ColorSpace.RGB),
        ("TEST.RGBA", ColorSpace.RGBA),
        ("TEST.YCBCR", ColorSpace.YCBCR),
        ("Not.Colour", None),
    ],
)
def test_get_color_space(color_space_string, expected):
    color_space = None

    try:
        color_space = _get_color_space(color_space_string=color_space_string)
    except ValidationError:
        pass

    assert color_space is expected


@pytest.mark.parametrize(
    (
        "path,"
        "color_space,"
        "resolution_levels,"
        "image_height,"
        "image_width,"
        "voxel_height_mm,"
        "voxel_width_mm,"
        "expected_error_message"
    ),
    [
        ("dummy.tiff", 1, 1, 10, 10, 0.1, 0.1, ""),
        (
            "dummy.tiff",
            1,
            None,
            10,
            10,
            0.1,
            0.1,
            "Not a valid tif: Resolution levels not valid",
        ),
        (
            "dummy.tiff",
            1,
            1,
            None,
            10,
            0.1,
            0.1,
            "Not a valid tif: Image height could not be determined",
        ),
        (
            "dummy.tiff",
            1,
            1,
            10,
            None,
            0.1,
            0.1,
            "Not a valid tif: Image width could not be determined",
        ),
        (
            "dummy.tiff",
            1,
            1,
            10,
            10,
            None,
            0.1,
            "Not a valid tif: Voxel height could not be determined",
        ),
        (
            "dummy.tiff",
            1,
            1,
            10,
            10,
            0.1,
            None,
            "Not a valid tif: Voxel width could not be determined",
        ),
    ],
)
def test_grandchallengetifffile_validation(
    path,
    color_space,
    resolution_levels,
    image_height,
    image_width,
    voxel_height_mm,
    voxel_width_mm,
    expected_error_message,
):
    error_message = ""

    try:
        gc_file = GrandChallengeTiffFile(Path(path))
        gc_file.color_space = color_space
        gc_file.resolution_levels = resolution_levels
        gc_file.image_height = image_height
        gc_file.image_width = image_width
        gc_file.voxel_height_mm = voxel_height_mm
        gc_file.voxel_width_mm = voxel_width_mm
        gc_file.validate()
    except ValidationError as e:
        error_message = str(e)

    assert expected_error_message in error_message
    if not expected_error_message:
        assert not error_message


@pytest.mark.parametrize(
    "source_dir, filename, expected_error_message",
    [
        (RESOURCE_PATH, "valid_tiff.tif", ""),
        (
            RESOURCE_PATH,
            "invalid_resolutions_tiff.tif",
            "Invalid resolution unit RESUNIT.NONE in tiff file",
        ),
    ],
)
def test_load_with_tiff(
    source_dir, filename, expected_error_message, tmpdir_factory
):
    error_message = ""
    # Copy resource file to writable temp folder
    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(source_dir / filename, temp_file)
    gc_file = GrandChallengeTiffFile(temp_file)
    gc_file.pk = uuid4()
    try:
        _load_with_tiff(gc_file=gc_file)
    except ValidationError as e:
        error_message = str(e)

    assert expected_error_message in error_message
    if not expected_error_message:
        assert not error_message


@pytest.mark.parametrize(
    "source_dir, filename",
    [(RESOURCE_PATH, "valid_tiff.tif"), (RESOURCE_PATH, "no_dzi.tif")],
)
def test_load_with_open_slide(source_dir, filename, tmpdir_factory):
    # Copy resource file to writable temp folder
    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(source_dir / filename, temp_file)
    gc_file = GrandChallengeTiffFile(temp_file)

    output_dir = Path(tmpdir_factory.mktemp("output"))
    (output_dir / filename).mkdir()

    gc_file = _load_with_tiff(gc_file=gc_file)

    assert gc_file.validate() is None


@pytest.mark.parametrize(
    "resource, expected_error_message, voxel_size",
    [(RESOURCE_PATH / "valid_tiff.tif", "", [1, 1, None])],
)
def test_tiff_image_entry_creation(
    resource, expected_error_message, voxel_size
):
    error_message = ""
    image_entry = None
    gc_file = GrandChallengeTiffFile(resource)
    try:
        tiff_file = tifffile.TiffFile(str(gc_file.path.absolute()))
        gc_file = _extract_tags(gc_file=gc_file, pages=tiff_file.pages)
        image_entry = _create_tiff_image_entry(tiff_file=gc_file)
    except ValidationError as e:
        error_message = str(e)

    # Asserts possible file opening failures
    assert expected_error_message in error_message
    if not expected_error_message:
        assert not error_message

    # Asserts successful creation data
    if not expected_error_message:
        tiff_file = tiff_lib.TiffFile(str(resource.absolute()))
        tiff_tags = tiff_file.pages[0].tags

        assert image_entry.name == resource.name
        assert image_entry.width == tiff_tags["ImageWidth"].value
        assert image_entry.height == tiff_tags["ImageLength"].value
        assert image_entry.depth == 1
        assert image_entry.resolution_levels == len(tiff_file.pages)
        assert image_entry.color_space == _get_color_space(
            color_space_string=str(
                tiff_tags["PhotometricInterpretation"].value
            )
        )
        assert image_entry.voxel_width_mm == approx(voxel_size[0])
        assert image_entry.voxel_height_mm == approx(voxel_size[1])
        assert image_entry.voxel_depth_mm == voxel_size[2]
        assert image_entry.pk == gc_file.pk


# Integration test of all features being accessed through the image builder
def test_image_builder_tiff(tmpdir_factory,):
    # Copy resource files to writable temp folder
    temp_dir = Path(tmpdir_factory.mktemp("temp") / "resources")
    output_dir = Path(tmpdir_factory.mktemp("output"))

    shutil.copytree(
        RESOURCE_PATH,
        temp_dir,
        ignore=shutil.ignore_patterns("dicom*", "complex_tiff", "dzi_tiff"),
    )
    files = [Path(d[0]).joinpath(f) for d in os.walk(temp_dir) for f in d[2]]

    image_builder_result = _build_files(
        builder=image_builder_tiff, files=files, output_directory=output_dir
    )

    expected_files = [
        temp_dir / "valid_tiff.tif",
        temp_dir / "no_dzi.tif",
    ]

    assert sorted(image_builder_result.consumed_files) == sorted(
        expected_files
    )

    file_to_pk = {i.name: i.pk for i in image_builder_result.new_images}

    for file in expected_files:
        pk = file_to_pk[file.name]
        assert os.path.isfile(output_dir / file.name / f"{pk}.tif")

    # Assert that both tiff images are imported
    assert len(image_builder_result.new_image_files) == 2


def test_handle_complex_files(tmpdir_factory):
    # Copy resource files to writable temp folder
    temp_dir = Path(tmpdir_factory.mktemp("temp") / "resources")
    shutil.copytree(RESOURCE_PATH / "complex_tiff", temp_dir)
    files = [Path(d[0]).joinpath(f) for d in os.walk(temp_dir) for f in d[2]]

    # set up mock object to mock pyvips
    properties = {
        "xres": 1,
        "yres": 1,
        "openslide.mpp-x": 0.2525,
        "openslide.mpp-y": 0.2525,
    }

    mock_converter = MagicMock(pyvips)
    mock_image = mock_converter.Image.new_from_file.return_value
    mock_image.get = Mock(return_value=1)
    mock_image.get_fields = Mock(return_value=properties)

    _convert(
        files=files,
        associated_files_getter=_get_mrxs_files,
        converter=mock_converter,
        output_directory=Path(tmpdir_factory.mktemp("output")),
        file_errors=defaultdict(list),
    )

    mock_image.copy.assert_called()
    assert "xres" in mock_image.copy.call_args[1]
    assert (
        pyvips.base.version(0) == 8 and pyvips.base.version(1) < 10
    ), "Remove work-around calculation of xres and yres in _convert_to_tiff function."


@pytest.mark.skip(
    reason="skip for now as we don't want to upload a large testset"
)
@pytest.mark.parametrize(
    "resource",
    [
        RESOURCE_PATH / "convert_to_tiff" / "vms",
        RESOURCE_PATH / "convert_to_tiff" / "svs",
        RESOURCE_PATH / "convert_to_tiff" / "ndpi",
        RESOURCE_PATH / "convert_to_tiff" / "scn",
        RESOURCE_PATH / "convert_to_tiff" / "mrxs",
        RESOURCE_PATH / "convert_to_tiff" / "bif",
    ],
)
def test_convert_to_tiff(resource, tmpdir_factory):
    output_dir = Path(tmpdir_factory.mktemp("output"))

    input_files = {f for f in resource.glob("*") if f.is_file()}

    result = image_builder_tiff(files=input_files, output_directory=output_dir)

    assert len(result.new_images) == 1
    assert len(result.new_image_files) == 1


def test_error_handling(tmpdir_factory):
    # Copy resource files to writable temp folder
    # The content files are dummy files and won't compile to tiff.
    # The point is to test the loading of gc_files and make sure all
    # related files are associated with the gc_file
    temp_dir = Path(tmpdir_factory.mktemp("temp") / "resources")
    shutil.copytree(RESOURCE_PATH / "complex_tiff", temp_dir)
    files = {Path(d[0]).joinpath(f) for d in os.walk(temp_dir) for f in d[2]}

    image_builder_result = _build_files(
        builder=image_builder_tiff,
        files=files,
        output_directory=Path(tmpdir_factory.mktemp("output")),
    )

    assert len(image_builder_result.file_errors) == 14
