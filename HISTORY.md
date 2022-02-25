# History

## 0.6.0 (2022-02-25)

* Added support for enhanced DICOM files
* Added header validation for nrrd and nifti files

## 0.5.3 (2022-02-01)

* Fix determination of slice spacing with oblique volumes

## 0.5.2 (2021-10-20)

* Fix duplicate except clause

## 0.5.1 (2021-10-04)

* Fix default values for extra metadata fields

## 0.5.0 (2021-10-01)

* Added extra metadata fields to PanImg object
* Allow array-like window level values in MHA files
* Simplified 4D ITK loading

## 0.4.2 (2021-09-06)

* Added support for nrrd files

## 0.4.1 (2021-08-31)

* Added support for vips 8.10

## 0.4.0 (2021-08-09)

* Removed dependency on `gdcm`
* `panimg` now requires `pydicom>=2.2`

## 0.3.2 (2021-08-06)

* Added `recurse_subdirectories` option to `convert`

## 0.3.1 (2021-07-26)

* Added support for e2e files

## 0.3.0 (2021-05-31)

* Added support for fds and fda images
* Added a CLI

## 0.2.2 (2021-05-05)

* Fix imports in subdirectories

## 0.2.1 (2021-04-12)

* Allows importing without pyvips and openslide
  * Checks for these libraries are now only done where needed at runtime

## 0.2.0 (2021-03-23)

* Builders now return generators
* Added post processors

## 0.1.0 (2021-03-09)

* Initial version
