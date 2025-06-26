from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from tifffile import TiffFile

from panimg.contrib.wsi_isyntax_to_tiff.isyntax_to_tiff import isyntax_to_tiff


def test_isyntax_to_tiff(downloaded_isyntax_image):
    if not downloaded_isyntax_image.exists():
        pytest.xfail(
            reason="iSyntax resource is not available. "
            "To run this test, download the file using --download-files."
        )

    from isyntax import ISyntax

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
