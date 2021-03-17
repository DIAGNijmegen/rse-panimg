from pathlib import Path
from typing import Set

from typing_extensions import Protocol  # for py37 support

from panimg.models import PanImgFile, PanImgResult


class ImageBuilder(Protocol):
    def __call__(
        self,
        *,
        files: Set[Path],
        output_directory: Path,
        created_image_prefix: str,
    ) -> PanImgResult:
        ...


class PostProcessor(Protocol):
    def __call__(self, *, image_files: Set[PanImgFile]) -> Set[PanImgFile]:
        ...
