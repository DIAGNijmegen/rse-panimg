import logging
from collections import defaultdict, namedtuple
from math import isclose
from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

import numpy as np
import pydicom
import SimpleITK

from panimg.exceptions import UnconsumedFilesException
from panimg.models import (
    EXTRA_METADATA,
    SimpleITKImage,
    validate_metadata_value,
)

logger = logging.getLogger(__name__)

NUMPY_IMAGE_TYPES = {
    "character": SimpleITK.sitkUInt8,
    "uint8": SimpleITK.sitkUInt8,
    "uint16": SimpleITK.sitkUInt16,
    "uint32": SimpleITK.sitkUInt32,
    "uint64": SimpleITK.sitkUInt64,
    "int8": SimpleITK.sitkInt8,
    "int16": SimpleITK.sitkInt16,
    "int32": SimpleITK.sitkInt32,
    "int64": SimpleITK.sitkInt64,
    "float32": SimpleITK.sitkFloat32,
    "float64": SimpleITK.sitkFloat64,
}

OPTIONAL_METADATA_FIELDS = (
    # These fields will be included in the output mha file
    "Laterality",
    "SliceThickness",
    "WindowCenter",
    "WindowWidth",
    *[md.keyword for md in EXTRA_METADATA],
)


def format_error(message: str) -> str:
    return f"Dicom image builder: {message}"


class DicomTagNotFoundError(KeyError):
    pass


def _find_dicom_tag(dataset: pydicom.Dataset, tag: str):
    for header in dataset.iterall():
        if header.keyword == tag:
            return header.value

    raise DicomTagNotFoundError(
        f"Could not find DICOM tag {tag} in the header"
    )


def _get_headers_by_study(files, file_errors):
    """
    Gets all headers from dicom files found in path.

    Parameters
    ----------
    files
        Paths images that were uploaded during an upload session.

    file_errors
        Dictionary in which reading errors are recorded per file

    Returns
    -------
    A dictionary of sorted headers for all dicom image files found within path,
    grouped by study id.
    """
    studies = {}
    indices = {}

    for file in files:
        if not file.is_file():
            continue
        with file.open("rb") as f:
            try:
                ds = pydicom.filereader.read_partial(
                    f,
                    stop_when=lambda tag, vr, length: tag == (0x7FE0, 0x0010),
                )
                dims = f"{ds.Rows}x{ds.Columns}"
                key = f"{ds.StudyInstanceUID}-{dims}"
                studies[key] = studies.get(key, {})
                indices[ds.StudyInstanceUID] = indices.get(
                    ds.StudyInstanceUID, {}
                )
                index = indices[ds.StudyInstanceUID].get(dims)
                if index is None:
                    index = (
                        max(list(indices[ds.StudyInstanceUID].values()) + [-1])
                        + 1
                    )
                    indices[ds.StudyInstanceUID][dims] = index
                headers = studies[key].get("headers", [])
                headers.append({"file": file, "data": ds})
                studies[key]["index"] = index
                studies[key]["headers"] = headers
            except Exception as e:
                file_errors[file].append(format_error(str(e)))

    for key in studies:
        studies[key]["headers"].sort(
            key=lambda x: int(x["data"].InstanceNumber)
        )
    return studies


def _validate_dicom_files(
    files: Set[Path], file_errors: DefaultDict[Path, List[str]]
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
    A list of `dicom_dataset` named tuples per study, consisting of:
     - Headers for all dicom image files for the study
     - Number of time points
     - Number of slices per time point

    Any study with an inconsistent amount of slices per time point is discarded.
    """
    studies = _get_headers_by_study(files=files, file_errors=file_errors)
    result = []
    dicom_dataset = namedtuple(
        "dicom_dataset",
        ["headers", "n_time", "n_slices", "n_slices_per_file", "index"],
    )
    for key in studies:
        headers = studies[key]["headers"]
        index = studies[key]["index"]
        if not headers:
            continue

        data = headers[-1]["data"]
        n_files = len(headers)
        n_time = getattr(data, "TemporalPositionIndex", None)
        try:
            n_slices_per_file = len(data.PerFrameFunctionalGroupsSequence)
        except AttributeError:
            n_slices_per_file = int(getattr(data, "NumberOfFrames", 1))
        n_slices = n_files * n_slices_per_file

        if n_time is None:
            # Not a 4d dicom file
            result.append(
                dicom_dataset(
                    headers=headers,
                    n_time=n_time,
                    n_slices=n_slices,
                    n_slices_per_file=n_slices_per_file,
                    index=index,
                )
            )
        elif len(headers) % n_time > 0:
            # Invalid 4d dicom file
            for d in headers:
                file_errors[d["file"]].append(
                    format_error("Number of slices per time point differs")
                )
        else:
            # Valid 4d dicom file
            result.append(
                dicom_dataset(
                    headers=headers,
                    n_time=n_time,
                    n_slices=n_slices // n_time,
                    n_slices_per_file=n_slices_per_file,
                    index=index,
                )
            )

    del studies
    return result


def _process_dicom_file(*, dicom_ds):  # noqa: C901
    # Use first slice or volume as reference
    ref = dicom_ds.headers[0]["data"]

    # Images are either 4D or 3D (2D images get an additional axis of size 1)
    dimensions = 4 if dicom_ds.n_time and dicom_ds.n_time > 1 else 3

    pixel_dims = (dicom_ds.n_slices, int(ref.Rows), int(ref.Columns))
    if dimensions == 4:
        pixel_dims = (dicom_ds.n_time,) + pixel_dims

    # Compute rotation matrix (orientation of the image)
    try:
        orientation = _find_dicom_tag(ref, "ImageOrientationPatient")
        row_cos = orientation[:3]
        col_cos = orientation[3:]
    except DicomTagNotFoundError:
        # Tag can be missing in X-ray images for example
        row_cos = (1, 0, 0)
        col_cos = (0, 1, 0)
    direction = np.eye(dimensions, dtype=float)
    direction[:3, :3] = np.stack(
        [row_cos, col_cos, np.cross(row_cos, col_cos)], axis=1
    )

    # Find origin and compute offset between slices (= spacing)
    if (
        dicom_ds.n_slices_per_file == 1
        or "PerFrameFunctionalGroupsSequence" not in ref
    ):
        # One or multiple regular DICOM files
        file_origins = [
            np.array(partial["data"].ImagePositionPatient, dtype=float)
            for partial in dicom_ds.headers
            if "ImagePositionPatient" in partial["data"]
        ]
    else:
        # An enhanced DICOM file with the entire volume stored in one file
        file_origins = []
        for frame in ref.PerFrameFunctionalGroupsSequence:
            try:
                file_origin = _find_dicom_tag(frame, "ImagePositionPatient")
            except DicomTagNotFoundError:
                pass
            else:
                file_origins.append(np.array(file_origin, dtype=float))

    try:
        ref_origin = tuple(file_origins[0])
    except IndexError:
        ref_origin = (0, 0, 0)

    origin = None
    origin_diff = np.array((0, 0, 0), dtype=float)
    origin_seen = []
    n_diffs = 0
    for file_origin in file_origins:
        if any(np.allclose(file_origin, o) for o in origin_seen):
            continue  # ignore duplicates (seen in 4D images)

        if origin is not None:
            diff = file_origin - origin
            origin_diff = origin_diff + diff
            n_diffs += 1
        origin = file_origin
        origin_seen.append(file_origin)

    if n_diffs == 0:
        # One slice or volume only, read spacing from header or default to 1 mm
        z_i = float(getattr(ref, "SpacingBetweenSlices", 1.0))
        z_order = 0
    else:
        # Multiple slices, average spacing between slices
        avg_origin_diff = origin_diff / n_diffs
        z_i = np.linalg.norm(avg_origin_diff)

        # Use orientation of the coordinate system to determine in which
        # direction the origins of the individual slices should move.
        # Use the dot product to find the angle between that direction
        # and the spacing vector - this tells us whether the order of
        # the slices is correct or should be reversed
        z_direction = direction @ np.ones(dimensions)
        if dimensions > 3:
            avg_origin_diff = np.pad(
                avg_origin_diff,
                pad_width=(0, dimensions - avg_origin_diff.size),
                mode="constant",
            )
        z_order = np.sign(np.dot(avg_origin_diff, z_direction))

    # Create ITK image from DICOM, collect additional metadata
    samples_per_pixel = int(getattr(ref, "SamplesPerPixel", 1))
    img = _create_itk_from_dcm(
        dicom_ds=dicom_ds,
        dimensions=dimensions,
        pixel_dims=pixel_dims,
        z_order=z_order,
        samples_per_pixel=samples_per_pixel,
    )

    # Slices might have been reordered, so compute the actual origin and
    # set the correct world coordinate system (origin, spacing, direction)
    if origin is None:
        origin = (0.0, 0.0, 0.0)
    sitk_origin = ref_origin if z_order >= 0 else tuple(origin)

    try:
        pixel_spacing = _find_dicom_tag(ref, "PixelSpacing")
    except DicomTagNotFoundError:
        pixel_spacing = (1.0, 1.0)

    x_i, y_i = (float(s) for s in pixel_spacing)
    sitk_spacing = (x_i, y_i, z_i)
    if dimensions == 4:
        sitk_spacing += (1.0,)
        sitk_origin += (0.0,)

    sitk_direction = tuple(direction.flatten())
    img.SetDirection(sitk_direction)
    img.SetSpacing(sitk_spacing)
    img.SetOrigin(sitk_origin)

    # Add additional metadata
    for f in OPTIONAL_METADATA_FIELDS:
        if hasattr(ref, f):
            value = getattr(ref, f)
            validate_metadata_value(key=f, value=value)
            str_value = str(value)
            if str_value != "":
                img.SetMetaData(f, str_value)

    return SimpleITKImage(
        image=img,
        name=(
            f"{dicom_ds.headers[0]['data'].StudyInstanceUID}-{dicom_ds.index}"
        ),
        consumed_files={d["file"] for d in dicom_ds.headers},
        spacing_valid=True,
    )


def _create_itk_from_dcm(
    *,
    dicom_ds,
    dimensions,
    pixel_dims,
    z_order,
    samples_per_pixel,
):
    apply_slope = any(
        not isclose(float(getattr(h["data"], "RescaleSlope", 1.0)), 1.0)
        for h in dicom_ds.headers
    )
    apply_intercept = any(
        not isclose(float(getattr(h["data"], "RescaleIntercept", 0.0)), 0.0)
        for h in dicom_ds.headers
    )
    apply_scaling = apply_slope or apply_intercept
    is_rgb = samples_per_pixel > 1
    if apply_scaling:
        np_dtype = np.float32
    else:
        np_dtype = np.short
    if samples_per_pixel > 1:
        pixel_dims += (samples_per_pixel,)

    dcm_array = None
    content_times = []
    exposures = []

    for index, partial in enumerate(dicom_ds.headers):
        ds = pydicom.dcmread(str(partial["file"]))

        if apply_scaling:
            slope = float(getattr(ds, "RescaleSlope", 1))
            intercept = float(getattr(ds, "RescaleIntercept", 0))
            pixel_array = slope * ds.pixel_array + intercept
        else:
            pixel_array = ds.pixel_array

        if (
            len(pixel_array.shape) == dimensions
            or pixel_array.shape == pixel_dims
        ):
            dcm_array = pixel_array.astype(np_dtype)
            del ds

            slicing = [slice(None)] * dimensions
            slicing[-3] = slice(None, None, 1 if z_order >= 0 else -1)
            dcm_array = dcm_array[tuple(slicing)]
            break

        if dcm_array is None:
            dcm_array = np.zeros(pixel_dims, dtype=np_dtype)

        z_index = index if z_order >= 0 else len(dicom_ds.headers) - index - 1

        if dimensions == 4:
            z = (
                z_index % dicom_ds.n_slices
                if dicom_ds.n_slices_per_file == 1
                else slice(None)
            )
            dcm_array[index // dicom_ds.n_slices, z, :, :] = pixel_array
            if index % dicom_ds.n_slices == 0:
                content_times.append(str(ds.ContentTime))
                exposures.append(str(ds.Exposure))
        else:
            dcm_array[z_index % dicom_ds.n_slices, :, :] = pixel_array

        del ds

    img = SimpleITK.GetImageFromArray(dcm_array, isVector=is_rgb)
    if dimensions == 4:
        img.SetMetaData("ContentTimes", " ".join(content_times))
        img.SetMetaData("Exposures", " ".join(exposures))

    return img


def image_builder_dicom(*, files: Set[Path]) -> Iterator[SimpleITKImage]:
    """
    Constructs image objects by inspecting files in a directory.

    Parameters
    ----------
    files
        Paths to images that were uploaded during an upload session.

    Returns
    -------
    An `ImageBuilder` object consisting of:
     - a list of filenames for all files consumed by the image builder
     - a list of detected images
     - a list files associated with the detected images
     - path->error message map describing what is wrong with a given file
    """
    file_errors: DefaultDict[Path, List[str]] = defaultdict(list)

    studies = _validate_dicom_files(files=files, file_errors=file_errors)

    for dicom_ds in studies:
        try:
            yield _process_dicom_file(dicom_ds=dicom_ds)
        except Exception as e:
            for d in dicom_ds.headers:
                file_errors[d["file"]].append(format_error(str(e)))

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
