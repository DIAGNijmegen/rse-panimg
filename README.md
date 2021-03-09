# panimg

[![CI](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml?query=branch%3Amain)
![PyPI](https://img.shields.io/pypi/v/panimg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panimg)
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

| Input                               | Output           | Strategy   | Notes                      |
| ----------------------------------- | ---------------- | ---------- | -------------------------- |
| `.mha`                              | `.mha`           | `metaio`   |                            |
| `.mhd` with `.raw` or `.zraw`       | `.mha`           | `metaio`   |                            |
| `.dcm`                              | `.mha`           | `dicom`    | <sup>[1](#footnote1)</sup> |
| `.nii`                              | `.mha`           | `nifty`    |                            |
| `.nii.gz`                           | `.mha`           | `nifty`    |                            |
| `.png`                              | `.mha`           | `fallback` | <sup>[2](#footnote2)</sup> |
| `.jpeg`                             | `.mha`           | `fallback` | <sup>[2](#footnote2)</sup> |
| `.tiff`                             | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |
| `.svs` (Aperio)                     | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |
| `.vms`, `.vmu`, `.ndpi` (Hamamatsu) | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |
| `.scn` (Leica)                      | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |
| `.mrxs` (MIRAX)                     | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |
| `.biff` (Ventana)                   | `.tiff` & `.dzi` | `tiff`     | <sup>[3](#footnote3)</sup> |

<a name="footnote1">1</a>: Compressed DICOM requires `gdcm`

<a name="footnote2">2</a>: 2D only, unitary dimensions

<a name="footnote3">3</a>: DZI only created if possible
