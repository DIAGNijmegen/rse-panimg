from pathlib import Path

import SimpleITK
import pytest
from pytest import approx

from panimg.image_builders.metaio_utils import load_sitk_image
from panimg.models import ColorSpace, EXTRA_METADATA, SimpleITKImage
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "image",
    (
        RESOURCE_PATH / "image3x4.mhd",
        RESOURCE_PATH / "image3x4-extra-stuff.mhd",
        RESOURCE_PATH / "image5x6x7.mhd",
        RESOURCE_PATH / "image10x10x10.mhd",
        RESOURCE_PATH / "image10x10x10.mha",
        RESOURCE_PATH / "image10x10x10-extra-stuff.mhd",
        RESOURCE_PATH / "image10x11x12x13.mhd",
        RESOURCE_PATH / "image10x11x12x13.mhd",
        RESOURCE_PATH / "image10x11x12x13-extra-stuff.mhd",
        RESOURCE_PATH / "image128x256RGB.mhd",
        RESOURCE_PATH / "image128x256x3RGB.mhd",
        RESOURCE_PATH / "image128x256x4RGB.mhd",
    ),
)
def test_convert_itk_to_internal(image: Path):
    def assert_img_properties(
        img: SimpleITK.Image, internal_image: SimpleITKImage
    ):
        color_space = {
            1: ColorSpace.GRAY,
            3: ColorSpace.RGB,
            4: ColorSpace.RGBA,
        }

        assert internal_image.color_space == color_space.get(
            img.GetNumberOfComponentsPerPixel()
        )
        if img.GetDimension() == 4:
            assert internal_image.timepoints == img.GetSize()[-1]
        else:
            assert internal_image.timepoints is None
        if img.GetDepth():
            assert internal_image.depth == img.GetDepth()
            assert internal_image.voxel_depth_mm == img.GetSpacing()[2]
        else:
            assert internal_image.depth is None
            assert internal_image.voxel_depth_mm is None

        assert internal_image.width == img.GetWidth()
        assert internal_image.height == img.GetHeight()
        assert internal_image.voxel_width_mm == approx(img.GetSpacing()[0])
        assert internal_image.voxel_height_mm == approx(img.GetSpacing()[1])

        md_keys = img.GetMetaDataKeys()
        metadata = internal_image.generate_extra_metadata()
        for md in EXTRA_METADATA:
            value = metadata[md.field_name]
            if md.keyword in md_keys:
                assert value == md.cast_func(img.GetMetaData(md.keyword))
            else:
                assert value is None

    img_ref = load_sitk_image(image)
    internal_image = SimpleITKImage(
        name=image.name,
        image=img_ref,
        consumed_files=set(),
        spacing_valid=True,
    )
    assert_img_properties(img_ref, internal_image)
