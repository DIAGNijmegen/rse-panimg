from typing import Set

import SimpleITK

from panimg.models import ImageType, PanImgFile, PostProcessorResult

MINIMUM_VALUE_TAG = "SmallestImagePixelValue"
MAXIMUM_VALUE_TAG = "LargestImagePixelValue"


def mha_pixel_range(*, image_files: Set[PanImgFile]) -> PostProcessorResult:
    reader = SimpleITK.ImageFileReader()
    writer = SimpleITK.ImageFileWriter()

    for file in image_files:
        if file.image_type != ImageType.MHD:
            continue

        reader.SetFileName(str(file.file.absolute()))

        reader.ReadImageInformation()
        if reader.HasMetaDataKey(MINIMUM_VALUE_TAG) and reader.HasMetaDataKey(
            MAXIMUM_VALUE_TAG
        ):
            continue

        image = reader.Execute()

        # Use the numpy-array route to support a larger range of data-types
        # than ITK' MinimumMaximumImageFilter (e.g. 2D uint8)
        array = SimpleITK.GetArrayViewFromImage(image)
        image.SetMetaData(MINIMUM_VALUE_TAG, str(array.min()))
        image.SetMetaData(MAXIMUM_VALUE_TAG, str(array.max()))

        writer.SetFileName(str(file.file.absolute()))
        writer.Execute(image)

    # No files or folders have been added
    return PostProcessorResult(new_image_files=set(), new_folders=set())
