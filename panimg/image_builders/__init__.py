from typing import Iterable

from panimg.image_builders.dicom import image_builder_dicom
from panimg.image_builders.fallback import image_builder_fallback
from panimg.image_builders.metaio_mhd_mha import image_builder_mhd
from panimg.image_builders.nifti import image_builder_nifti
from panimg.image_builders.nrrd import image_builder_nrrd
from panimg.image_builders.oct import image_builder_oct
from panimg.image_builders.tiff import image_builder_tiff
from panimg.types import ImageBuilder

DEFAULT_IMAGE_BUILDERS: Iterable[ImageBuilder] = [
    image_builder_mhd,
    image_builder_nifti,
    image_builder_nrrd,
    image_builder_dicom,
    image_builder_tiff,
    image_builder_oct,
    image_builder_fallback,
]

__all__ = [
    "image_builder_mhd",
    "image_builder_nifti",
    "image_builder_nrrd",
    "image_builder_dicom",
    "image_builder_tiff",
    "image_builder_oct",
    "image_builder_fallback",
    "DEFAULT_IMAGE_BUILDERS",
]
