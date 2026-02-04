from panimg.post_processors.tiff_to_dzi import tiff_to_dzi

# DEFAULT_POST_PROCESSORS are used directly by Grand Challenge
# DO NOT CHANGE THEM without considering the impact there.
DEFAULT_POST_PROCESSORS = [tiff_to_dzi]

__all__ = ["tiff_to_dzi", "DEFAULT_POST_PROCESSORS"]
