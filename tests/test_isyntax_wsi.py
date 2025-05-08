from pathlib import Path
from tempfile import TemporaryDirectory

from tifffile import TiffFile

from panimg.contrib.wsi_isyntax_to_tiff.isyntax_to_tiff import isyntax_to_tiff

try:
    from isyntax import ISyntax
except ImportError:
    _has_isyntax = False
else:
    _has_isyntax = True


def test_isyntax_to_tiff(downloaded_isyntax_image):
    if not _has_isyntax:
        raise ImportError(
            "Install pyisyntax to convert isyntax files: pip install pyisyntax."
        )
    with TemporaryDirectory() as output_directory:
        converted_tiff = Path(output_directory) / "output.tiff"
        isyntax_to_tiff(downloaded_isyntax_image, converted_tiff)
        with ISyntax.open(downloaded_isyntax_image) as o_tif:
            with TiffFile(converted_tiff) as c_tif:
                assert o_tif.level_count == len(c_tif.pages)
                for i in range(0, o_tif.wsi.level_count):
                    assert (
                        o_tif.wsi.get_level(i).height
                        == c_tif.pages[i].shape[0]
                    )
                    assert (
                        o_tif.wsi.get_level(i).width == c_tif.pages[i].shape[1]
                    )
                    assert o_tif.tile_height == c_tif.pages[i].tile[0]
                    assert o_tif.tile_width == c_tif.pages[i].tile[1]
