# panimg

[![CI](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/pypi/v/panimg)](https://pypi.org/project/panimg/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panimg)](https://pypi.org/project/panimg/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NOT FOR CLINICAL USE**

Conversion of medical images to MHA and TIFF. 
Requires Python 3.7, 3.8 or 3.9.
`libvips-dev` and `libopenslide-dev` must be installed on your system.

Under the hood we use:

* `SimpleITK`
* `pydicom`
* `pylibjpeg`  
* `Pillow`
* `openslide-python`
* `pyvips`
* `oct-converter`

## Usage

`panimg` takes a folder and tries to convert the containing files to MHA or TIFF.
By default, it will try to convert files from subdirectories as well.
To only convert files in the top level directory, set `recurse_subdirectories` to `False`.
It will try several strategies for loading the contained files, and if an image is found it will output it to the output folder.
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

### Command Line Interface

`panimg` is also accessible from the command line.
Install the package from pip as before, then you can use:

**NOTE: Alpha software, do not run this on folders you do not have a backup of.**

```shell
panimg convert /path/to/files/ /where/files/will/go/
```

To access the help test you can use `panimg -h`.

### Supported Formats

| Input                               | Output  | Strategy   | Notes                      |
| ----------------------------------- | --------| ---------- | -------------------------- |
| `.mha`                              | `.mha`  | `metaio`   |                            |
| `.mhd` with `.raw` or `.zraw`       | `.mha`  | `metaio`   |                            |
| `.dcm`                              | `.mha`  | `dicom`    |                            |
| `.nii`                              | `.mha`  | `nifti`    |                            |
| `.nii.gz`                           | `.mha`  | `nifti`    |                            |
| `.e2e`                              | `.mha`  | `oct`      | <sup>[1](#footnote1)</sup> |
| `.fds`                              | `.mha`  | `oct`      | <sup>[1](#footnote1)</sup> |
| `.fda`                              | `.mha`  | `oct`      | <sup>[1](#footnote1)</sup> |
| `.png`                              | `.mha`  | `fallback` | <sup>[2](#footnote2)</sup> |
| `.jpeg`                             | `.mha`  | `fallback` | <sup>[2](#footnote2)</sup> |
| `.tiff`                             | `.tiff` | `tiff`     |                            |
| `.svs` (Aperio)                     | `.tiff` | `tiff`     |                            |
| `.vms`, `.vmu`, `.ndpi` (Hamamatsu) | `.tiff` | `tiff`     |                            |
| `.scn` (Leica)                      | `.tiff` | `tiff`     |                            |
| `.mrxs` (MIRAX)                     | `.tiff` | `tiff`     |                            |
| `.biff` (Ventana)                   | `.tiff` | `tiff`     |                            |

<a name="footnote1">1</a>: Only OCT volume(s), no fundus image(s) will be extracted.

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
