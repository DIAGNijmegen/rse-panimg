# panimg

`panimg` takes a folder of image files, and creates MetaImage, or TIFF/DZI, depending on the input. 

The converter supports several strategies.

## Usage

Current usage in grand challenge

```python

@dataclass
class ImageBuilderResult:
    new_images: Set[Image]
    new_image_files: Set[ImageFile]
    new_folders: Set[FolderUpload]
    consumed_files: Set[Path]
    file_errors: Dict[Path, str]

@dataclass
class ImporterResult:
    new_images: Set[Image]
    consumed_files: Set[Path]
    file_errors: Dict[Path, List[str]]

DEFAULT_IMAGE_BUILDERS = [
    image_builder_mhd,
    image_builder_nifti,
    image_builder_dicom,
    image_builder_tiff,
    image_builder_fallback,
]

import_images(
    *,
    files: Set[Path],
    origin: RawImageUploadSession = None,
    builders: Iterable[Callable] = None,
) -> ImporterResult

```

We would like

```python
import panimg

panimg.convert(*, files: Set[Path], strategies: Optional[Iterable[PanimgStrategy]], prefix: str = "") -> PanimgResult
```
