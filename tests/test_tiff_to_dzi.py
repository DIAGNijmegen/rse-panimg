import shutil
from pathlib import Path
from uuid import uuid4

from panimg.models import ImageType, PanImgFile
from panimg.post_processors.tiff_to_dzi import tiff_to_dzi
from tests import RESOURCE_PATH


def test_dzi_creation(tmpdir_factory):
    filename = "valid_tiff.tif"

    # Copy resource file to writable temp folder
    temp_file = Path(tmpdir_factory.mktemp("temp") / filename)
    shutil.copy(RESOURCE_PATH / filename, temp_file)

    image_file = PanImgFile(
        image_id=uuid4(), image_type=ImageType.TIFF, file=temp_file
    )

    result = tiff_to_dzi(image_files={image_file})

    assert len(result) == 1

    new_file = result.pop()

    assert new_file.image_id == image_file.image_id
    assert new_file.image_type == ImageType.DZI
    assert (
        new_file.file == image_file.file.parent / f"{image_file.image_id}.dzi"
    )
