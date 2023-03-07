import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from panimg.models import ImageType, PanImgFile
from panimg.post_processors.tiff_to_dzi import tiff_to_dzi
from tests import RESOURCE_PATH


def test_dzi_creation(tmpdir_factory):
    filename = "valid_tiff.tif"

    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(RESOURCE_PATH / filename, temp_file)

    image_file = PanImgFile(
        image_id=uuid4(), image_type=ImageType.TIFF, file=temp_file
    )

    result = tiff_to_dzi(image_files={image_file})

    assert len(result.new_image_files) == 1

    new_file = result.new_image_files.pop()

    assert new_file.image_id == image_file.image_id
    assert new_file.image_type == ImageType.DZI
    assert (
        new_file.file == image_file.file.parent / f"{image_file.image_id}.dzi"
    )
    assert (
        new_file.directory
        == image_file.file.parent / f"{image_file.image_id}_files"
    )

    assert len(list((new_file.directory).rglob("*.jpeg"))) == 9


def test_no_exception_when_failed(tmpdir_factory, caplog):
    filename = "no_dzi.tif"

    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(RESOURCE_PATH / filename, temp_file)

    image_file = PanImgFile(
        image_id=uuid4(), image_type=ImageType.TIFF, file=temp_file
    )

    result = tiff_to_dzi(image_files={image_file})

    assert len(result.new_image_files) == 0

    # The last warning should be from our logger
    last_log = caplog.records[-1]
    assert last_log.name == "panimg.post_processors.tiff_to_dzi"
    assert last_log.levelname == "WARNING"
    assert "Could not create DZI for" in last_log.message


@pytest.mark.parametrize("image_type", (ImageType.DZI, ImageType.MHD))
def test_non_tiff_skipped(tmpdir_factory, image_type):
    filename = "valid_tiff.tif"

    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(RESOURCE_PATH / filename, temp_file)

    image_file = PanImgFile(
        image_id=uuid4(), image_type=image_type, file=temp_file
    )

    result = tiff_to_dzi(image_files={image_file})

    assert len(result.new_image_files) == 0
