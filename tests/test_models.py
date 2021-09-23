import re

import pytest

from panimg.models import DICOM_VR_TO_VALIDATION_REGEXP, DICOM_VR_TO_VALUE_CAST


@pytest.mark.parametrize(
    "vr,valid,invalid",
    (
        (
            "AS",
            ("000D", "123W", "456M", "789Y"),
            ("1Y", "12D", "1234D", "123", ""),
        ),
        ("CS(PatientSex)", ("M", "F", "O"), ("X", "MF", "")),
        (
            "DA",
            ("12345678", "20210923"),
            ("1", "1234567", "2021923", "a", "123456789", ""),
        ),
        (
            "LO",
            ("", "a" * 64, "😄", "😄" * 64),
            ("a" * 65, "\\", "😄" * 65, r"a\a"),
        ),
        (
            "PN",
            ("", "a" * 324, "😄", "😄" * 324),
            ("a" * 325, "\\", "😄" * 325, r"a\a"),
        ),
        (
            "UI",
            ("", "1.0", "0.0.0.0", "1." * 32),
            ("1." * 33, "a", "😄.😄", "1.2.+.a"),
        ),
    ),
)
def test_dicom_vr_validation(vr, valid, invalid):
    pattern = DICOM_VR_TO_VALIDATION_REGEXP[vr]
    for t in valid:
        assert re.match(pattern, t)

    for t in invalid:
        assert not re.match(pattern, t)


def test_date_casting():
    cast_func = DICOM_VR_TO_VALUE_CAST["DA"]
    for t in ("20210923", "12341231", "12341231123456"):
        cast_func(t)

    for t in (
        "",
        "12345678",
        "1",
        "1234567",
        "2021923",
        "2021010a",
        "123456789",
        "20210229",
        "20210931",
    ):
        with pytest.raises(ValueError):
            cast_func(t)
