from panimg.post_processors.sitk_pixel_range import sitk_pixel_range
from panimg.post_processors.tiff_to_dzi import tiff_to_dzi

DEFAULT_POST_PROCESSORS = [tiff_to_dzi, sitk_pixel_range]

__all__ = ["tiff_to_dzi", "sitk_pixel_range", "DEFAULT_POST_PROCESSORS"]
