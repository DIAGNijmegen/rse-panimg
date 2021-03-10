from pathlib import Path
from typing import Protocol, Set

from panimg.models import PanImgResult


class ImageBuilder(Protocol):
    def __call__(
        self,
        *,
        files: Set[Path],
        output_directory: Path,
        created_image_prefix: str,
    ) -> PanImgResult:
        ...
