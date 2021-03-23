import pytest

from panimg.exceptions import UnconsumedFilesException
from panimg.image_builders import DEFAULT_IMAGE_BUILDERS
from panimg.panimg import _build_files
from tests import RESOURCE_PATH

EXPECTED_ERROR_MESSAGE = {
    "image_builder_dicom": [
        (
            "Dicom image builder: File is missing DICOM File Meta "
            "Information header or the 'DICM' prefix is missing from the "
            "header. Use force=True to force reading."
        )
    ],
    "image_builder_fallback": [
        "Fallback image builder: Not a valid image file"
    ],
    "image_builder_mhd": ["Mhd image builder: Not an ITK file"],
    "image_builder_nifti": ["NifTI image builder: Not a NifTI image file"],
    "image_builder_tiff": [
        "Could not open file with tifffile.",
        "Could not open file with OpenSlide.",
        "Validation error: Not a valid tif: Image width could not be determined.",
    ],
}


@pytest.mark.parametrize("builder", DEFAULT_IMAGE_BUILDERS)
def test_image_builder_raises_unconsumed_file_exception(tmp_path, builder):
    f = tmp_path / "image.jpg"
    f.write_bytes(b"")

    with pytest.raises(UnconsumedFilesException) as e:
        _ = [*builder(files={f})]

    assert {**e.value.file_errors} == {
        f: EXPECTED_ERROR_MESSAGE[builder.__name__]
    }


@pytest.mark.parametrize("builder", DEFAULT_IMAGE_BUILDERS)
def test_one_image_consumed_by_each_builder(tmp_path, builder):
    # Each of these images should only be consumed by one builder
    # The other files should error out
    files = {
        *(RESOURCE_PATH / "dicom").glob("*.dcm"),
        RESOURCE_PATH / "test_rgb.png",
        RESOURCE_PATH / "image10x10x10.mha",
        RESOURCE_PATH / "image10x11x12.nii.gz",
        RESOURCE_PATH / "valid_tiff.tif",
    }

    result = _build_files(
        builder=builder, files=files, output_directory=tmp_path
    )

    assert len(result.new_images) == 1
    assert len(result.consumed_files) == len(files) - len(result.file_errors)
    assert result.consumed_files | {*result.file_errors} == files
