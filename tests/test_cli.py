import shutil
from uuid import uuid4

from click.testing import CliRunner
from pydantic import TypeAdapter

from panimg.cli import convert_cli, post_process_cli
from panimg.models import PanImgResult, PostProcessorResult
from tests import RESOURCE_PATH


def test_convert_cli_no_files(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()

    runner = CliRunner()
    cli_result = runner.invoke(
        convert_cli,
        ["--input-dir", str(input_dir), "--output-dir", str(output_dir)],
    )
    assert cli_result.output == (
        '{"new_images":[],"new_image_files":[],'
        '"consumed_files":[],"file_errors":{}}\n'
    )
    assert cli_result.exit_code == 0


def test_convert_cli_with_post_processing_and_dicom(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()

    # 3 new files, all supported
    shutil.copy(str(RESOURCE_PATH / "image10x10x10.mha"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "valid_tiff.tif"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "dicom_2d" / "cxr.dcm"), str(input_dir))

    runner = CliRunner()
    cli_result = runner.invoke(
        convert_cli,
        ["--input-dir", str(input_dir), "--output-dir", str(output_dir)],
    )
    assert cli_result.exit_code == 0

    panimg_result: PanImgResult = TypeAdapter(PanImgResult).validate_json(
        cli_result.output.splitlines()[-1]
    )

    assert {im.name for im in panimg_result.new_images} == {
        "1.2.392.200036.9125.0.199302241758.16-0",
        "valid_tiff.tif",
        "image10x10x10.mha",
    }
    assert len(panimg_result.new_image_files) == 4
    assert {im.image_type for im in panimg_result.new_image_files} == {
        "DZI",
        "TIFF",
        "MHD",
    }


def test_convert_cli_with_post_processing_no_dicom(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()

    # 3 new files, DICOM should be skipped
    shutil.copy(str(RESOURCE_PATH / "image10x10x10.mha"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "valid_tiff.tif"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "dicom_2d" / "cxr.dcm"), str(input_dir))

    runner = CliRunner()
    cli_result = runner.invoke(
        convert_cli,
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--only-metaio-tiff-builders",
        ],
    )
    assert cli_result.exit_code == 0

    panimg_result: PanImgResult = TypeAdapter(PanImgResult).validate_json(
        cli_result.output.splitlines()[-1]
    )

    assert {im.name for im in panimg_result.new_images} == {
        "valid_tiff.tif",
        "image10x10x10.mha",
    }
    assert len(panimg_result.new_image_files) == 3
    assert {im.image_type for im in panimg_result.new_image_files} == {
        "DZI",
        "TIFF",
        "MHD",
    }


def test_convert_cli_no_post_processing_no_dicom(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()

    # 3 new files, DICOM and post processing should be skipped
    shutil.copy(str(RESOURCE_PATH / "image10x10x10.mha"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "valid_tiff.tif"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "dicom_2d" / "cxr.dcm"), str(input_dir))

    runner = CliRunner()
    cli_result = runner.invoke(
        convert_cli,
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--no-post-processing",
            "--only-metaio-tiff-builders",
        ],
    )
    assert cli_result.exit_code == 0

    panimg_result: PanImgResult = TypeAdapter(PanImgResult).validate_json(
        cli_result.output.splitlines()[-1]
    )

    assert {im.name for im in panimg_result.new_images} == {
        "valid_tiff.tif",
        "image10x10x10.mha",
    }
    assert len(panimg_result.new_image_files) == 2
    assert {im.image_type for im in panimg_result.new_image_files} == {
        "TIFF",
        "MHD",
    }


def test_convert_cli_no_post_processing_and_dicom(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"

    input_dir.mkdir()

    # 3 new files, all supported
    shutil.copy(str(RESOURCE_PATH / "image10x10x10.mha"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "valid_tiff.tif"), str(input_dir))
    shutil.copy(str(RESOURCE_PATH / "dicom_2d" / "cxr.dcm"), str(input_dir))

    runner = CliRunner()
    cli_result = runner.invoke(
        convert_cli,
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--no-post-processing",
        ],
    )
    assert cli_result.exit_code == 0

    panimg_result: PanImgResult = TypeAdapter(PanImgResult).validate_json(
        cli_result.output.splitlines()[-1]
    )

    assert {im.name for im in panimg_result.new_images} == {
        "1.2.392.200036.9125.0.199302241758.16-0",
        "valid_tiff.tif",
        "image10x10x10.mha",
    }
    assert len(panimg_result.new_image_files) == 3
    assert {im.image_type for im in panimg_result.new_image_files} == {
        "TIFF",
        "MHD",
    }


def test_post_process_cli_no_dzi():
    runner = CliRunner()
    cli_result = runner.invoke(
        post_process_cli,
        [
            "--image-id",
            str(uuid4()),
            "--image-type",
            "MHD",
            "--input-file",
            RESOURCE_PATH / "image10x10x10.mha",
        ],
    )
    assert cli_result.stdout == '{"new_image_files":[]}\n'
    assert cli_result.exit_code == 0

    post_processor_result: PostProcessorResult = TypeAdapter(
        PostProcessorResult
    ).validate_json(cli_result.output.splitlines()[-1])

    assert post_processor_result.new_image_files == set()


def test_post_process_cli_dzi():
    runner = CliRunner()
    cli_result = runner.invoke(
        post_process_cli,
        [
            "--image-id",
            str(uuid4()),
            "--image-type",
            "TIFF",
            "--input-file",
            RESOURCE_PATH / "valid_tiff.tif",
        ],
    )
    assert cli_result.exit_code == 0

    post_processor_result: PostProcessorResult = TypeAdapter(
        PostProcessorResult
    ).validate_json(cli_result.output.splitlines()[-1])

    assert len(post_processor_result.new_image_files) == 1
    assert {im.image_type for im in post_processor_result.new_image_files} == {
        "DZI"
    }
