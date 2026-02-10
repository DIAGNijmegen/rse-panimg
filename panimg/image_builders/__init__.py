from collections.abc import Iterable

from panimg_models import ImageBuilderOptions

from panimg.image_builders.dicom import image_builder_dicom
from panimg.image_builders.fallback import image_builder_fallback
from panimg.image_builders.metaio_mhd_mha import image_builder_mhd
from panimg.image_builders.metaio_nifti import image_builder_nifti
from panimg.image_builders.metaio_nrrd import image_builder_nrrd
from panimg.image_builders.oct import image_builder_oct
from panimg.image_builders.tiff import image_builder_tiff
from panimg.types import ImageBuilder

# DEFAULT_IMAGE_BUILDERS are used directly by Grand Challenge
# DO NOT CHANGE THEM without considering the impact there.
DEFAULT_IMAGE_BUILDERS: Iterable[ImageBuilder] = [
    image_builder_mhd,
    image_builder_nifti,
    image_builder_nrrd,
    image_builder_dicom,
    image_builder_tiff,
    image_builder_oct,
    image_builder_fallback,
]


IMAGE_BUILDER_OPTIONS_TO_IMPLEMENTATION: dict[str, ImageBuilder] = {
    ImageBuilderOptions.MHD: image_builder_mhd,
    ImageBuilderOptions.NIFTI: image_builder_nifti,
    ImageBuilderOptions.NRRD: image_builder_nrrd,
    ImageBuilderOptions.DICOM: image_builder_dicom,
    ImageBuilderOptions.TIFF: image_builder_tiff,
    ImageBuilderOptions.OCT: image_builder_oct,
    ImageBuilderOptions.FALLBACK: image_builder_fallback,
}

__all__ = [
    "image_builder_mhd",
    "image_builder_nifti",
    "image_builder_nrrd",
    "image_builder_dicom",
    "image_builder_tiff",
    "image_builder_oct",
    "image_builder_fallback",
    "DEFAULT_IMAGE_BUILDERS",
    "ImageBuilderOptions",
    "IMAGE_BUILDER_OPTIONS_TO_IMPLEMENTATION",
]
