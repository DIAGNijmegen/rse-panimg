import shutil
from pathlib import Path
from typing import Set
from uuid import uuid4

import pytest

from panimg import convert, post_process
from panimg.models import (
    ImageType,
    PanImgFile,
    PanImgFolder,
    PostProcessorResult,
)
from tests import RESOURCE_PATH


@pytest.mark.parametrize("post_processors", (None, []))
def test_dzi_creation(tmpdir_factory, post_processors):
    filenames = [
        "valid_tiff.tif",
        "no_dzi.tif",
        "invalid_resolutions_tiff.tif",
    ]

    input_dir = Path(tmpdir_factory.mktemp("input"))
    output_dir = Path(tmpdir_factory.mktemp("output"))

    for f in filenames:
        shutil.copy(RESOURCE_PATH / f, input_dir / f)

    result = convert(
        input_directory=input_dir,
        output_directory=output_dir,
        post_processors=post_processors,
    )

    assert len(result.new_images) == 2

    if post_processors is None:
        assert len(result.new_image_files) == 3
        assert len(result.new_folders) == 1
    else:
        assert len(result.new_image_files) == 2
        assert len(result.new_folders) == 0


def bad_post_processor(*, image_files: Set[PanImgFile]) -> PostProcessorResult:
    good_files = {
        PanImgFile(
            image_id=f.image_id, image_type=f.image_type, file=Path("foo")
        )
        for f in image_files
    }
    bad_files = {
        PanImgFile(image_id=uuid4(), image_type=f.image_type, file=Path("foo"))
        for f in image_files
    }

    good_folders = {
        PanImgFolder(image_id=f.image_id, folder=Path("foo"))
        for f in image_files
    }
    bad_folders = {
        PanImgFolder(image_id=uuid4(), folder=Path("foo")) for _ in image_files
    }

    return PostProcessorResult(
        new_image_files=good_files | bad_files,
        new_folders=good_folders | bad_folders,
    )


def test_post_processors_are_filtered():
    image_files = {
        PanImgFile(image_id=uuid4(), image_type=t, file=f"{t}")
        for t in ImageType
    }
    existing_ids = {f.image_id for f in image_files}

    raw_result = bad_post_processor(image_files=image_files)

    # The bad processor should produce twice as many outputs than inputs
    assert len(image_files) == 3
    assert len(raw_result.new_image_files) == 6
    assert len(raw_result.new_folders) == 6

    # The bad results should be filtered out
    result = post_process(
        image_files=image_files, post_processors=[bad_post_processor]
    )

    assert len(result.new_image_files) == 3
    assert len(result.new_folders) == 3
    assert {f.image_id for f in result.new_image_files} == existing_ids
    assert {f.image_id for f in result.new_folders} == existing_ids
