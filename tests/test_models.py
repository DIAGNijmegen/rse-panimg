import logging
from pathlib import Path

import pytest

from panimg import image_builders
from panimg.exceptions import ValidationError
from panimg.image_builders.metaio_utils import load_sitk_image
from panimg.models import EXTRA_METADATA, ExtraMetaData, SimpleITKImage
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "vr,valid,invalid",
    (
        (
            "AS",
            ("000D", "123W", "456M", "789Y"),
            ("1Y", "12D", "1234D", "123"),
        ),
        ("CS", ("M", " A_A", "", "A" * 16), ("a", "A" * 17, "\\")),
        (
            "DA",
            ("20210923", "12341231", ""),
            (
                "12345678",
                "a",
                "1",
                "1234567",
                "2021923",
                "2021010a",
                "123456789",
                "20210229",
                "20210931",
                "12341231123456",
            ),
        ),
        (
            "LO",
            ("", "a" * 64, "😄", "😄" * 64),
            ("a" * 65, "\\", "😄" * 65, r"a\a"),
        ),
        (
            "PN",
            ("", "a" * 324, "😄", "😄" * 324),
            ("a" * 325, "\\", "😄" * 325, r"a\a"),
        ),
        (
            "UI",
            ("", "1.0", "0.0.0.0", "1." * 32),
            ("1." * 33, "a", "😄.😄", "1.2.+.a"),
        ),
    ),
)
def test_dicom_vr_validation(vr, valid, invalid):
    md = ExtraMetaData("Test", vr, "test", "default")
    for t in valid:
        md.validate_value(t)

    for t in invalid:
        with pytest.raises(ValidationError):
            md.validate_value(t)


@pytest.mark.parametrize(
    ["key", "value"],
    [
        ("PatientID", "a" * 65),
        ("PatientName", "a" * 325),
        ("PatientBirthDate", "invalid date"),
        ("PatientAge", "invalid age"),
        ("PatientSex", "invalid sex"),
        ("StudyDate", "invalid date"),
        ("StudyInstanceUID", "invalid uid"),
        ("SeriesInstanceUID", "invalid uid"),
        ("StudyDescription", "a" * 65),
        ("SeriesDescription", "a" * 65),
    ],
)
def test_built_image_invalid_headers(tmpdir, caplog, key, value):
    src = RESOURCE_PATH / "image3x4-extra-stuff.mhd"
    sitk_image = load_sitk_image(src)
    sitk_image.SetMetaData(key, value)
    result = SimpleITKImage(
        image=sitk_image,
        name=src.name,
        consumed_files={src},
        spacing_valid=True,
    )
    result.save(output_directory=tmpdir)
    assert len(caplog.records) == 1
    warning = caplog.records[0]
    assert warning.levelno == logging.WARNING
    assert "ValidationError" in warning.msg


def test_built_image_extra_metadata_defaults(tmpdir, caplog):
    src = RESOURCE_PATH / "image3x4.mhd"
    sitk_image = load_sitk_image(src)
    result = SimpleITKImage(
        image=sitk_image,
        name=src.name,
        consumed_files={src},
        spacing_valid=True,
    )
    new_image, new_files = result.save(output_directory=tmpdir)
    assert len(caplog.records) == 0
    expected_default_values = {
        md.field_name: md.default_value for md in EXTRA_METADATA
    }
    for key, val in expected_default_values.items():
        assert getattr(new_image, key) == val


@pytest.mark.parametrize(
    "src_image_name,smallest_pixel_value,largest_pixel_value",
    [
        (  # Regular case
            "image_min10_max10.mha",
            -10,
            10,
        ),
        (  # Predefined ranges in input file
            "image3x4-extra-stuff.mhd",
            -100,
            100,
        ),
        (  # 3D image
            "image10x10x10.mha",
            8.341192e-05,
            0.999185,
        ),
        (  # 4D image
            "image10x11x12x13.mha",
            0,
            0,
        ),
    ],
)
def test_sitk_image_value_range(
    src_image_name,
    smallest_pixel_value,
    largest_pixel_value,
):
    src = RESOURCE_PATH / src_image_name
    sitk_image = load_sitk_image(src)
    result = SimpleITKImage(
        image=sitk_image,
        name=src.name,
        consumed_files={src},
        spacing_valid=True,
    )

    for value, tag in [
        (smallest_pixel_value, "SmallestImagePixelValue"),
        (largest_pixel_value, "LargestImagePixelValue"),
    ]:
        if value is None:
            assert not result.image.HasMetaDataKey(tag)
        else:
            assert float(result.image.GetMetaData(tag)) == pytest.approx(value)


@pytest.mark.parametrize(
    "src_image,builder,segments",
    [
        (
            "image_min10_max10.mha",
            image_builders.image_builder_mhd,
            frozenset(
                (
                    -10,
                    -9,
                    -8,
                    -7,
                    -6,
                    -5,
                    -4,
                    -3,
                    -2,
                    -1,
                    0,
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                    9,
                    10,
                )
            ),
        ),
        (  # Too many values
            "dicom_2d/cxr.dcm",
            image_builders.image_builder_dicom,
            None,
        ),
        (  # Image type is vector of ints
            "test_rgb.png",
            image_builders.image_builder_fallback,
            None,
        ),
        (  # Tiffs are always None
            "valid_tiff.tif",
            image_builders.image_builder_tiff,
            None,
        ),
    ],
)
def test_segments(
    src_image,
    builder,
    segments,
    tmpdir_factory,
):
    files = {RESOURCE_PATH / src_image}
    output_dir = Path(tmpdir_factory.mktemp("output"))
    result = _build_files(
        builder=builder, files=files, output_directory=output_dir
    )
    assert result.consumed_files == files
    assert len(result.new_images) == 1

    image = result.new_images.pop()
    assert image.segments == segments
