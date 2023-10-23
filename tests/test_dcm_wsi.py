from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from tifffile import TiffFile
from wsidicom import WsiDicom

from panimg.contrib.wsi_dcm_to_tiff.dcm_to_tiff import dcm_to_tiff
from tests import RESOURCE_PATH


@pytest.mark.parametrize(
    "src",
    (
        RESOURCE_PATH / "dicom_wsi/sparse_with_bot",
        RESOURCE_PATH / "dicom_wsi/sparse_no_bot",
        RESOURCE_PATH / "dicom_wsi/full_with_bot",
        RESOURCE_PATH / "dicom_wsi/full_no_bot",
    ),
)
def test_dcm_to_tiff(src: Path):
    with TemporaryDirectory() as output_directory:
        converted_tiff = Path(output_directory) / "output.tiff"
        dcm_to_tiff(src, converted_tiff)
        files = {f for f in src.rglob("*") if f.is_file()}
        with WsiDicom.open(files) as o_tif:
            with TiffFile(converted_tiff) as c_tif:
                assert len(o_tif.levels) == len(c_tif.pages)
                for i in range(0, len(o_tif.levels)):
                    assert (
                        o_tif.collection[i].size.height
                        == c_tif.pages[i].shape[0]
                    )
                    assert (
                        o_tif.collection[i].size.width
                        == c_tif.pages[i].shape[1]
                    )
                    assert (
                        o_tif.collection[i].tile_size.height
                        == c_tif.pages[i].tile[0]
                    )
                    assert (
                        o_tif.collection[i].tile_size.width
                        == c_tif.pages[i].tile[1]
                    )
