import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import tifffile as tiff_lib
from pytest import approx
from tifffile import tifffile

from panimg.exceptions import ValidationError
from panimg.image_builders.tiff import (
    GrandChallengeTiffFile,
    _extract_tags,
    _get_color_space,
    _load_with_openslide,
    _load_with_tiff,
    image_builder_tiff,
)
from panimg.models import MAXIMUM_SEGMENTS_LENGTH, ColorSpace
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "color_space_string, expected",
    [
        ("GRAY", ColorSpace.GRAY),
        ("MINISBLACK", ColorSpace.GRAY),
        ("minisblack", ColorSpace.GRAY),
        ("RGB", ColorSpace.RGB),
        ("RGBA", ColorSpace.RGBA),
        ("YCBCR", ColorSpace.YCBCR),
        ("Colour", None),
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
    "source_dir, filename, error_message, min, max, segments",
    [
        (RESOURCE_PATH, "test_min_max.tif", "", 0, 4, {0, 1, 2, 3, 4}),
        (
            RESOURCE_PATH,
            "invalid_resolutions_tiff.tif",
            "Invalid resolution unit NONE in tiff file",
            None,
            None,
            {},
        ),
    ],
)
def test_load_with_tiff(
    source_dir,
    filename,
    error_message,
    min,
    max,
    segments,
    tmpdir_factory,
):
    error = ""
    # Copy resource file to writable temp directory
    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(source_dir / filename, temp_file)
    gc_file = GrandChallengeTiffFile(temp_file)
    gc_file.pk = uuid4()
    try:
        gc_file = _load_with_tiff(gc_file=gc_file)
        assert gc_file.min_voxel_value == min
        assert gc_file.max_voxel_value == max
        assert gc_file.segments == segments
    except ValidationError as e:
        error = str(e)

    assert error_message in error
    if not error_message:
        assert not error


def test_segments_computed_property():
    gc_file = GrandChallengeTiffFile(RESOURCE_PATH / "test_min_max.tif")
    assert gc_file.segments is None
    gc_file.min_voxel_value = 0
    gc_file.max_voxel_value = MAXIMUM_SEGMENTS_LENGTH
    assert gc_file.segments is None
    gc_file.max_voxel_value = 4
    assert gc_file.segments == frozenset({0, 1, 2, 3, 4})


@pytest.mark.parametrize(
    "source_dir, filename",
    [(RESOURCE_PATH, "valid_tiff.tif"), (RESOURCE_PATH, "no_dzi.tif")],
)
def test_load_with_open_slide(source_dir, filename, tmpdir_factory):
    # Copy resource file to writable temp directory
    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(source_dir / filename, temp_file)
    gc_file = GrandChallengeTiffFile(temp_file)

    output_dir = Path(tmpdir_factory.mktemp("output"))
    (output_dir / filename).mkdir()
    gc_file = _load_with_tiff(gc_file=gc_file)
    gc_file = _load_with_openslide(gc_file=gc_file)

    assert gc_file.validate() is None


@pytest.mark.parametrize(
    "resource, expected_error_message, voxel_size",
    [
        (
            RESOURCE_PATH / "valid_tiff.tif",
            "",
            [1, 1],
        )
    ],
)
def test_tiff_image_entry_creation(
    resource, expected_error_message, voxel_size
):
    error_message = ""
    gc_file = GrandChallengeTiffFile(resource)
    try:
        tiff_file = tifffile.TiffFile(str(gc_file.path.absolute()))
        gc_file = _extract_tags(
            gc_file=gc_file,
            pages=tiff_file.pages,
            byteorder=tiff_file.byteorder,
        )
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

        assert gc_file.path.name == resource.name
        assert gc_file.image_width == tiff_tags["ImageWidth"].value
        assert gc_file.image_height == tiff_tags["ImageLength"].value
        assert gc_file.resolution_levels == len(tiff_file.pages)
        assert gc_file.color_space == _get_color_space(
            color_space_string=tiff_tags[
                "PhotometricInterpretation"
            ].value.name
        )
        assert gc_file.voxel_width_mm == approx(voxel_size[0])
        assert gc_file.voxel_height_mm == approx(voxel_size[1])
        assert gc_file.min_voxel_value is None
        assert gc_file.max_voxel_value is None
        assert gc_file.segments is None


# Integration test of all features being accessed through the image builder
def test_image_builder_tiff(tmpdir_factory):
    # Copy resource files to writable temp directory
    temp_dir = Path(tmpdir_factory.mktemp("temp") / "resources")
    output_dir = Path(tmpdir_factory.mktemp("output"))

    shutil.copytree(
        RESOURCE_PATH,
        temp_dir,
        ignore=shutil.ignore_patterns(
            "dicom*", "complex_tiff", "dzi_tiff", "isyntax_wsi"
        ),
    )
    files = [Path(d[0]).joinpath(f) for d in os.walk(temp_dir) for f in d[2]]

    image_builder_result = _build_files(
        builder=image_builder_tiff, files=files, output_directory=output_dir
    )

    expected_files = [
        temp_dir / "valid_tiff.tif",
        temp_dir / "no_dzi.tif",
        temp_dir / "test_min_max.tif",
    ]

    assert sorted(image_builder_result.consumed_files) == sorted(
        expected_files
    )

    file_to_pk = {i.name: i.pk for i in image_builder_result.new_images}

    for file in expected_files:
        pk = file_to_pk[file.name]
        assert os.path.isfile(output_dir / file.name / f"{pk}.tif")

    # Assert that both tiff images are imported
    assert len(image_builder_result.new_image_files) == 3


@pytest.mark.xfail(
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
        RESOURCE_PATH / "convert_to_tiff" / "isyntax",
    ],
)
def test_convert_to_tiff(resource, tmpdir_factory):
    output_dir = Path(tmpdir_factory.mktemp("output"))

    input_files = {f for f in resource.glob("*") if f.is_file()}

    result = _build_files(
        builder=image_builder_tiff,
        files=input_files,
        output_directory=output_dir,
    )

    assert len(result.new_images) == 1
    assert len(result.new_image_files) == 1


def test_error_handling(tmpdir_factory):
    # Copy resource files to writable temp directory
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

    output = {k.name: v for k, v in image_builder_result.file_errors.items()}

    assert output == {
        "Mirax2-Fluorescence-1.mrxs": [
            "TIFF image builder: Could not convert file to TIFF: "
            "Mirax2-Fluorescence-1.mrxs",
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05.vms": [
            "TIFF image builder: Could not convert file to TIFF: "
            "CMU-1-40x - 2010-01-12 13.24.05.vms",
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "Data0001.dat": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "Index.dat": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05(0,1).jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05_map2.jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "Slidedat.ini": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05_macro.jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05.opt": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05(1,0).jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "Data0000.dat": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05.jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "CMU-1-40x - 2010-01-12 13.24.05(1,1).jpg": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
        "Data0002.dat": [
            "TIFF image builder: Could not open file with tifffile.",
            "TIFF image builder: Could not open file with OpenSlide.",
            "TIFF image builder: Validation error: "
            "Not a valid tif: Image width could not be determined.",
        ],
    }
