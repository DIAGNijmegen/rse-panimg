import re
from pathlib import Path
from typing import Any, Dict, List

import SimpleITK

from panimg.exceptions import ValidationError
from panimg.models import EXTRA_METADATA, validate_metadata_value

METAIO_IMAGE_TYPES = {
    "MET_NONE": None,
    "MET_ASCII_CHAR": None,
    "MET_CHAR": SimpleITK.sitkInt8,
    "MET_UCHAR": SimpleITK.sitkUInt8,
    "MET_SHORT": SimpleITK.sitkInt16,
    "MET_USHORT": SimpleITK.sitkUInt16,
    "MET_INT": SimpleITK.sitkInt32,
    "MET_UINT": SimpleITK.sitkUInt32,
    "MET_LONG": SimpleITK.sitkInt64,
    "MET_ULONG": SimpleITK.sitkUInt64,
    "MET_LONG_LONG": None,
    "MET_ULONG_LONG": None,
    "MET_FLOAT": SimpleITK.sitkFloat32,
    "MET_DOUBLE": SimpleITK.sitkFloat64,
    "MET_STRING": None,
    "MET_CHAR_ARRAY": SimpleITK.sitkVectorInt8,
    "MET_UCHAR_ARRAY": SimpleITK.sitkVectorUInt8,
    "MET_SHORT_ARRAY": SimpleITK.sitkVectorInt16,
    "MET_USHORT_ARRAY": SimpleITK.sitkVectorUInt16,
    "MET_INT_ARRAY": SimpleITK.sitkVectorInt32,
    "MET_UINT_ARRAY": SimpleITK.sitkVectorUInt32,
    "MET_LONG_ARRAY": SimpleITK.sitkVectorInt64,
    "MET_ULONG_ARRAY": SimpleITK.sitkVectorUInt64,
    "MET_LONG_LONG_ARRAY": None,
    "MET_ULONG_LONG_ARRAY": None,
    "MET_FLOAT_ARRAY": SimpleITK.sitkVectorFloat32,
    "MET_DOUBLE_ARRAY": SimpleITK.sitkVectorFloat64,
    "MET_FLOAT_MATRIX": None,
    "MET_OTHER": None,
}


FLOAT_REGEX = r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?"
FLOAT_MATCH_REGEXP = re.compile(fr"^{FLOAT_REGEX}$")
FLOAT_LIST_MATCH_REGEXP = re.compile(fr"^({FLOAT_REGEX})(\s{FLOAT_REGEX})*$")
FLOAT_ARRAY_MATCH_REGEXP = re.compile(
    fr"^\[({FLOAT_REGEX},\s?)*{FLOAT_REGEX}]$"
)
FLOAT_OR_FLOAT_ARRAY_MATCH_REGEX = re.compile(
    fr"({FLOAT_MATCH_REGEXP.pattern})|({FLOAT_ARRAY_MATCH_REGEXP.pattern})"
)
CONTENT_TIMES_LIST_MATCH_REGEXP = re.compile(
    r"^((2[0-3]|[0-1]\d)[0-5]\d[0-5]\d(\.\d\d\d)?)"
    r"(\s(2[0-3]|[0-1]\d)[0-5]\d[0-5]\d(\.\d\d\d)?)*$"
)

LENGTH_LIMIT_MATCH_REGEXP = re.compile(r"^.{0,128}$")

ADDITIONAL_HEADERS = {
    "Laterality": LENGTH_LIMIT_MATCH_REGEXP,
    "SliceThickness": FLOAT_MATCH_REGEXP,
    "Exposures": FLOAT_LIST_MATCH_REGEXP,
    "ContentTimes": CONTENT_TIMES_LIST_MATCH_REGEXP,
    "WindowCenter": FLOAT_OR_FLOAT_ARRAY_MATCH_REGEX,
    "WindowWidth": FLOAT_OR_FLOAT_ARRAY_MATCH_REGEX,
    "t0": FLOAT_MATCH_REGEXP,
    "t1": FLOAT_MATCH_REGEXP,
    **{md.keyword: md.match_pattern for md in EXTRA_METADATA},
}

HEADERS_MATCHING_NUM_TIMEPOINTS: List[str] = ["Exposures", "ContentTimes"]

HEADERS_MATCHING_WINDOW_SETTINGS: List[str] = ["WindowCenter", "WindowWidth"]

HEADERS_WITH_LISTING: List[str] = [
    "TransformMatrix",
    "Offset",
    "CenterOfRotation",
    "ElementSpacing",
]

EXPECTED_HEADERS: List[str] = [
    "ObjectType",
    "NDims",
    "BinaryData",
    "BinaryDataByteOrderMSB",
    "CompressedData",
    "CompressedDataSize",
    "TransformMatrix",
    "Offset",
    "CenterOfRotation",
    "AnatomicalOrientation",
    "ElementSpacing",
    "ElementNumberOfChannels",
    "DimSize",
    "ElementType",
    "ElementDataFile",
]


def parse_mh_header(file: Path) -> Dict[str, str]:
    """
    Attempts to parse the headers of an mhd file.

    This function must be secure to safeguard against any untrusted uploaded
    file.

    Parameters
    ----------
    filename

    Returns
    -------
        The extracted header from the mhd file as key value pairs.

    Raises
    ------
    ValidationError
        Raised when the file contains problems making it impossible to
        read.
    """

    # attempt to limit number of read headers to prevent overflow attacks
    read_line_limit = 10000

    result: Dict[str, str] = {}
    with file.open("rb") as f:
        lines = True
        while lines:
            read_line_limit -= 1
            if read_line_limit < 0:
                raise ValidationError("Files contains too many header lines")

            bin_line = f.readline(10000)

            if not bin_line:
                lines = False
                continue

            if len(bin_line) >= 10000:
                raise ValidationError("Line length is too long")

            try:
                line = bin_line.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ValidationError("Header contains invalid UTF-8") from e
            else:
                result.update(extract_key_value_pairs(line))

            if "ElementDataFile" in result:
                break  # last parsed header...

    return result


def extract_key_value_pairs(line: str) -> Dict[str, str]:
    line = line.rstrip("\n\r")
    if line.strip() and "=" in line:
        key, value = line.split("=", 1)
        return {key.strip(): value.strip()}
    else:
        return {}


def extract_header_listing(
    property: str, headers: Dict[str, str], dtype: type = float
) -> List[Any]:
    return [dtype(e) for e in headers[property].strip().split(" ")]


def resolve_mh_data_file_path(
    headers: Dict[str, str], is_mha: bool, mhd_file: Path
) -> Path:
    if is_mha:
        data_file_path = mhd_file
    else:
        data_file_path = (
            mhd_file.resolve().parent / Path(headers["ElementDataFile"]).name
        )
    if not data_file_path.exists():
        raise OSError("cannot find data file")
    return data_file_path


def validate_and_clean_additional_mh_headers(
    headers: Dict[str, str]
) -> Dict[str, str]:
    cleaned_headers = {}
    for key, value in headers.items():
        if key in EXPECTED_HEADERS:
            cleaned_headers[key] = value
        elif key in ADDITIONAL_HEADERS:
            validate_metadata_value(key=key, value=value)
            match_pattern = ADDITIONAL_HEADERS[key]
            if not re.match(match_pattern, value):
                raise ValidationError(
                    f"Value '{value}' for field {key} does not match "
                    f"pattern {match_pattern.pattern}"
                )
            if key in HEADERS_MATCHING_NUM_TIMEPOINTS:
                validate_list_data_matches_num_timepoints(
                    headers=headers, key=key, value=value
                )
            if key in HEADERS_MATCHING_WINDOW_SETTINGS:
                validate_center_matches_width_setting(
                    headers=headers, key=key, value=value
                )
            cleaned_headers[key] = value
    return cleaned_headers


def validate_center_matches_width_setting(
    headers: Dict[str, str], key: str, value: str
):
    window_keys = ("WindowWidth", "WindowCenter")
    if key not in window_keys:
        return
    if not re.match(FLOAT_ARRAY_MATCH_REGEXP, value):
        return

    counter_key = window_keys[0] if key == window_keys[1] else window_keys[1]
    if not re.match(FLOAT_ARRAY_MATCH_REGEXP, headers[counter_key]):
        raise ValidationError(
            f"Header '{key}' is of a different format than '{counter_key}'"
        )
    if len(value.split(",")) != len(headers[counter_key].split(",")):
        raise ValidationError(
            f"Headers '{key}' and '{counter_key}' should "
            f"contain an equal number of values"
        )


def validate_list_data_matches_num_timepoints(
    headers: Dict[str, str], key: str, value: str
):
    num_timepoints = len(value.split(" "))
    expected_timepoints = (
        int(headers["DimSize"].split(" ")[3])
        if int(headers["NDims"]) >= 4
        else 1
    )
    if num_timepoints != expected_timepoints:
        raise ValidationError(
            f"Found {num_timepoints} values for {key}, "
            f"but expected {expected_timepoints} (1/timepoint)"
        )


def add_additional_mh_headers_to_sitk_image(
    sitk_image: SimpleITK.Image, headers: Dict[str, str]
):
    cleaned_headers = validate_and_clean_additional_mh_headers(headers)
    for header in ADDITIONAL_HEADERS:
        if header in cleaned_headers:
            value = cleaned_headers[header]
            if isinstance(value, (list, tuple)):
                value = " ".join([str(v) for v in value])
            else:
                value = str(value)
            sitk_image.SetMetaData(header, value)


def load_sitk_image(mhd_file: Path) -> SimpleITK.Image:
    headers = parse_mh_header(mhd_file)
    headers = validate_and_clean_additional_mh_headers(headers=headers)
    ndims = int(headers["NDims"])
    if ndims <= 4:
        sitk_image = SimpleITK.ReadImage(str(mhd_file))
        for key in sitk_image.GetMetaDataKeys():
            if key not in ADDITIONAL_HEADERS:
                sitk_image.EraseMetaData(key)
    else:
        error_msg = (
            "SimpleITK images with more than 4 dimensions are not supported"
        )
        raise NotImplementedError(error_msg)
    add_additional_mh_headers_to_sitk_image(
        sitk_image=sitk_image, headers=headers
    )
    return sitk_image
