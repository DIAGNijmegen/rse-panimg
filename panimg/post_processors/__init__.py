from panimg_models import PostProcessorOptions

from panimg.post_processors.tiff_to_dzi import tiff_to_dzi

# DEFAULT_POST_PROCESSORS are used directly by Grand Challenge
# DO NOT CHANGE THEM without considering the impact there.
DEFAULT_POST_PROCESSORS = [tiff_to_dzi]


POST_PROCESSOR_OPTIONS_TO_IMPLEMENTATION = {
    PostProcessorOptions.DZI: tiff_to_dzi,
}

__all__ = [
    "tiff_to_dzi",
    "DEFAULT_POST_PROCESSORS",
    "PostProcessorOptions",
    "POST_PROCESSOR_OPTIONS_TO_IMPLEMENTATION",
]
