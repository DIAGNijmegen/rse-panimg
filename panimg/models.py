import datetime
import logging
import re
import shutil
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple
from uuid import UUID, uuid4

from SimpleITK import Image, WriteImage
from pydantic import BaseModel, validator
from pydantic.dataclasses import dataclass

from panimg.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ColorSpace(str, Enum):
    GRAY = "GRAY"
    RGB = "RGB"
    RGBA = "RGBA"
    YCBCR = "YCBCR"


ITK_COLOR_SPACE_MAP = {
    1: ColorSpace.GRAY,
    3: ColorSpace.RGB,
    4: ColorSpace.RGBA,
}


class ImageType(str, Enum):
    MHD = "MHD"
    TIFF = "TIFF"
    DZI = "DZI"


class EyeChoice(str, Enum):
    OCULUS_DEXTER = "OD"
    OCULUS_SINISTER = "OS"
    UNKNOWN = "U"
    NOT_APPLICABLE = "NA"


class PatientSex(str, Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"


DICOM_VR_TO_VALIDATION_REGEXP = {
    "AS": re.compile(r"^\d{3}[DWMY]$"),
    "CS": re.compile(r"^[A-Z\d _]{0,16}$"),
    "DA": re.compile(r"^\d{8}$"),
    "LO": re.compile(r"^[^\\]{0,64}$"),
    "PN": re.compile(r"^[^\\]{0,324}$"),
    "UI": re.compile(r"^[\d.]{0,64}$"),
}
DICOM_VR_TO_VALUE_CAST = {
    "DA": lambda v: datetime.date(int(v[:4]), int(v[4:6]), int(v[6:8]))
}


class ExtraMetaData(NamedTuple):
    keyword: str  # DICOM tag keyword (eg. 'PatientID')
    vr: str  # DICOM Value Representation (eg. 'LO')
    field_name: str  # Name of field on PanImg model (eg. 'patient_id')

    @property
    def match_pattern(self):
        return DICOM_VR_TO_VALIDATION_REGEXP[self.vr]

    @property
    def cast_func(self):
        def default_func(v):
            return None if v == "" else v

        return DICOM_VR_TO_VALUE_CAST.get(self.vr, default_func)

    def validate_value(self, value):
        if value is None or str(value) == "":
            return
        if not re.match(self.match_pattern, str(value)):
            raise ValidationError(
                f"Value '{value}' for field {self.keyword} does not match "
                f"pattern {self.match_pattern.pattern}"
            )
        try:
            self.cast_func(value)
        except ValueError as e:
            raise ValidationError from e


def validate_metadata_value(*, key, value):
    key_to_md = {md.keyword: md for md in EXTRA_METADATA}
    if key in key_to_md:
        key_to_md[key].validate_value(value)


EXTRA_METADATA = (
    ExtraMetaData("PatientID", "LO", "patient_id"),
    ExtraMetaData("PatientName", "PN", "patient_name"),
    ExtraMetaData("PatientBirthDate", "DA", "patient_birth_date"),
    ExtraMetaData("PatientAge", "AS", "patient_age"),
    ExtraMetaData("PatientSex", "CS", "patient_sex"),
    ExtraMetaData("StudyDate", "DA", "study_date"),
    ExtraMetaData("StudyInstanceUID", "UI", "study_instance_uid"),
    ExtraMetaData("SeriesInstanceUID", "UI", "series_instance_uid"),
    ExtraMetaData("StudyDescription", "LO", "study_description"),
    ExtraMetaData("SeriesDescription", "LO", "series_description"),
)


@dataclass(frozen=True)
class PanImg:
    pk: UUID
    name: str
    width: int
    height: int
    depth: Optional[int]
    voxel_width_mm: Optional[float]
    voxel_height_mm: Optional[float]
    voxel_depth_mm: Optional[float]
    timepoints: Optional[int]
    resolution_levels: Optional[int]
    window_center: Optional[float]
    window_width: Optional[float]
    color_space: ColorSpace
    eye_choice: EyeChoice
    patient_id: Optional[str]
    patient_name: Optional[str]
    patient_birth_date: Optional[datetime.date]
    patient_age: Optional[str]
    patient_sex: Optional[PatientSex]
    study_date: Optional[datetime.date]
    study_instance_uid: Optional[str]
    series_instance_uid: Optional[str]
    study_description: Optional[str]
    series_description: Optional[str]


@dataclass(frozen=True)
class PanImgFile:
    image_id: UUID
    image_type: ImageType
    file: Path


@dataclass(frozen=True)
class PanImgFolder:
    image_id: UUID
    folder: Path


@dataclass
class PanImgResult:
    new_images: Set[PanImg]
    new_image_files: Set[PanImgFile]
    new_folders: Set[PanImgFolder]
    consumed_files: Set[Path]
    file_errors: Dict[Path, List[str]]


@dataclass
class PostProcessorResult:
    new_image_files: Set[PanImgFile]
    new_folders: Set[PanImgFolder]


class SimpleITKImage(BaseModel):
    image: Image

    name: str
    consumed_files: Set[Path]

    spacing_valid: bool
    eye_choice: EyeChoice = EyeChoice.NOT_APPLICABLE

    class Config:
        arbitrary_types_allowed = True
        allow_mutation = False

    @property
    def width(self) -> int:
        return int(self.image.GetWidth())

    @property
    def height(self) -> int:
        return int(self.image.GetHeight())

    @property
    def depth(self) -> Optional[int]:
        try:
            depth = int(self.image.GetDepth())
        except (RuntimeError, ValueError):
            return None

        return depth or None

    @staticmethod
    def _extract_first_float(value: str,) -> float:
        if value.startswith("["):
            return float(value[1:-1].split(",")[0])
        else:
            return float(value)

    @property
    def window_center(self) -> Optional[float]:
        try:
            return self._extract_first_float(
                self.image.GetMetaData("WindowCenter")
            )
        except (RuntimeError, ValueError):
            return None

    @property
    def window_width(self) -> Optional[float]:
        try:
            return self._extract_first_float(
                self.image.GetMetaData("WindowWidth")
            )
        except (RuntimeError, ValueError):
            return None

    @property
    def timepoints(self) -> Optional[int]:
        if self.image.GetDimension() == 4:
            return int(self.image.GetSize()[-1])
        else:
            return None

    @validator("image")
    def check_color_space(cls, image: Image):  # noqa: B902, N805
        cs = image.GetNumberOfComponentsPerPixel()
        if cs not in ITK_COLOR_SPACE_MAP:
            raise ValueError(f"Unknown color space for MetaIO image: {cs}")
        return image

    @property
    def color_space(self) -> ColorSpace:
        return ITK_COLOR_SPACE_MAP[self.image.GetNumberOfComponentsPerPixel()]

    @property
    def voxel_width_mm(self) -> Optional[float]:
        if self.spacing_valid:
            return float(self.image.GetSpacing()[0])
        else:
            return None

    @property
    def voxel_height_mm(self) -> Optional[float]:
        if self.spacing_valid:
            return float(self.image.GetSpacing()[1])
        else:
            return None

    @property
    def voxel_depth_mm(self) -> Optional[float]:
        if self.spacing_valid:
            try:
                return float(self.image.GetSpacing()[2])
            except IndexError:
                return None
        else:
            return None

    def generate_extra_metadata(self,) -> Dict[str, Any]:
        extra_metadata = {md.field_name: None for md in EXTRA_METADATA}
        for md in EXTRA_METADATA:
            try:
                value = str(self.image.GetMetaData(md.keyword))
            except (RuntimeError, ValueError):
                pass
            else:
                try:
                    md.validate_value(value)
                    if str(value) != "":
                        extra_metadata[md.field_name] = md.cast_func(value)
                except ValidationError as e:
                    # Validation of metadata is already done in the builders so
                    # that it only fails and skips the images with corrupt
                    # metadata. This validation is done as an extra check.
                    logger.warning(
                        f"Value for metadata field {md.keyword} is stripped "
                        f"because it produced a ValidationError: '{e}'"
                    )
        return extra_metadata

    def save(self, output_directory: Path) -> Tuple[PanImg, Set[PanImgFile]]:
        pk = uuid4()

        work_dir = Path(output_directory) / self.name
        work_dir.mkdir()

        new_image = PanImg(
            pk=pk,
            name=self.name,
            width=self.width,
            height=self.height,
            depth=self.depth,
            window_center=self.window_center,
            window_width=self.window_width,
            timepoints=self.timepoints,
            resolution_levels=None,
            color_space=self.color_space,
            voxel_width_mm=self.voxel_width_mm,
            voxel_height_mm=self.voxel_height_mm,
            voxel_depth_mm=self.voxel_depth_mm,
            eye_choice=self.eye_choice,
            **self.generate_extra_metadata(),
        )

        WriteImage(
            image=self.image,
            fileName=str(work_dir.absolute() / f"{pk}.mha"),
            useCompression=True,
        )

        new_files = set()
        for file in work_dir.iterdir():
            new_file = PanImgFile(
                image_id=pk, image_type=ImageType.MHD, file=file,
            )
            new_files.add(new_file)

        return new_image, new_files


class TIFFImage(BaseModel):
    file: Path

    name: str
    consumed_files: Set[Path]

    width: int
    height: int
    voxel_width_mm: float
    voxel_height_mm: float
    resolution_levels: int
    color_space: ColorSpace
    eye_choice: EyeChoice = EyeChoice.NOT_APPLICABLE

    class Config:
        allow_mutation = False

    def save(self, output_directory: Path) -> Tuple[PanImg, Set[PanImgFile]]:
        pk = uuid4()

        output_file = output_directory / self.name / f"{pk}{self.file.suffix}"
        output_file.parent.mkdir()

        new_image = PanImg(
            pk=pk,
            name=self.name,
            width=self.width,
            height=self.height,
            depth=1,
            resolution_levels=self.resolution_levels,
            color_space=self.color_space,
            voxel_width_mm=self.voxel_width_mm,
            voxel_height_mm=self.voxel_height_mm,
            voxel_depth_mm=None,
            timepoints=None,
            window_center=None,
            window_width=None,
            eye_choice=self.eye_choice,
            **{md.field_name: None for md in EXTRA_METADATA},
        )

        shutil.copy(src=self.file, dst=output_file)

        new_files = {
            PanImgFile(
                image_id=pk,
                image_type=ImageType.TIFF,
                file=output_file.absolute(),
            )
        }

        return new_image, new_files
