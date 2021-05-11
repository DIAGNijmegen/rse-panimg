import os
import numpy as np

try:
    import imageio
except ImportError:
    imageio = False
try:
    import cv2
except ImportError:
    cv2 = False
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = False

VIDEO_TYPES = [
    ".avi",
    ".mp4",
]
IMAGE_TYPES = [".png", ".bmp", ".tiff", ".jpg", ".jpeg"]


class OCTVolumeWithMetaData:
    """ Class to hold the OCT volume and any related metadata, and enable viewing and saving.

    Attributes:
        volume (list of np.array): All the volume's b-scans.
        laterality (str): Left or right eye.
        patient_id (str): Patient ID.
        DOB (str): Patient date of birth.
        num_slices: Number of b-scans present in volume.
    """

    def __init__(
        self, volume, laterality=None, patient_id=None, patient_dob=None
    ):
        self.volume = volume
        self.laterality = laterality
        self.patient_id = patient_id
        self.DOB = patient_dob
        self.num_slices = len(self.volume)

    def peek(self, rows=5, cols=5, filepath=None):
        """ Plots a montage of the OCT volume. Optionally saves the plot if a filepath is provided.

        Args:
            rows (int) : Number of rows in the plot.
            cols (int) : Number of columns in the plot.
            filepath (str): Location to save montage to.
        """
        if plt is False:
            raise RuntimeError(
                "matplotlib is missing, please install oct-converter[extras]"
            )

        images = rows * cols
        x_size = rows * self.volume[0].shape[0]
        y_size = cols * self.volume[0].shape[1]
        ratio = y_size / x_size
        slices_indices = np.linspace(0, self.num_slices - 1, images).astype(
            np.int
        )
        plt.figure(figsize=(12 * ratio, 12))
        for i in range(images):
            plt.subplot(rows, cols, i + 1)
            plt.imshow(self.volume[slices_indices[i]], cmap="gray")
            plt.axis("off")
            plt.title("{}".format(slices_indices[i]))
        plt.suptitle(f"OCT volume with {self.num_slices} slices.")

        if filepath is not None:
            plt.savefig(filepath)
        else:
            plt.show()

    def save(self, filepath):
        """Saves OCT volume as a video or stack of slices.

        Args:
            filepath (str): Location to save volume to. Extension must be in VIDEO_TYPES or IMAGE_TYPES.
        """
        if imageio is False:
            raise RuntimeError(
                "imageio is missing, please install oct-converter[extras]"
            )

        if cv2 is False:
            raise RuntimeError(
                "cv2 is missing, please install oct-converter[extras]"
            )

        extension = os.path.splitext(filepath)[1]
        if extension.lower() in VIDEO_TYPES:
            video_writer = imageio.get_writer(filepath, macro_block_size=None)
            for slice in self.volume:
                video_writer.append_data(slice)
            video_writer.close()
        elif extension.lower() in IMAGE_TYPES:
            base = os.path.splitext(os.path.basename(filepath))[0]
            print(
                "Saving OCT as sequential slices {}_[1..{}]{}".format(
                    base, len(self.volume), extension
                )
            )
            full_base = os.path.splitext(filepath)[0]
            for index, slice in enumerate(self.volume):
                filename = f"{full_base}_{index}{extension}"
                cv2.imwrite(filename, slice)
        elif extension.lower() == ".npy":
            np.save(filepath, self.volume)
        else:
            raise NotImplementedError(
                f"Saving with file extension {extension} not supported"
            )
