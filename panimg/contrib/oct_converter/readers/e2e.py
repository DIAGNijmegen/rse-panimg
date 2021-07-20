import re
import struct

import numpy as np
from construct import (
    PaddedString,
    Int16un,
    Struct,
    Int32sn,
    Int32un,
    Int8un,
)
from panimg.contrib.oct_converter.image_types import (
    OCTVolumeWithMetaData,
    FundusImageWithMetaData,
)
from pathlib import Path


class E2E:
    """ Class for extracting data from Heidelberg's .e2e file format.

        Notes:
            Mostly based on description of .e2e file format here:
            https://bitbucket.org/uocte/uocte/wiki/Heidelberg%20File%20Format.

        Attributes:
            filepath (str): Path to .img file for reading.
            header_structure (obj:Struct): Defines structure of volume's header.
            main_directory_structure (obj:Struct): Defines structure of volume's main directory.
            sub_directory_structure (obj:Struct): Defines structure of each sub directory in the volume.
            chunk_structure (obj:Struct): Defines structure of each data chunk.
            image_structure (obj:Struct): Defines structure of image header.
    """

    def __init__(self, filepath):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(self.filepath)

        self.chunk_structure = Struct(
            "magic" / PaddedString(12, "ascii"),
            "unknown" / Int32un,
            "unknown2" / Int32un,
            "pos" / Int32un,
            "size" / Int32un,
            "unknown3" / Int32un,
            "patient_id" / Int32un,
            "study_id" / Int32un,
            "series_id" / Int32un,
            "slice_id" / Int32sn,
            "ind" / Int16un,
            "unknown4" / Int16un,
            "type" / Int32un,
            "unknown5" / Int32un,
        )
        self.image_structure = Struct(
            "size" / Int32un,
            "type" / Int32un,
            "unknown" / Int32un,
            "width" / Int32un,
            "height" / Int32un,
        )
        self.lat_structure = Struct(
            "unknown" / PaddedString(14, "ascii"),
            "laterality" / Int8un,
            "unknown2" / Int8un,
        )

    def find_data_chunks(self, f):
        data = f.read()
        # find all 'MDbData' chunks
        regex_pattern = re.compile(b"MDbData")
        matches = regex_pattern.finditer(data)
        positions = []
        for match in matches:
            positions.append(match.start())
        return positions

    def extract_laterality_data(self, f):
        raw = f.read(20)
        try:
            laterality_data = self.lat_structure.parse(raw)
            if laterality_data.laterality == 82:
                laterality = "R"
            elif laterality_data.laterality == 76:
                laterality = "L"
        except:
            laterality = None
        return laterality

    def read_oct_volume(self):
        with open(self.filepath, "rb") as f:
            """ Reads oct data.

                Returns:
                    obj:OCTVolumeWithMetaData
            """
            chunk_positions = self.find_data_chunks(f)

            # first pass through MDbData chunks:
            # - save volume names
            # - save all oct data start positions for second pass
            # - extract laterality info
            chunk_stack = []
            volume_dict = []
            for start in chunk_positions:
                f.seek(start)
                raw = f.read(60)
                chunk = self.chunk_structure.parse(raw)

                if chunk.type == 11:  # laterality data
                    self.laterality = self.extract_laterality_data(f)

                if chunk.type == 1073741824:  # image data
                    if chunk.ind == 1:  # oct data
                        volume_string = f"{chunk.patient_id}_{chunk.study_id}_{chunk.series_id}"
                        volume_dict.append(volume_string)
                        chunk_stack.append(start)

            # second pass through MDbData chunks:
            # - extract OCT image data
            volume_array_dict = {}
            for volume in set(volume_dict):
                volume_array_dict[volume] = [0] * len(
                    [slice for slice in volume_dict if slice == volume]
                )

            for pos in chunk_stack:
                f.seek(pos)
                raw = f.read(60)
                chunk = self.chunk_structure.parse(raw)

                raw = f.read(20)
                image_data = self.image_structure.parse(raw)

                all_bits = [
                    f.read(2)
                    for i in range(image_data.height * image_data.width)
                ]
                raw_volume = list(map(self.read_custom_float, all_bits))
                image = np.array(raw_volume).reshape(
                    image_data.width, image_data.height
                )
                image = (image * 255).astype(np.uint8)
                image = 256 * pow(image, 1.0 / 2.4)
                volume_string = (
                    f"{chunk.patient_id}_{chunk.study_id}_{chunk.series_id}"
                )
                volume_array_dict[volume_string][
                    int(chunk.slice_id / 2) - 1
                ] = image

            oct_volumes = []
            for key, volume in volume_array_dict.items():
                oct_volumes.append(
                    OCTVolumeWithMetaData(
                        volume=volume,
                        patient_id=key,
                        laterality=self.laterality,
                    )
                )

        return oct_volumes

    def read_fundus_image(self):
        """ Reads fundus data.

            Returns:
                obj:FundusImageWithMetaData
        """
        with open(self.filepath, "rb") as f:
            chunk_positions = self.find_data_chunks(f)
            # initalise dict to hold all the image volumes
            image_array_dict = {}
            # traverse all chunks and extract slices
            for start in chunk_positions:
                f.seek(start)
                raw = f.read(60)
                chunk = self.chunk_structure.parse(raw)

                if chunk.type == 11:  # laterality data
                    self.laterality = self.extract_laterality_data(f)

                if chunk.type == 1073741824:  # image data
                    raw = f.read(20)
                    image_data = self.image_structure.parse(raw)

                    if chunk.ind == 0:  # fundus data
                        raw_volume = np.frombuffer(
                            f.read(image_data.height * image_data.width),
                            dtype=np.uint8,
                        )
                        image = np.array(raw_volume).reshape(
                            image_data.height, image_data.width
                        )
                        image_string = f"{chunk.patient_id}_{chunk.study_id}_{chunk.series_id}"
                        image_array_dict[image_string] = image

            fundus_images = []
            for key, image in image_array_dict.items():
                fundus_images.append(
                    FundusImageWithMetaData(
                        image=image, patient_id=key, laterality=self.laterality
                    )
                )

        return fundus_images

    def read_custom_float(self, bytes):
        """ Implementation of bespoke float type used in .e2e files.

        Notes:
            Custom float is a floating point type with no sign, 6-bit exponent, and 10-bit mantissa.

        Args:
            bytes (str): The two bytes.

        Returns:
            float
        """
        power = pow(2, 10)
        # convert two bytes to 16-bit binary representation
        bits = (
            bin(bytes[0])[2:].zfill(8)[::-1] + bin(bytes[1])[2:].zfill(8)[::-1]
        )

        # get mantissa and exponent
        mantissa = bits[:10]
        exponent = bits[10:]

        # convert to decimal representations
        mantissa_sum = 1 + int(mantissa, 2) / power
        exponent_sum = int(exponent[::-1], 2) - 63
        decimal_value = mantissa_sum * pow(2, exponent_sum)
        return decimal_value
