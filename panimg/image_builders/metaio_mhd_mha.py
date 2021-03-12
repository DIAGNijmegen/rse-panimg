"""
Image builder for MetaIO mhd/mha files.

See: https://itk.org/Wiki/MetaIO/Documentation
"""
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Set, Tuple, Union

from panimg.image_builders.metaio_utils import (
    load_sitk_image,
    parse_mh_header,
)
from panimg.image_builders.utils import convert_itk_to_internal
from panimg.models import PanImg, PanImgFile, PanImgResult


def image_builder_mhd(  # noqa: C901
    *, files: Set[Path], output_directory: Path, **_
) -> PanImgResult:
    """
    Constructs image objects by inspecting files in a directory.

    Parameters
    ----------
    path: Path
        Path to a directory that contains all images that were uploaded during
        an upload session.

    Returns
    -------
    A tuple of
     - all detected images
     - files associated with the detected images
     - path->error message map describing what is wrong with a given file
    """
    element_data_file_key = "ElementDataFile"

    def detect_mhd_file(headers: Dict[str, str], path: Path) -> bool:
        try:
            data_file = headers[element_data_file_key]
        except KeyError:
            return False

        if data_file == "LOCAL":
            return False

        data_file_path = (path / Path(data_file)).resolve(strict=False)

        if path not in data_file_path.parents:
            raise ValueError(
                f"{element_data_file_key} references a file which is not in "
                f"the uploaded data folder"
            )
        if not data_file_path.is_file():
            raise ValueError("Data container of mhd file is missing")
        return True

    def detect_mha_file(headers: Mapping[str, Union[str, None]]) -> bool:
        data_file = headers.get(element_data_file_key, None)
        return data_file == "LOCAL"

    def convert_itk_file(
        *, filename: Path, output_dir: Path,
    ) -> Tuple[PanImg, Sequence[PanImgFile]]:
        try:
            simple_itk_image = load_sitk_image(filename.absolute())
        except RuntimeError:
            raise ValueError("SimpleITK cannot open file")

        return convert_itk_to_internal(
            simple_itk_image=simple_itk_image,
            name=filename.name,
            output_directory=output_dir,
        )

    def format_error(message: str) -> str:
        return f"Mhd image builder: {message}"

    new_images = set()
    new_image_files: Set[PanImgFile] = set()
    consumed_files = set()
    invalid_file_errors: Dict[Path, List[str]] = defaultdict(list)
    for file in files:
        try:
            parsed_headers = parse_mh_header(file)
        except ValueError:
            # Maybe add .mhd and .mha files here as "processed" but with errors
            continue

        try:
            is_hd_or_mha = detect_mhd_file(
                parsed_headers, file.parent
            ) or detect_mha_file(parsed_headers)
        except ValueError as e:
            invalid_file_errors[file].append(format_error(str(e)))
            continue

        if is_hd_or_mha:
            file_dependency = None
            if parsed_headers[element_data_file_key] != "LOCAL":
                file_dependency = (
                    file.parent / parsed_headers[element_data_file_key]
                )
                if not file_dependency.is_file():
                    invalid_file_errors[file].append(
                        format_error("Cannot find data file")
                    )
                    continue

            n_image, n_image_files = convert_itk_file(
                filename=file, output_dir=output_directory
            )
            new_images.add(n_image)
            new_image_files |= set(n_image_files)

            consumed_files.add(file)
            if file_dependency is not None:
                consumed_files.add(file_dependency)

    return PanImgResult(
        consumed_files=consumed_files,
        file_errors=invalid_file_errors,
        new_images=new_images,
        new_image_files=new_image_files,
        new_folders=set(),
    )
