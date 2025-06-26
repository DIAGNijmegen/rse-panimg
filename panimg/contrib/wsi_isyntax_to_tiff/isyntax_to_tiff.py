import math
from pathlib import Path

import numpy as np
from tifffile import TiffWriter

try:
    from isyntax import ISyntax
except ImportError:
    _has_isyntax = False
else:
    _has_isyntax = True


def is_isyntax(dir_path):
    try:
        path = Path(dir_path)
        files = list(path.iterdir())
        with ISyntax.open(files):
            return True
    except Exception:
        return False


def isyntax_to_tiff(input_path, output_path):
    """Convert iSyntax WSI to TIFF format.

    This function converts an iSyntax WSI file to a TIFF file using the pyisyntax
    library.

    Parameters
    ----------
    input_path: str
        Path to the iSyntax WSI file.
    output_path: str
        Path to the output TIFF file."""
    if not _has_isyntax:
        raise ImportError("pyisyntax not installed")
    path = Path(input_path)
    image = ISyntax.open(path)
    wsi = image.wsi

    with TiffWriter(output_path, bigtiff=True) as tif:

        def tiler(getter, level_idx, cols, rows):
            for row in range(rows):
                for col in range(cols):
                    im_rgb = np.asarray(
                        getter(
                            col * image.tile_width,
                            row * image.tile_width,
                            image.tile_width,
                            image.tile_height,
                            level_idx,
                        )
                    )[..., :3]
                    yield im_rgb

        for level_idx, level in enumerate(wsi.levels):
            col = int(math.ceil(level.width / image.tile_width))
            row = int(math.ceil(level.height / image.tile_height))

            shape = (level.height, level.width, 3)

            level_tiler = tiler(image.read_region, level_idx, col, row)

            resolution = (
                int(1e4 / level.mpp_x),
                int(1e4 / level.mpp_y),
            )

            sub_filetype = 1 if level_idx != 0 else None

            tif.write(
                level_tiler,
                dtype="uint8",
                shape=shape,
                tile=(image.tile_height, image.tile_width),
                photometric="rgb",
                compression="jpeg",
                subsampling=(1, 1),
                resolution=resolution,
                resolutionunit="CENTIMETER",
                description="Converted from iSyntax",
                subfiletype=sub_filetype,
            )

    image.close()
