import shutil

import pytest

from panimg import convert
from panimg.image_builders.metaio_utils import (
    ADDITIONAL_HEADERS,
    EXPECTED_HEADERS,
    HEADERS_MATCHING_NUM_TIMEPOINTS,
    HEADERS_WITH_LISTING,
    extract_header_listing,
    parse_mh_header,
)
from panimg.models import ColorSpace
from tests import RESOURCE_PATH


def _convert_images(*, images, tmpdir_factory):
    input_directory = tmpdir_factory.mktemp("input")
    for image in images:
        shutil.copy(RESOURCE_PATH / image, input_directory)

    output_directory = tmpdir_factory.mktemp("output")

    return convert(
        input_directory=input_directory, output_directory=output_directory
    )


def test_image_file_creation(tmpdir_factory):
    images = [
        "image10x10x10.zraw",
        "image10x10x10.mhd",
        "image10x10x10.mha",
        "image10x11x12x13.mhd",
        "image10x11x12x13.zraw",
        "image10x10x10-extra-stuff.mhd",
        "invalid_utf8.mhd",
        "no_image",
        "valid_tiff.tif",
        "invalid_resolutions_tiff.tif",
    ]

    invalid_images = (
        "no_image",
        "invalid_utf8.mhd",
        "invalid_resolutions_tiff.tif",
    )

    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.consumed_files) == len(images) - len(invalid_images)
    assert len(result.new_images) == 5


@pytest.mark.parametrize(
    "images",
    (
        ["image10x11x12x13.mha"],
        ["image10x11x12x13.mhd", "image10x11x12x13.zraw"],
    ),
)
def test_staged_4d_mha_and_4d_mhd_upload(images, tmpdir_factory):
    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.new_images) == 1

    image = result.new_images.pop()

    assert image.timepoints == 13
    assert image.depth == 12
    assert image.height == 11
    assert image.width == 10
    assert image.color_space == ColorSpace.GRAY


@pytest.mark.parametrize(
    "images,four_d",
    (
        (["image10x11x12x13-extra-stuff.mhd", "image10x11x12x13.zraw"], True),
        (["image3x4-extra-stuff.mhd", "image3x4.zraw"], False),
    ),
)
def test_staged_mhd_upload_with_additional_headers(
    tmpdir_factory, images, four_d
):
    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.new_images) == 1
    assert len(result.new_image_files) == 1

    image_file = result.new_image_files.pop()
    headers = parse_mh_header(image_file.file)

    for key in headers.keys():
        assert (key in ADDITIONAL_HEADERS) or (key in EXPECTED_HEADERS)

    for key in ADDITIONAL_HEADERS:
        assert key in headers.keys()
        if key in HEADERS_MATCHING_NUM_TIMEPOINTS:
            if four_d:
                assert len(headers[key].split(" ")) == 13
            else:
                assert len(headers[key].split(" ")) == 1

    assert "Bogus" not in headers.keys()

    original_headers = parse_mh_header(RESOURCE_PATH / images[0])
    exempt_headers = {
        "CompressedDataSize",  # Expected to change between mha/(mhd+.zraw)
        "ElementDataFile",  # Expected to change between mha/(mhd+.zraw)
        "AnatomicalOrientation",  # Isn't read but only writen based on direction
        "ElementNumberOfChannels",  # Not applicable
    }
    for key in (
        set(ADDITIONAL_HEADERS.keys()) | set(EXPECTED_HEADERS)
    ) - exempt_headers:
        if key in HEADERS_WITH_LISTING:
            for original, new in zip(
                extract_header_listing(key, original_headers),
                extract_header_listing(key, headers),
                strict=True,
            ):
                assert original == new, key
        else:
            assert original_headers[key] == headers[key], key


def test_no_convertible_file(tmpdir_factory):
    images = ["no_image", "image10x10x10.mhd", "referring_to_system_file.mhd"]

    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.new_images) == 0
    assert len(result.new_image_files) == 0
    assert len(result.file_errors) == 3


def test_errors_on_files_with_duplicate_file_names(tmpdir_factory):
    images = [
        "image10x10x10.zraw",
        "image10x10x10.mhd",
        "image10x10x10.zraw",
        "image10x10x10.mhd",
    ]

    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.new_images) == 1
    assert len(result.consumed_files) == 2


def test_mhd_file_annotation_creation(tmpdir_factory):
    images = ["image5x6x7.mhd", "image5x6x7.zraw"]

    result = _convert_images(images=images, tmpdir_factory=tmpdir_factory)

    assert len(result.new_images) == 1

    image = result.new_images.pop()
    assert image.depth == 7
    assert image.height == 6
    assert image.width == 5
    assert image.color_space == ColorSpace.GRAY


def test_subdirectory_traverse_setting(tmpdir_factory):
    input_dir = tmpdir_factory.mktemp("input")
    sub_dir = input_dir / "sub"
    sub_dir.mkdir()

    image = RESOURCE_PATH / "nifti" / "image10x11x12.nii"
    image_sub = RESOURCE_PATH / "image10x10x10.mha"

    shutil.copy(image, input_dir)
    shutil.copy(image_sub, sub_dir)
    output_dir = tmpdir_factory.mktemp("output")

    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        recurse_subdirectories=True,
    )

    assert len(result.new_images) == 2

    output_dir = tmpdir_factory.mktemp("output2")
    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        recurse_subdirectories=False,
    )

    assert len(result.new_images) == 1
