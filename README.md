# panimg

[![CI](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DIAGNijmegen/rse-panimg/actions/workflows/ci.yml?query=branch%3Amain)
![PyPI](https://img.shields.io/pypi/v/panimg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panimg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Conversion of medical images to MHA and TIFF. 
Requires Python 3.7, 3.8 or 3.9.
`libvips-dev` and `libopenslide-dev` must be installed on your system.

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
