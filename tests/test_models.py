import pytest

from panimg.exceptions import ValidationError
from panimg.models import ExtraMetaData


@pytest.mark.parametrize(
    "vr,valid,invalid",
    (
        (
            "AS",
            ("000D", "123W", "456M", "789Y"),
            ("1Y", "12D", "1234D", "123"),
        ),
        ("CS(PatientSex)", ("M", "F", "O"), ("X", "MF")),
        (
            "DA",
            ("20210923", "12341231", ""),
            (
                "12345678",
                "a",
                "1",
                "1234567",
                "2021923",
                "2021010a",
                "123456789",
                "20210229",
                "20210931",
                "12341231123456",
            ),
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
    md = ExtraMetaData("Test", vr, "test")
    for t in valid:
        md.validate_value(t)

    for t in invalid:
        with pytest.raises(ValidationError):
            md.validate_value(t)
