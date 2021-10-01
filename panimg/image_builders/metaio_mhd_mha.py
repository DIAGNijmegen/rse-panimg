"""
Image builder for MetaIO mhd/mha files.

See: https://itk.org/Wiki/MetaIO/Documentation
"""
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterator, List, Mapping, Set, Union

from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.image_builders.metaio_utils import (
    load_sitk_image,
    parse_mh_header,
)
from panimg.models import SimpleITKImage


def image_builder_mhd(  # noqa: C901
    *, files: Set[Path]
) -> Iterator[SimpleITKImage]:
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
    file_errors: DefaultDict[Path, List[str]] = defaultdict(list)

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

    def format_error(message: str) -> str:
        return f"Mhd image builder: {message}"

    for file in files:
        try:
            parsed_headers = parse_mh_header(file)
        except ValidationError as e:
            file_errors[file].append(
                format_error(f"Could not validate or parse ITK header. {e}")
            )
            continue

        try:
            is_hd_or_mha = detect_mhd_file(
                parsed_headers, file.parent
            ) or detect_mha_file(parsed_headers)
        except ValueError as e:
            file_errors[file].append(format_error(str(e)))
            continue

        if is_hd_or_mha:
            file_dependency = None

            if parsed_headers[element_data_file_key] != "LOCAL":
                file_dependency = (
                    file.parent / parsed_headers[element_data_file_key]
                )
                if not file_dependency.is_file():
                    file_errors[file].append(
                        format_error("Cannot find data file")
                    )
                    continue

            try:
                simple_itk_image = load_sitk_image(file.absolute())
            except ValidationError as e:
                file_errors[file].append(
                    format_error(f"Could not validate file. {e}")
                )
            except RuntimeError:
                file_errors[file].append(
                    format_error("SimpleITK could not open file.")
                )
                continue
            except ValidationError as e:
                file_errors[file].append(format_error(str(e)))
                continue

            consumed_files = {file}
            if file_dependency is not None:
                consumed_files.add(file_dependency)

            yield SimpleITKImage(
                image=simple_itk_image,
                name=file.name,
                consumed_files=consumed_files,
                spacing_valid=True,
            )
        else:
            file_errors[file].append(format_error("Not an ITK file"))
            continue

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
