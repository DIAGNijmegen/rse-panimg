from pathlib import Path

import numpy as np
from construct import Int32un, PaddedString, Struct

from panimg.contrib.oct_converter.image_types import (
    FundusImageWithMetaData,
    OCTVolumeWithMetaData,
)


class FDS:
    """Class for extracting data from Topcon's .fds file format.

    Notes:
        Mostly based on description of .fds file format here:
        https://bitbucket.org/uocte/uocte/wiki/Topcon%20File%20Format

    Attributes:
        filepath (str): Path to .img file for reading.
        header (obj:Struct): Defines structure of volume's header.
        oct_header (obj:Struct): Defines structure of OCT header.
        fundus_header (obj:Struct): Defines structure of fundus header.
        chunk_dict (dict): Name of data chunks present in the file, and their start locations.
    """

    def __init__(self, filepath):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(self.filepath)

        self.header = Struct(
            "FOCT" / PaddedString(4, "ascii"),
            "FDA" / PaddedString(3, "ascii"),
            "version_info_1" / Int32un,
            "version_info_2" / Int32un,
        )
        self.oct_header = Struct(
            "unknown" / PaddedString(1, "ascii"),
            "width" / Int32un,
            "height" / Int32un,
            "bits_per_pixel" / Int32un,
            "number_slices" / Int32un,
            "unknown" / PaddedString(1, "ascii"),
            "size" / Int32un,
        )
        self.fundus_header = Struct(
            "width" / Int32un,
            "height" / Int32un,
            "bits_per_pixel" / Int32un,
            "number_slices" / Int32un,
            "unknown" / PaddedString(1, "ascii"),
            "size" / Int32un,
        )
        self.chunk_dict = self.get_list_of_file_chunks()

    def get_list_of_file_chunks(self):
        """Find all data chunks present in the file.

        Returns:
            dict
        """
        chunk_dict = {}
        with open(self.filepath, "rb") as f:
            # skip header
            raw = f.read(15)
            header = self.header.parse(raw)

            eof = False
            while not eof:
                chunk_name_size = np.frombuffer(f.read(1), dtype=np.uint8)[0]
                if chunk_name_size == 0:
                    eof = True
                else:
                    chunk_name = f.read(chunk_name_size)
                    chunk_size = np.frombuffer(f.read(4), dtype=np.uint32)[0]
                    chunk_location = f.tell()
                    f.seek(chunk_size, 1)
                    chunk_dict[chunk_name] = [chunk_location, chunk_size]
        print(f"File {self.filepath} contains the following chunks:")
        for key in chunk_dict.keys():
            print(key)
        return chunk_dict

    def read_oct_volume(self):
        """Reads OCT data.

        Returns:
            obj:OCTVolumeWithMetaData
        """
        if b"@IMG_SCAN_03" not in self.chunk_dict:
            raise ValueError(
                "Could not find OCT header @IMG_SCAN_03 in chunk list"
            )
        with open(self.filepath, "rb") as f:
            chunk_location, chunk_size = self.chunk_dict[b"@IMG_SCAN_03"]
            f.seek(chunk_location)
            raw = f.read(22)
            oct_header = self.oct_header.parse(raw)
            number_pixels = (
                oct_header.width * oct_header.height * oct_header.number_slices
            )
            raw_volume = np.frombuffer(
                f.read(number_pixels * 2), dtype=np.uint16
            )
            volume = np.array(raw_volume)
            volume = volume.reshape(
                oct_header.width,
                oct_header.height,
                oct_header.number_slices,
                order="F",
            )
            volume = np.transpose(volume, [1, 0, 2])
        oct_volume = OCTVolumeWithMetaData(
            [volume[:, :, i] for i in range(volume.shape[2])]
        )
        return oct_volume

    def read_fundus_image(self):
        """Reads fundus image.

        Returns:
            obj:FundusImageWithMetaData
        """
        if b"@IMG_OBS" not in self.chunk_dict:
            raise ValueError(
                "Could not find fundus header @IMG_OBS in chunk list"
            )
        with open(self.filepath, "rb") as f:
            chunk_location, chunk_size = self.chunk_dict[b"@IMG_OBS"]
            f.seek(chunk_location)
            raw = f.read(21)
            fundus_header = self.fundus_header.parse(raw)
            # number_pixels = fundus_header.width * fundus_header.height * fundus_header.number_slices
            raw_image = np.frombuffer(
                f.read(fundus_header.size), dtype=np.uint8
            )
            # raw_image = [struct.unpack('B', f.read(1)) for pixel in range(fundus_header.size)]
            image = np.array(raw_image)
            image = image.reshape(
                3, fundus_header.width, fundus_header.height, order="F"
            )
            image = np.transpose(image, [2, 1, 0])
            image = image.astype(np.float32)
        fundus_image = FundusImageWithMetaData(image)
        return fundus_image
