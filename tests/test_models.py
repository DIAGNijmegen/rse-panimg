from pathlib import Path

import pytest

from panimg import image_builders
from panimg.image_builders.metaio_utils import load_sitk_image
from panimg.models import SimpleITKImage
from panimg.panimg import _build_files
from tests import RESOURCE_PATH


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
            2,
            2,
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
            "segments/-10_10_Int8.mha",
            image_builders.image_builder_mhd,
            frozenset(range(-10, 10)),
        ),
        (
            "segments/0_10_UInt8.mha",
            image_builders.image_builder_mhd,
            frozenset(range(10)),
        ),
        (
            "segments/4D_1_1_1_5_UInt8.mha",
            image_builders.image_builder_mhd,
            frozenset({1, 2, 3, 4, 5}),
        ),
        (
            # Contains non-zero or ones as values
            "segments/4D_1_1_1_5_UInt8_threes.mha",
            image_builders.image_builder_mhd,
            None,
        ),
        (
            # Datatype is not sitkUInt8 or sitkInt8
            "image_min10_max10.mha",
            image_builders.image_builder_mhd,
            None,
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


def test_invalid_4d(tmp_path_factory):
    file = RESOURCE_PATH / "channels" / "5_1_1_1_invalid.mha"
    result = _build_files(
        builder=image_builders.image_builder_mhd,
        files={file},
        output_directory=tmp_path_factory.mktemp("output"),
    )

    assert result.consumed_files == set()
    assert len(result.new_images) == 0
    assert result.file_errors == {
        file: [
            (
                "Mhd image builder: Images with more than 4 channels not supported. "
                "For 4D data please use the 4th dimension instead."
            )
        ]
    }


def test_4d_segmentation_none_timepoints(tmp_path_factory):
    result = _build_files(
        builder=image_builders.image_builder_mhd,
        files={RESOURCE_PATH / "segments" / "4D_1_1_1_5_UInt8.mha"},
        output_directory=tmp_path_factory.mktemp("output"),
    )

    new_image = result.new_images.pop()

    assert new_image.segments == frozenset({1, 2, 3, 4, 5})
    assert new_image.timepoints is None


def test_model_strips_headers(tmpdir):
    src = RESOURCE_PATH / "image3x4-extra-stuff.mhd"
    old_image = load_sitk_image(src)
    old_image.SetMetaData("PatientID", "remove_me")

    result = SimpleITKImage(
        image=old_image,
        name=src.name,
        consumed_files={src},
        spacing_valid=True,
    )
    _, new_files = result.save(output_directory=tmpdir)

    new_image = load_sitk_image(new_files.pop().file)

    removed_keys = {*old_image.GetMetaDataKeys()} - {
        *new_image.GetMetaDataKeys()
    }

    assert removed_keys == {"PatientID"}
    assert {*new_image.GetMetaDataKeys()} == {
        "ContentTimes",
        "Exposures",
        "LargestImagePixelValue",
        "Laterality",
        "SliceThickness",
        "SmallestImagePixelValue",
        "WindowCenter",
        "WindowWidth",
        "t0",
        "t1",
    }
