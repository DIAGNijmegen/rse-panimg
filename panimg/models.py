import logging
import shutil
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from SimpleITK import Image, WriteImage
from openslide import open_slide
from pydantic import BaseModel, validator
from pydantic.dataclasses import dataclass
from tifffile.tifffile import TiffFile

logger = logging.getLogger(__name__)


class ColorSpace(str, Enum):
    GRAY = "GRAY"
    RGB = "RGB"
    RGBA = "RGBA"
    YCBCR = "YCBCR"


class ImageType(str, Enum):
    MHD = "MHD"
    TIFF = "TIFF"
    DZI = "DZI"


ITK_COLOR_SPACE_MAP = {
    1: ColorSpace.GRAY,
    3: ColorSpace.RGB,
    4: ColorSpace.RGBA,
}


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

    class Config:
        arbitrary_types_allowed = True

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

    @property
    def window_center(self) -> Optional[float]:
        try:
            return float(self.image.GetMetaData("WindowCenter"))
        except (RuntimeError, ValueError):
            return None

    @property
    def window_width(self) -> Optional[float]:
        try:
            return float(self.image.GetMetaData("WindowWidth"))
        except (RuntimeError, ValueError):
            return None

    @property
    def timepoints(self) -> Optional[int]:
        if self.image.GetDimension() == 4:
            return int(self.image.GetSize()[-1])
        else:
            return None

    @validator("image")
    def check_color_space(cls, image: Image):
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

    class Config:
        underscore_attrs_are_private = True

    @property
    def width(self) -> int:
        return int(
            self._get_property(
                tiff_key="ImageWidth", openslide_key="openslide.level[0].width"
            )
        )

    @property
    def height(self) -> int:
        return int(
            self._get_property(
                tiff_key="ImageLength",
                openslide_key="openslide.level[0].height",
            )
        )

    @property
    def voxel_width_mm(self) -> float:
        try:
            return self._get_tiff_resolution(tiff_key="XResolution")
        except (ValueError, TypeError, ZeroDivisionError, IndexError) as e:
            logger.debug(e)

        return float(
            self._get_openslide_property(openslide_key="openslide.mpp-x")
            / 1000
        )

    @property
    def voxel_height_mm(self) -> float:
        try:
            return self._get_tiff_resolution(tiff_key="YResolution")
        except (ValueError, TypeError, ZeroDivisionError, IndexError) as e:
            logger.debug(e)

        return float(
            self._get_openslide_property(openslide_key="openslide.mpp-y")
            / 1000
        )

    def _get_tiff_resolution(self, *, tiff_key: str) -> float:
        res = self._get_tiff_property(tiff_key=tiff_key)
        res_unit = str(self._get_tiff_property(tiff_key="ResolutionUnit"))

        if res_unit.upper() == "RESUNIT.INCH":
            return 25.4 / (res[0] / res[1])
        elif res_unit.upper() == "RESUNIT.CENTIMETER":
            return 10 / (res[0] / res[1])
        raise ValueError(
            f"Invalid resolution unit {res_unit} in {self.file}"
        )

    @property
    def resolution_levels(self) -> int:
        with TiffFile(str(self.file.absolute())) as f:
            try:
                return len(f.pages)
            except AttributeError:
                logger.debug(
                    f"Could not determine number of pages for {self.file}"
                )

        return int(
            self._get_openslide_property(openslide_key="openslide.level-count")
        )

    @property
    def color_space(self) -> ColorSpace:
        color_space = self._get_tiff_property(
            tiff_key="PhotometricInterpretation"
        )
        color_space_code = str(color_space).split(".")[1].upper()

        if color_space_code == "MINISBLACK":
            return ColorSpace.GRAY
        else:
            return ColorSpace[color_space_code]

    def _get_property(self, *, tiff_key: str, openslide_key: str):
        try:
            return self._get_tiff_property(tiff_key=tiff_key)
        except ValueError as e:
            logger.debug(e)

        try:
            return self._get_openslide_property(openslide_key=openslide_key)
        except ValueError as e:
            logger.debug(e)

        raise ValueError(
            f"Could not find {tiff_key} or {openslide_key} in {self.file}"
        )

    def _get_tiff_property(self, *, tiff_key: str):
        with TiffFile(str(self.file.absolute())) as f:
            try:
                return f.pages[0].tags[tiff_key].value
            except (IndexError, KeyError, AttributeError):
                raise ValueError(
                    f"Could not find {tiff_key} in {self.file} using tifffile"
                )

    def _get_openslide_property(self, *, openslide_key: str):
        with open_slide(str(self.file.absolute())) as f:
            try:
                return f.properties[openslide_key]
            except KeyError:
                raise ValueError(
                    f"Could not find {openslide_key} in {self.file} using openslide"
                )

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
