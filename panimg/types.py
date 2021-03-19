from pathlib import Path
from typing import Iterator, Set

from typing_extensions import Protocol  # for py37 support

from panimg.models import FileLoaderResult, PanImgFile, PostProcessorResult


class ImageBuilder(Protocol):
    def __call__(self, *, files: Set[Path]) -> Iterator[FileLoaderResult]:
        ...


class PostProcessor(Protocol):
    def __call__(self, *, image_files: Set[PanImgFile]) -> PostProcessorResult:
        ...
