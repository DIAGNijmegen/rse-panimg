import os
import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import DefaultDict
from uuid import UUID, uuid4

import tifffile

from panimg.contrib.wsi_dcm_to_tiff.dcm_to_tiff import (
    dcm_to_tiff as wsi_dcm_to_tiff,
)
from panimg.contrib.wsi_isyntax_to_tiff.isyntax_to_tiff import (
    isyntax_to_tiff as wsi_isyntax_to_tiff,
)
from panimg.exceptions import UnconsumedFilesException, ValidationError
from panimg.image_builders.dicom import get_dicom_headers_by_study
from panimg.models import MAXIMUM_SEGMENTS_LENGTH, ColorSpace, TIFFImage

try:
    from isyntax import ISyntax
except ImportError:
    _has_isyntax = False
else:
    _has_isyntax = True

DICOM_WSI_STORAGE_ID = "1.2.840.10008.5.1.4.1.1.77.1.6"


def format_error(message: str) -> str:
    return f"TIFF image builder: {message}"


@dataclass
class GrandChallengeTiffFile:
    path: Path
    pk: UUID = field(default_factory=uuid4)
    image_width: int = 0
    image_height: int = 0
    resolution_levels: int = 0
    color_space: ColorSpace | None = None
    voxel_width_mm: float = 0
    voxel_height_mm: float = 0
    associated_files: list[Path] = field(default_factory=list)
    min_voxel_value: int | None = None
    max_voxel_value: int | None = None

    def validate(self) -> None:
        if not self.image_width:
            raise ValidationError(
                "Not a valid tif: Image width could not be determined"
            )
        if not self.image_height:
            raise ValidationError(
                "Not a valid tif: Image height could not be determined"
            )
        if not self.resolution_levels:
            raise ValidationError(
                "Not a valid tif: Resolution levels not valid"
            )
        if not self.voxel_width_mm:
            raise ValidationError(
                "Not a valid tif: Voxel width could not be determined"
            )
        if not self.voxel_height_mm:
            raise ValidationError(
                "Not a valid tif: Voxel height could not be determined"
            )
        if not self.color_space:
            raise ValidationError(
                "Not a valid tif: Color space could not be determined"
            )

    @property
    def segments(self) -> frozenset[int] | None:
        if self.min_voxel_value is None or self.max_voxel_value is None:
            return None
        if (
            self.max_voxel_value - self.min_voxel_value
            >= MAXIMUM_SEGMENTS_LENGTH
        ):
            return None

        return frozenset(range(self.min_voxel_value, self.max_voxel_value + 1))


def _get_tag_value(tags, tag):
    try:
        return tags[tag].value
    except (KeyError, AttributeError):
        return None


def _get_voxel_spacing_mm(tags, tag):
    """
    Calculate the voxel spacing in mm.

    Use the set of tags from the tiff image to calculate the spacing for a
    particular dimension. Supports INCH and CENTIMETER resolution units.

    Parameters
    ----------
    tags
        The collection of tags from the tif file.
    tag
        The tag that contains the resolution of the tif file along the
        dimension of interest.

    Raises
    ------
    ValidationError
        Raised if an unrecognised resolution unit is used.


    Returns
    -------
        The voxel spacing in mm.

    """
    try:
        # Resolution is a tuple of the number of pixels and the length of the
        # image in cm or inches, depending on resolution unit
        resolution_unit = _get_tag_value(tags, "ResolutionUnit").name
        resolution = _get_tag_value(tags, tag)
        if resolution_unit == "INCH":
            return 25.4 / (resolution[0] / resolution[1])
        elif resolution_unit == "CENTIMETER":
            return 10 / (resolution[0] / resolution[1])
        raise ValidationError(
            f"Invalid resolution unit {resolution_unit}" f" in tiff file"
        )
    except (ZeroDivisionError, TypeError, IndexError) as e:
        raise ValidationError("Invalid resolution in tiff file") from e


def _extract_openslide_properties(
    *, gc_file: GrandChallengeTiffFile, image
) -> GrandChallengeTiffFile:
    if not gc_file.voxel_width_mm and "openslide.mpp-x" in image.properties:
        gc_file.voxel_width_mm = (
            float(image.properties["openslide.mpp-x"]) / 1000
        )
    if not gc_file.voxel_height_mm and "openslide.mpp-y" in image.properties:
        gc_file.voxel_height_mm = (
            float(image.properties["openslide.mpp-y"]) / 1000
        )
    if (
        not gc_file.image_height
        and "openslide.level[0].height" in image.properties
    ):
        gc_file.image_height = int(
            image.properties["openslide.level[0].height"]
        )

    if (
        not gc_file.image_width
        and "openslide.level[0].width" in image.properties
    ):
        gc_file.image_width = int(image.properties["openslide.level[0].width"])

    if (
        not gc_file.resolution_levels
        and "openslide.level-count" in image.properties
    ):
        gc_file.resolution_levels = int(
            image.properties["openslide.level-count"]
        )
    return gc_file


def _extract_tags(
    *,
    gc_file: GrandChallengeTiffFile,
    pages: tifffile.tifffile.TiffPages,
    byteorder: str,
) -> GrandChallengeTiffFile:
    """
    Extracts tags form a tiff file loaded with tifffile for use in grand challenge
    :param pages: The pages and tags from tifffile
    :return: The GrandChallengeTiffFile with the properties defined in the tags
    """
    if not pages:
        return gc_file

    tags = pages[0].tags

    gc_file.resolution_levels = len(pages)

    gc_file.color_space = _get_color_space(
        color_space_string=_get_tag_value(
            tags, "PhotometricInterpretation"
        ).name
    )
    gc_file.image_width = _get_tag_value(tags, "ImageWidth")
    gc_file.image_height = _get_tag_value(tags, "ImageLength")

    #  some formats like the Philips tiff don't have the spacing in their tags,
    #  we retrieve them later with OpenSlide
    if "XResolution" in tags:
        gc_file.voxel_width_mm = _get_voxel_spacing_mm(tags, "XResolution")
        gc_file.voxel_height_mm = _get_voxel_spacing_mm(tags, "YResolution")

    get_min_max_sample_value(tags=tags, gc_file=gc_file, byteorder=byteorder)

    return gc_file


def _get_color_space(*, color_space_string) -> ColorSpace | None:
    color_space_string = color_space_string.upper()

    if color_space_string == "MINISBLACK":
        color_space = ColorSpace.GRAY
    else:
        try:
            color_space = ColorSpace[color_space_string]
        except KeyError:
            return None

    return color_space


def get_min_max_sample_value(*, tags, gc_file, byteorder):
    samples_per_pixel = _get_tag_value(tags, "SamplesPerPixel")
    sample_format = _get_tag_value(tags, "SampleFormat")
    if samples_per_pixel != 1 or sample_format not in (None, 1, 2):
        return

    signed = sample_format == 2
    byteorder = {"<": "little", ">": "big"}.get(byteorder, "big")

    def get_voxel_value(first_tag, second_tag):
        voxel_value = _get_tag_value(tags, first_tag) or _get_tag_value(
            tags, second_tag
        )
        if isinstance(voxel_value, bytes):
            return int.from_bytes(
                voxel_value, byteorder=byteorder, signed=signed
            )
        return voxel_value

    gc_file.min_voxel_value = get_voxel_value(
        "MinSampleValue", "SMinSampleValue"
    )
    gc_file.max_voxel_value = get_voxel_value(
        "MaxSampleValue", "SMaxSampleValue"
    )


def _load_with_tiff(
    *, gc_file: GrandChallengeTiffFile
) -> GrandChallengeTiffFile:
    tiff_file = tifffile.TiffFile(str(gc_file.path.absolute()))
    gc_file = _extract_tags(
        gc_file=gc_file, pages=tiff_file.pages, byteorder=tiff_file.byteorder
    )
    return gc_file


def _load_with_openslide(
    *, gc_file: GrandChallengeTiffFile
) -> GrandChallengeTiffFile:
    import openslide

    open_slide_file = openslide.open_slide(str(gc_file.path.absolute()))
    gc_file = _extract_openslide_properties(
        gc_file=gc_file, image=open_slide_file
    )
    return gc_file


mirax_pattern = r"INDEXFILE\s?=\s?.|FILE_\d+\s?=\s?."
# vms (and vmu) files contain key value pairs, where the ImageFile keys
# can have the following format:
# ImageFile =, ImageFile(x,y) ImageFile(z,x,y)
vms_pattern = (
    r"ImageFile(\(\d*,\d*(,\d)?\))?\s?=\s?."
    r"|MapFile\s?=\s?."
    r"|OptimisationFile\s?=\s?."
    r"|MacroImage\s?=\s?."
)


def _get_mrxs_files(mrxs_file: Path):
    # Find Slidedat.ini, which provides us with all the other file names
    name, _ = os.path.splitext(mrxs_file.name)
    slide_dat = mrxs_file.parent / name / "Slidedat.ini"
    file_matched = []
    if not slide_dat.exists():
        slide_dat = [
            f
            for f in slide_dat.parent.iterdir()
            if f.name.lower() == slide_dat.name.lower()
        ][0]
    with open(slide_dat) as f:
        lines = [
            line for line in f.readlines() if re.match(mirax_pattern, line)
        ]
        for line in lines:
            original_name = line.split("=")[1].strip()
            if os.path.exists(slide_dat.parent / original_name):
                file_matched.append(slide_dat.parent / original_name)
        file_matched.append(slide_dat)
    return file_matched


def _get_vms_files(vms_file: Path):
    file_matched = []
    with open(str(vms_file.absolute())) as f:
        lines = [line for line in f.readlines() if re.match(vms_pattern, line)]
        for line in lines:
            original_name = line.split("=")[1].strip()
            if os.path.exists(vms_file.parent / original_name):
                file_matched.append(vms_file.parent / original_name)
        return file_matched


def _convert(
    *,
    files: list[Path],
    associated_files_getter: Callable[[Path], list[Path]] | None,
    output_directory: Path,
    file_errors: dict[Path, list[str]],
) -> list[GrandChallengeTiffFile]:
    converted_files: list[GrandChallengeTiffFile] = []
    associated_files: list[Path] = []

    for file in files:
        try:
            gc_file = GrandChallengeTiffFile(file)

            if associated_files_getter:
                associated_files = associated_files_getter(gc_file.path)

            tiff_file = _convert_to_tiff(
                path=file,
                pk=gc_file.pk,
                output_directory=output_directory,
            )
        except Exception:
            file_errors[file].append(
                format_error(f"Could not convert file to TIFF: {file.name}")
            )
            continue
        else:
            gc_file.path = tiff_file
            gc_file.associated_files = associated_files
            gc_file.associated_files.append(file)
            converted_files.append(gc_file)

    return converted_files


def _convert_to_tiff(*, path: Path, pk: UUID, output_directory: Path) -> Path:
    import pyvips

    major = pyvips.base.version(0)
    minor = pyvips.base.version(1)

    if not (major > 8 or (major == 8 and minor >= 10)):
        raise RuntimeError(
            f"libvips {major}.{minor} is too old - requires >= 8.10"
        )

    new_file_name = output_directory / path.name / f"{pk}.tif"
    new_file_name.parent.mkdir()

    image = pyvips.Image.new_from_file(
        str(path.absolute()), access="sequential"
    )

    image.write_to_file(
        str(new_file_name.absolute()),
        tile=True,
        pyramid=True,
        bigtiff=True,
        compression="jpeg",
        Q=70,
    )

    return new_file_name


def _convert_dicom_wsi_dir(
    gc_file: GrandChallengeTiffFile,
    file: Path,
    output_directory: Path,
    file_errors: dict[Path, list[str]],
):
    wsidicom_dir = file.parent
    try:
        new_file_name = output_directory / file.name / f"{gc_file.pk}.tif"
        new_file_name.parent.mkdir()

        wsi_dcm_to_tiff(wsidicom_dir, new_file_name)
    except Exception:
        file_errors[file].append(
            format_error(f"Could not convert dicom-wsi to TIFF: {file.name}")
        )
    else:
        gc_file.path = new_file_name
        gc_file.associated_files = [
            f for f in wsidicom_dir.iterdir() if f.is_file()
        ]
    return gc_file


def _convert_isyntax_file(
    gc_file: GrandChallengeTiffFile,
    file: Path,
    output_directory: Path,
    file_errors: dict[Path, list[str]],
):
    try:
        new_file_name = output_directory / file.name / f"{gc_file.pk}.tif"
        new_file_name.parent.mkdir()

        wsi_isyntax_to_tiff(file, new_file_name)
    except Exception:
        file_errors[file].append(
            format_error(f"Could not convert iSyntax to TIFF: {file.name}")
        )
    else:
        gc_file.path = new_file_name
        gc_file.associated_files = [file]
    return gc_file


def _find_valid_dicom_wsi_files(
    files: set[Path], file_errors: DefaultDict[Path, list[str]]
):
    """
    Gets the headers for all dicom files on path and validates them.

    Parameters
    ----------
    files
        Paths images that were uploaded during an upload session.

    file_errors
        Dictionary in which reading errors are recorded per file

    Returns
    -------
    A dictionary with filename as key, and all other files belonging to that study
    as value

    """
    # Try and get dicom files; ignore errors
    dicom_errors = file_errors.copy()
    studies = get_dicom_headers_by_study(files=files, file_errors=dicom_errors)
    result: dict[Path, list[Path]] = {}

    for key in studies:
        headers = studies[key]["headers"]
        if not headers:
            continue

        if not all(
            header["data"].SOPClassUID == DICOM_WSI_STORAGE_ID
            for header in headers
        ):
            for d in headers:
                file_errors[d["file"]].append(
                    format_error("Non-WSI-DICOM not supported by TIFF builder")
                )
        else:
            result[Path(headers[0]["file"])] = [
                Path(h["file"]) for h in headers[1:]
            ]

    def associated_files(file_path: Path):
        return result[file_path]

    return list(result.keys()), associated_files


def _find_valid_isyntax_wsi_files(
    files: set[Path], file_errors: DefaultDict[Path, list[str]]
):
    """
    Gets the headers for all isyntax files on path and validates them.

    Parameters
    ----------
    files
        Paths images that were uploaded during an upload session.

    file_errors
        Dictionary in which reading errors are recorded per file

    Returns
    -------
    A dictionary with filename as key, and all other files belonging to that study
    as value

    """
    result: dict[Path, list[Path]] = {}

    isyntax_files = [
        file for file in files if file.suffix.casefold() == ".isyntax"
    ]
    for isyntax_file in isyntax_files:
        try:
            if not _has_isyntax:
                raise ImportError("Install pyisyntax to convert isyntax files")
            with ISyntax.open(isyntax_file) as image:
                wsi = image.wsi
                if not wsi.level_count:
                    file_errors[isyntax_file].append(
                        format_error("No levels found in iSyntax file")
                    )
                else:
                    result[isyntax_file] = [isyntax_file]
        except Exception:
            file_errors[isyntax_file].append(
                format_error("Could not open iSyntax file")
            )

    def associated_files(file_path: Path):
        return result[file_path]

    return list(result.keys()), associated_files


def _load_gc_files(
    *,
    files: set[Path],
    output_directory: Path,
    file_errors: DefaultDict[Path, list[str]],
) -> list[GrandChallengeTiffFile]:
    loaded_files: list[GrandChallengeTiffFile] = []

    complex_file_handlers = {
        ".mrxs": _get_mrxs_files,
        ".vms": _get_vms_files,
        ".vmu": _get_vms_files,
        ".svs": None,
        ".ndpi": None,
        ".scn": None,
        ".bif": None,
    }

    dicom_files, handler = _find_valid_dicom_wsi_files(files, file_errors)
    for dicom_file in dicom_files:
        gc_file = GrandChallengeTiffFile(dicom_file)
        gc_file = _convert_dicom_wsi_dir(
            gc_file=gc_file,
            file=dicom_file,
            output_directory=output_directory,
            file_errors=file_errors,
        )
        loaded_files.append(gc_file)

    isyntax_files, handler = _find_valid_isyntax_wsi_files(files, file_errors)
    for isyntax_file in isyntax_files:
        gc_file = GrandChallengeTiffFile(isyntax_file)
        gc_file = _convert_isyntax_file(
            gc_file=gc_file,
            file=isyntax_file,
            output_directory=output_directory,
            file_errors=file_errors,
        )
        loaded_files.append(gc_file)

    for ext, handler in complex_file_handlers.items():
        complex_files = [file for file in files if file.suffix.lower() == ext]
        if len(complex_files) > 0:
            converted_files = _convert(
                files=complex_files,
                associated_files_getter=handler,
                output_directory=output_directory,
                file_errors=file_errors,
            )
            loaded_files += converted_files

    # don't handle files that are associated files
    for file in files:
        if not any(g.path == file for g in loaded_files) and not any(
            file in g.associated_files
            for g in loaded_files
            if g.associated_files is not None
        ):
            gc_file = GrandChallengeTiffFile(file)
            loaded_files.append(gc_file)

    return loaded_files


def image_builder_tiff(  # noqa: C901
    *, files: set[Path]
) -> Iterator[TIFFImage]:
    file_errors: DefaultDict[Path, list[str]] = defaultdict(list)

    with TemporaryDirectory() as output_directory:
        loaded_files = _load_gc_files(
            files=files,
            output_directory=Path(output_directory),
            file_errors=file_errors,
        )

        for gc_file in loaded_files:
            # try and load image with tiff file
            try:
                gc_file = _load_with_tiff(gc_file=gc_file)
            except Exception:
                file_errors[gc_file.path].append(
                    format_error("Could not open file with tifffile.")
                )

            # try and load image with open slide
            try:
                gc_file = _load_with_openslide(gc_file=gc_file)
            except Exception:
                file_errors[gc_file.path].append(
                    format_error("Could not open file with OpenSlide.")
                )

            # validate
            try:
                gc_file.validate()
                if gc_file.color_space is None:
                    # TODO This needs to be solved by refactoring of
                    # GrandChallengeTiffFile
                    raise RuntimeError("Color space not found")
            except ValidationError as e:
                file_errors[gc_file.path].append(
                    format_error(f"Validation error: {e}.")
                )
                continue

            if gc_file.associated_files:
                consumed_files = {
                    f.absolute() for f in gc_file.associated_files
                }
            else:
                consumed_files = {gc_file.path.absolute()}

            yield TIFFImage(
                file=gc_file.path,
                name=gc_file.path.name,
                consumed_files=consumed_files,
                width=gc_file.image_width,
                height=gc_file.image_height,
                voxel_width_mm=gc_file.voxel_width_mm,
                voxel_height_mm=gc_file.voxel_height_mm,
                resolution_levels=gc_file.resolution_levels,
                color_space=gc_file.color_space,
                segments=gc_file.segments,
            )

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
