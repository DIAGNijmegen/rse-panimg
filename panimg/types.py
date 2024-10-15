from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, Union

from panimg.models import (
    PanImgFile,
    PostProcessorResult,
    SimpleITKImage,
    TIFFImage,
)


class ImageBuilder(Protocol):
    def __call__(  # noqa: E704
        self, *, files: set[Path]
    ) -> Union[Iterator[SimpleITKImage], Iterator[TIFFImage]]: ...


class PostProcessor(Protocol):
    def __call__(  # noqa: E704
        self, *, image_files: set[PanImgFile]
    ) -> PostProcessorResult: ...
