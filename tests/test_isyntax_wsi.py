import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from isyntax import ISyntax
from tifffile import TiffFile

from panimg.contrib.wsi_isyntax_to_tiff.isyntax_to_tiff import isyntax_to_tiff
from tests import RESOURCE_PATH


@pytest.fixture(scope="session", autouse=True)
def downloaded_isyntax_image():
    url = "https://zenodo.org/record/5037046/files/testslide.isyntax"
    image_path = RESOURCE_PATH / "isyntax_wsi" / "testslide.isyntax"
    image_path.parent.mkdir()

    if not image_path.exists():
        urllib.request.urlretrieve(url, image_path)

    return image_path


def test_isyntax_to_tiff(downloaded_isyntax_image):
    assert downloaded_isyntax_image.exists()
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
