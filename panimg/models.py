import logging
import shutil
from enum import Enum
from functools import cached_property
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import SimpleITK
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.dataclasses import dataclass
from SimpleITK import GetArrayViewFromImage, Image, WriteImage

logger = logging.getLogger(__name__)

MASK_TYPE_PIXEL_IDS = [
    SimpleITK.sitkInt8,
    SimpleITK.sitkUInt8,
]


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


# NOTE: Only int8 or uint8 data types are checked for segments
# so the true maximum is 256
MAXIMUM_SEGMENTS_LENGTH = 64


@dataclass(frozen=True)
class PanImg:
    pk: UUID
    name: str
    width: int
    height: int
    depth: int | None
    voxel_width_mm: float | None
    voxel_height_mm: float | None
    voxel_depth_mm: float | None
    timepoints: int | None
    resolution_levels: int | None
    window_center: float | None
    window_width: float | None
    color_space: ColorSpace
    eye_choice: EyeChoice
    segments: frozenset[int] | None = None


@dataclass(frozen=True)
class PanImgFile:
    image_id: UUID
    image_type: ImageType
    file: Path
    directory: Path | None = None


@dataclass
class PanImgResult:
    new_images: set[PanImg]
    new_image_files: set[PanImgFile]
    consumed_files: set[Path]
    file_errors: dict[Path, list[str]]


@dataclass
class PostProcessorResult:
    new_image_files: set[PanImgFile]


class SimpleITKImage(BaseModel):
    image: Image

    name: str
    consumed_files: set[Path]

    spacing_valid: bool
    eye_choice: EyeChoice = EyeChoice.NOT_APPLICABLE

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    @property
    def width(self) -> int:
        return int(self.image.GetWidth())

    @property
    def height(self) -> int:
        return int(self.image.GetHeight())

    @property
    def depth(self) -> int | None:
        try:
            depth = int(self.image.GetDepth())
        except (RuntimeError, ValueError):
            return None

        return depth or None

    @staticmethod
    def _extract_first_float(value: str) -> float:
        if value.startswith("["):
            return float(value[1:-1].split(",")[0])
        else:
            return float(value)

    @property
    def window_center(self) -> float | None:
        try:
            return self._extract_first_float(
                self.image.GetMetaData("WindowCenter")
            )
        except (RuntimeError, ValueError):
            return None

    @property
    def window_width(self) -> float | None:
        try:
            return self._extract_first_float(
                self.image.GetMetaData("WindowWidth")
            )
        except (RuntimeError, ValueError):
            return None

    @property
    def timepoints(self) -> int | None:
        if self.image.GetDimension() == 4 and self.segments is None:
            # Only 4D files that are non-segmentations have timepoints
            return int(self.image.GetSize()[3])
        else:
            return None

    @field_validator("image")
    @classmethod
    def check_color_space(cls, image: Image):  # noqa: B902, N805
        cs = image.GetNumberOfComponentsPerPixel()
        if cs not in ITK_COLOR_SPACE_MAP:
            raise ValueError(f"Unknown color space for MetaIO image: {cs}")
        return image

    @field_validator("image")
    @classmethod
    def add_value_range_meta_data(cls, image: Image):  # noqa: B902, N805
        smallest_tag = "SmallestImagePixelValue"
        largest_tag = "LargestImagePixelValue"

        if image.HasMetaDataKey(smallest_tag) and image.HasMetaDataKey(
            largest_tag
        ):
            return image

        # Use the numpy-array route to support a larger range of data-types
        # than ITK' MinimumMaximumImageFilter (e.g. 2D uint8)
        array = GetArrayViewFromImage(image)
        image.SetMetaData(smallest_tag, str(array.min()))
        image.SetMetaData(largest_tag, str(array.max()))

        return image

    @cached_property
    def segments(self) -> frozenset[int] | None:
        if (
            self.image.GetNumberOfComponentsPerPixel() != 1
            or self.image.GetPixelIDValue() not in MASK_TYPE_PIXEL_IDS
        ):
            # Only single channel, 8 bit images should be checked.
            # Everything else is not a segmentation
            return None

        im_arr = GetArrayViewFromImage(self.image)

        if self.image.GetDimension() == 4:
            segments = set()
            n_volumes = self.image.GetSize()[3]

            for volume in range(n_volumes):
                # Calculate the segments for each volume for memory efficiency
                volume_segments = np.unique(im_arr[volume, :, :, :])
                segments.update({*volume_segments})

                if not segments.issubset({0, 1}):
                    # 4D Segmentations must only have values 0 and 1
                    # as the 4th dimension encodes the overlay type
                    return None

            # Use 1-indexing for each segmentation
            segments = {idx + 1 for idx in range(n_volumes)}
        else:
            segments = np.unique(im_arr)

        if len(segments) <= MAXIMUM_SEGMENTS_LENGTH:
            return frozenset(segments)
        else:
            return None

    @property
    def color_space(self) -> ColorSpace:
        return ITK_COLOR_SPACE_MAP[self.image.GetNumberOfComponentsPerPixel()]

    @property
    def voxel_width_mm(self) -> float | None:
        if self.spacing_valid:
            return float(self.image.GetSpacing()[0])
        else:
            return None

    @property
    def voxel_height_mm(self) -> float | None:
        if self.spacing_valid:
            return float(self.image.GetSpacing()[1])
        else:
            return None

    @property
    def voxel_depth_mm(self) -> float | None:
        if self.spacing_valid:
            try:
                return float(self.image.GetSpacing()[2])
            except IndexError:
                return None
        else:
            return None

    def save(self, output_directory: Path) -> tuple[PanImg, set[PanImgFile]]:
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
            segments=self.segments,
        )

        WriteImage(
            image=self.image,
            fileName=str(work_dir.absolute() / f"{pk}.mha"),
            useCompression=True,
        )

        new_files = set()
        for file in work_dir.iterdir():
            new_file = PanImgFile(
                image_id=pk, image_type=ImageType.MHD, file=file
            )
            new_files.add(new_file)

        return new_image, new_files


class TIFFImage(BaseModel):
    file: Path

    name: str
    consumed_files: set[Path]

    width: int
    height: int
    voxel_width_mm: float
    voxel_height_mm: float
    resolution_levels: int
    color_space: ColorSpace
    eye_choice: EyeChoice = EyeChoice.NOT_APPLICABLE
    segments: frozenset[int] | None = None

    model_config = ConfigDict(frozen=True)

    def save(self, output_directory: Path) -> tuple[PanImg, set[PanImgFile]]:
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
            segments=self.segments,
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
