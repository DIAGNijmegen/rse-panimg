from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import UUID

from SimpleITK import Image
from pydantic.dataclasses import dataclass


class ColorSpace(str, Enum):
    GRAY = "GRAY"
    RGB = "RGB"
    RGBA = "RGBA"
    YCBCR = "YCBCR"


class ImageType(str, Enum):
    MHD = "MHD"
    TIFF = "TIFF"
    DZI = "DZI"


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


class SimpleITKImageConfig:
    arbitrary_types_allowed = True


@dataclass(config=SimpleITKImageConfig)
class SimpleITKImage:
    image: Image
    name: str
    consumed_files: Set[Path]
    use_spacing: bool


@dataclass
class TIFFImage:
    file: Path
    name: str
    consumed_files: Set[Path]
    width: int
    height: int
    voxel_width_mm: Optional[float]
    voxel_height_mm: Optional[float]
    voxel_depth_mm: Optional[float]
    resolution_levels: Optional[int]
    color_space: ColorSpace
