from pathlib import Path
from typing import Iterator, Protocol, Set, Union

from panimg.models import (
    PanImgFile,
    PostProcessorResult,
    SimpleITKImage,
    TIFFImage,
)


class ImageBuilder(Protocol):
    def __call__(
        self, *, files: Set[Path]
    ) -> Union[Iterator[SimpleITKImage], Iterator[TIFFImage]]:
        ...


class PostProcessor(Protocol):
    def __call__(self, *, image_files: Set[PanImgFile]) -> PostProcessorResult:
        ...
