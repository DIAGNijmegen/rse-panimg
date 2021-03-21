# panimg

[![CI](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/pypi/v/panimg)](https://pypi.org/project/panimg/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panimg)](https://pypi.org/project/panimg/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NOT FOR CLINICAL USE**

Conversion of medical images to MHA and TIFF. 
Requires Python 3.7, 3.8 or 3.9.
`libvips-dev` and `libopenslide-dev` must be installed on your system.
For compressed DICOM support ensure that `gdcm` is installed.

Under the hood we use:

* `SimpleITK`
* `pydicom`
* `Pillow`
* `openslide-python`
* `pyvips`

## Usage

`panimg` takes a folder full of files and tries to covert them to MHA or TIFF.
For each subdirectory of files it will try several strategies for loading the contained files, and if an image is found it will output it to the output folder.
It will return a structure containing information about what images were produced, what images were used to form the new images, image metadata, and any errors from any of the strategies.

**NOTE: Alpha software, do not run this on folders you do not have a backup of.**

```python
from pathlib import Path
from panimg import convert

result = convert(
    input_directory=Path("/path/to/files/"),
    output_directory=Path("/where/files/will/go/"),
)
```

### Supported Formats

| Input                               | Output  | Strategy   | Notes                      |
| ----------------------------------- | --------| ---------- | -------------------------- |
| `.mha`                              | `.mha`  | `metaio`   |                            |
| `.mhd` with `.raw` or `.zraw`       | `.mha`  | `metaio`   |                            |
| `.dcm`                              | `.mha`  | `dicom`    | <sup>[1](#footnote1)</sup> |
| `.nii`                              | `.mha`  | `nifti`    |                            |
| `.nii.gz`                           | `.mha`  | `nifti`    |                            |
| `.png`                              | `.mha`  | `fallback` | <sup>[2](#footnote2)</sup> |
| `.jpeg`                             | `.mha`  | `fallback` | <sup>[2](#footnote2)</sup> |
| `.tiff`                             | `.tiff` | `tiff`     |                            |
| `.svs` (Aperio)                     | `.tiff` | `tiff`     |                            |
| `.vms`, `.vmu`, `.ndpi` (Hamamatsu) | `.tiff` | `tiff`     |                            |
| `.scn` (Leica)                      | `.tiff` | `tiff`     |                            |
| `.mrxs` (MIRAX)                     | `.tiff` | `tiff`     |                            |
| `.biff` (Ventana)                   | `.tiff` | `tiff`     |                            |

<a name="footnote1">1</a>: Compressed DICOM requires `gdcm`

<a name="footnote2">2</a>: 2D only, unitary dimensions

#### Post Processors

You can also define a set of post processors that will operate on each output file.
We provide a `dzi_to_tiff` post processor that is enabled by default, which will produce a DZI file if it is able to.
To customise the post processors that run you can do this with

```python
result = convert(..., post_processors=[...])
```

#### Using Strategies Directly

If you want to run a particular strategy directly which returns a generator of images for a set of files you can do this with

```python
files = {f for f in Path("/foo/").glob("*.dcm") if f.is_file()}

try:
    for result in image_builder_dicom(files=files):
        sitk_image = result.image
        process(sitk_image)  # etc. you can also look at result.name for the name of the file,
                             # and result.consumed_files to see what files were used for this image
except UnconsumedFilesException as e:
    # e.errors is keyed with a Path to a file that could not be consumed,
    # with a list of all the errors found with loading it,
    # the user can then choose what to do with that information
    ...
```
