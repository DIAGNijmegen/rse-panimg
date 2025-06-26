import pytest

from panimg.exceptions import UnconsumedFilesException
from panimg.image_builders import DEFAULT_IMAGE_BUILDERS, image_builder_oct
from panimg.panimg import _build_files
from tests import RESOURCE_PATH

EXPECTED_ERROR_MESSAGE = {
    "image_builder_dicom": ["Dicom image builder: could not parse headers"],
    "image_builder_fallback": [
        "Fallback image builder: Not a valid image file"
    ],
    "image_builder_mhd": ["Mhd image builder: Not an ITK file"],
    "image_builder_nifti": ["NifTI image builder: Not a NifTI image file"],
    "image_builder_nrrd": ["NRRD image builder: Not a NRRD image file"],
    "image_builder_oct": [
        "OCT image builder: Not a valid OCT file "
        "(supported formats: .fds,.fda,.e2e)"
    ],
    "image_builder_tiff": [
        "TIFF image builder: Could not open file with tifffile.",
        "TIFF image builder: Could not open file with OpenSlide.",
        "TIFF image builder: Validation error: Not a valid tif: "
        "Image width could not be determined.",
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
def test_number_of_images_consumed_by_each_builder(tmp_path, builder):
    # Except for the oct builder, each of the builders should only consume one
    # image. The other files should error out.
    files = {
        *(RESOURCE_PATH / "dicom_4d").glob("*.dcm"),
        RESOURCE_PATH / "test_rgb.png",
        RESOURCE_PATH / "image10x10x10.mha",
        RESOURCE_PATH / "nifti" / "image10x11x12.nii.gz",
        RESOURCE_PATH / "nrrd" / "image10x11x12.nrrd",
        RESOURCE_PATH / "valid_tiff.tif",
        RESOURCE_PATH / "oct/fda_minimized.fda",
        RESOURCE_PATH / "oct/fds_minimized.fds",
    }

    result = _build_files(
        builder=builder, files=files, output_directory=tmp_path
    )

    if image_builder_oct == builder:
        assert len(result.new_images) == 2
    else:
        assert len(result.new_images) == 1
    assert len(result.consumed_files) == len(files) - len(result.file_errors)
    assert result.consumed_files | {*result.file_errors} == files
