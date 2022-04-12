import logging
from collections import defaultdict
from math import isclose
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterator, List, Set, Tuple

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


class PixelValueInverter:
    """Inverts pixel values to generate MONOCHROME2 images from MONOCHROME1 images"""

    def __init__(self, image: np.ndarray):
        self.offset = np.add(np.min(image), np.max(image))
        self.dtype = image.dtype

    def invert(self, pixel_array: np.ndarray) -> np.ndarray:
        a = np.asarray(pixel_array, dtype=self.dtype)
        return np.add(-a, self.offset)  # use np.add to avoid overflow warnings


class DicomDataset:
    def __init__(self, *, name, headers, n_time, n_slices, n_slices_per_file):
        self.name = name
        self.headers = headers
        self.n_time = n_time
        self.n_slices = n_slices
        self.n_slices_per_file = n_slices_per_file

        self._direction = None
        self._pixel_value_dtype = None
        self._pixel_value_inverter = None

    @property
    def ref_header(self) -> pydicom.Dataset:
        return self.headers[0]["data"]

    @property
    def dimensions(self) -> int:
        # Images are either 4D or 3D (2D images get an additional axis of size 1)
        return 4 if self.n_time and self.n_time > 1 else 3

    @property
    def direction(self) -> np.ndarray:
        if self._direction is None:
            # Compute rotation matrix (orientation of the image)
            try:
                orientation = _find_dicom_tag(
                    self.ref_header, "ImageOrientationPatient"
                )
                row_cos = orientation[:3]
                col_cos = orientation[3:]
            except DicomTagNotFoundError:
                # Tag can be missing in X-ray images for example
                row_cos = (1, 0, 0)
                col_cos = (0, 1, 0)

            direction = np.eye(self.dimensions, dtype=float)
            direction[:3, :3] = np.stack(
                [row_cos, col_cos, np.cross(row_cos, col_cos)], axis=1
            )
            self._direction = direction

        return self._direction

    def _iter_origins(self):
        has_frame_details = (
            "PerFrameFunctionalGroupsSequence" in self.ref_header
        )
        if self.n_slices_per_file == 1 or not has_frame_details:
            # One or multiple regular DICOM files
            for partial in self.headers:
                if "ImagePositionPatient" in partial["data"]:
                    yield np.array(
                        partial["data"].ImagePositionPatient, dtype=float
                    )
        else:
            # An enhanced DICOM file with the entire volume stored in one file
            for frame in self.ref_header.PerFrameFunctionalGroupsSequence:
                try:
                    file_origin = _find_dicom_tag(
                        frame, "ImagePositionPatient"
                    )
                except DicomTagNotFoundError:
                    pass
                else:
                    yield np.array(file_origin, dtype=float)

    def _determine_slice_order(self):
        # Compute coordinate differences between successive slices
        origin = None
        origin_diff = np.array((0, 0, 0), dtype=float)
        origin_seen = []
        n_diffs = 0
        for file_origin in self._iter_origins():
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
            z_i = float(getattr(self.ref_header, "SpacingBetweenSlices", 1.0))
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
            z_direction = self.direction @ np.ones(self.dimensions)
            if self.dimensions > 3:
                avg_origin_diff = np.pad(
                    avg_origin_diff,
                    pad_width=(0, self.dimensions - avg_origin_diff.size),
                    mode="constant",
                )
            z_order = np.sign(np.dot(avg_origin_diff, z_direction))

        try:
            pixel_spacing = _find_dicom_tag(self.ref_header, "PixelSpacing")
        except DicomTagNotFoundError:
            pixel_spacing = (1.0, 1.0)

        x_i, y_i = (float(s) for s in pixel_spacing)
        spacing = (x_i, y_i, z_i)

        # Slices might require reordering, so compute the actual origin
        if origin is None:
            origin = (0.0, 0.0, 0.0)
        else:
            origin = tuple(origin_seen[0] if z_order >= 0 else origin)

        # Add dummy values for 4D images
        if self.dimensions == 4:
            spacing += (1.0,)
            origin += (0.0,)

        return origin, spacing, z_order

    def _pixel_values_need_scaling(self) -> bool:
        apply_slope = any(
            not isclose(float(getattr(h["data"], "RescaleSlope", 1.0)), 1.0)
            for h in self.headers
        )
        apply_intercept = any(
            not isclose(
                float(getattr(h["data"], "RescaleIntercept", 0.0)), 0.0
            )
            for h in self.headers
        )
        return apply_slope or apply_intercept

    def _read_pixel_values(self, filename: Path, rescale: bool) -> np.ndarray:
        ds = pydicom.dcmread(str(filename))

        # Read rescaling parameters already now so that we can delete
        # the DICOM dataset instance as soon as possible
        slope = float(getattr(ds, "RescaleSlope", 1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))

        # If the data type is still unknown, use data type of this slice
        if self._pixel_value_dtype is None:
            if rescale:
                self._pixel_value_dtype = np.float32
            else:
                self._pixel_value_dtype = ds.pixel_array.dtype

        # Get pixel array and cast to desired data type if needed
        pixel_array = ds.pixel_array.astype(
            dtype=self._pixel_value_dtype, copy=False
        )
        del ds

        if rescale:
            return slope * pixel_array + intercept
        else:
            return pixel_array

    def _shape(self, samples_per_pixel: int) -> Tuple[int, ...]:
        pixel_dims = [
            self.n_slices,
            self.ref_header.Rows,
            self.ref_header.Columns,
        ]
        if self.dimensions == 4:
            pixel_dims.insert(0, self.n_time)
        if samples_per_pixel > 1:
            pixel_dims.append(samples_per_pixel)

        return tuple(int(s) for s in pixel_dims)

    def _create_itk_from_dcm(self, z_order: int) -> SimpleITK.Image:
        samples_per_pixel = int(getattr(self.ref_header, "SamplesPerPixel", 1))
        pixel_dims = self._shape(samples_per_pixel)
        is_rgb = samples_per_pixel > 1
        apply_scaling = self._pixel_values_need_scaling()
        dcm_array: np.ndarray = None

        for index, partial in enumerate(self.headers):
            pixel_array = self._read_pixel_values(
                filename=partial["file"], rescale=apply_scaling
            )

            if (
                len(pixel_array.shape) == self.dimensions
                or pixel_array.shape == pixel_dims
            ):
                slicing = [slice(None)] * self.dimensions
                slicing[-3] = slice(None, None, 1 if z_order >= 0 else -1)
                dcm_array = pixel_array[tuple(slicing)]
                break

            if dcm_array is None:
                dcm_array = np.zeros(pixel_dims, dtype=pixel_array.dtype)

            # Determine slice position in array based on slice order
            z_index = index if z_order >= 0 else len(self.headers) - index - 1

            # Add slice to volume
            if self.dimensions == 4:
                z = (
                    z_index % self.n_slices
                    if self.n_slices_per_file == 1
                    else slice(None)
                )
                dcm_array[index // self.n_slices, z, :, :] = pixel_array
            else:
                dcm_array[z_index % self.n_slices, :, :] = pixel_array

        # When images have a photometric interpretation that requires low
        # values to be displayed in white, we invert the image values
        photometric_interpretation = getattr(
            self.ref_header, "PhotometricInterpretation", None
        )
        if not is_rgb and photometric_interpretation == "MONOCHROME1":
            self._pixel_value_inverter = PixelValueInverter(dcm_array)
            dcm_array = self._pixel_value_inverter.invert(dcm_array)

        return SimpleITK.GetImageFromArray(dcm_array, isVector=is_rgb)

    def _add_optional_metadata(self, img: SimpleITK.Image):
        for f in OPTIONAL_METADATA_FIELDS:
            value = getattr(self.ref_header, f, "")
            str_value = str(value)

            # Skip empty entries, ITK will not write them anyway
            if str_value == "":
                continue

            validate_metadata_value(key=f, value=value)

            # Invert value of window level
            if f == "WindowCenter" and self._pixel_value_inverter is not None:
                centers = self._pixel_value_inverter.invert(value)
                str_value = str(
                    list(centers) if centers.size > 1 else centers.item()
                )

            img.SetMetaData(f, str_value)

    def _add_temporal_metadata(self, img: SimpleITK.Image, z_order: int):
        content_times = []
        exposures = []

        for index, partial in enumerate(self.headers):
            if self.n_slices_per_file > 1 or index % self.n_slices == 0:
                content_times.append(str(partial["data"].ContentTime))
                exposures.append(str(partial["data"].Exposure))

        if z_order < 0:
            content_times = content_times[::-1]
            exposures = exposures[::-1]

        img.SetMetaData("ContentTimes", " ".join(content_times))
        img.SetMetaData("Exposures", " ".join(exposures))

    def read(self) -> SimpleITKImage:
        origin, spacing, z_order = self._determine_slice_order()

        # Create ITK image from DICOM
        img = self._create_itk_from_dcm(z_order=z_order)
        img.SetDirection(tuple(self.direction.flatten()))
        img.SetSpacing(spacing)
        img.SetOrigin(origin)

        # Add additional metadata
        self._add_optional_metadata(img)
        if self.dimensions == 4:
            self._add_temporal_metadata(img, z_order)

        return SimpleITKImage(
            image=img,
            name=self.name,
            consumed_files={d["file"] for d in self.headers},
            spacing_valid=True,
        )


def _get_headers_by_study(
    files: Set[Path], file_errors: DefaultDict[Path, List[str]]
):
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
    study_key_type = Tuple[str, ...]
    studies: Dict[study_key_type, Dict[str, Any]] = {}
    indices: Dict[str, Dict[study_key_type, int]] = {}

    for file in files:
        if not file.is_file():
            continue
        with file.open("rb") as f:
            try:
                # Read header only, skip reading the pixel data for now
                ds = pydicom.dcmread(f, stop_before_pixels=True)

                # Group by series instance uid or by stack ID (for 4D images)
                # Additionally also group by SOP class UID to skip over extra
                # raw data (dose reports for example) that are sometimes stored
                # under the same series instance UID.
                key: study_key_type = (
                    ds.StudyInstanceUID,
                    getattr(ds, "StackID", ds.SeriesInstanceUID),
                    ds.SOPClassUID,
                )

                studies[key] = studies.get(key, {})
                indices[ds.StudyInstanceUID] = indices.get(
                    ds.StudyInstanceUID, {}
                )

                try:
                    index = indices[ds.StudyInstanceUID][key]
                except KeyError:
                    index = len(indices[ds.StudyInstanceUID])
                    indices[ds.StudyInstanceUID][key] = index

                headers = studies[key].get("headers", [])
                headers.append({"file": file, "data": ds})
                studies[key]["headers"] = headers

                # Since we might need to combine multiple images with different
                # series instance UID (in 4D images), we cannot use the series
                # as the unique file name - instead, we use the study instance
                # uid and a counter (index) per study
                studies[key]["name"] = f"{ds.StudyInstanceUID}-{index}"

            except Exception as e:
                file_errors[file].append(format_error(str(e)))

    for key in studies:
        studies[key]["headers"].sort(
            key=lambda x: int(x["data"].InstanceNumber)
        )
    return studies


def _find_valid_dicom_files(
    files: Set[Path], file_errors: DefaultDict[Path, List[str]]
) -> List[DicomDataset]:
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
    A list of `DicomDataset` instances

    Any study with an inconsistent amount of slices per time point is discarded.
    """
    studies = _get_headers_by_study(files=files, file_errors=file_errors)
    result = []
    for key in studies:
        headers = studies[key]["headers"]
        set_name = studies[key]["name"]
        if not headers:
            continue

        data = headers[-1]["data"]
        n_files = len(headers)
        n_time = int(getattr(data, "TemporalPositionIndex", 0))
        try:
            n_slices_per_file = len(data.PerFrameFunctionalGroupsSequence)
        except AttributeError:
            n_slices_per_file = int(getattr(data, "NumberOfFrames", 1))
        n_slices = n_files * n_slices_per_file

        if n_time < 1:
            # Not a 4d dicom file (DICOM standard says TPI is >=1 )
            result.append(
                DicomDataset(
                    name=set_name,
                    headers=headers,
                    n_time=None,
                    n_slices=n_slices,
                    n_slices_per_file=n_slices_per_file,
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
                DicomDataset(
                    name=set_name,
                    headers=headers,
                    n_time=n_time,
                    n_slices=n_slices // n_time,
                    n_slices_per_file=n_slices_per_file,
                )
            )

    del studies
    return result


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

    studies = _find_valid_dicom_files(files=files, file_errors=file_errors)
    for dicom_ds in studies:
        try:
            yield dicom_ds.read()
        except Exception as e:
            for d in dicom_ds.headers:
                file_errors[d["file"]].append(format_error(str(e)))

    if file_errors:
        raise UnconsumedFilesException(file_errors=file_errors)
