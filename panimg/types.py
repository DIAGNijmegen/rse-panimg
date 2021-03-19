from pathlib import Path
from typing import DefaultDict, Iterator, List, Set

from typing_extensions import Protocol  # for py37 support

from panimg.models import FileLoaderResult, PanImgFile, PostProcessorResult


class ImageBuilder(Protocol):
    def __call__(
        self, *, files: Set[Path], file_errors: DefaultDict[Path, List[str]]
    ) -> Iterator[FileLoaderResult]:
        ...


class PostProcessor(Protocol):
    def __call__(self, *, image_files: Set[PanImgFile]) -> PostProcessorResult:
        ...
