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
