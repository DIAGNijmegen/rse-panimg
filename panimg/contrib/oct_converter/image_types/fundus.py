class FundusImageWithMetaData:
    """ Class to hold the fundus image and any related metadata, and enable saving.

    Attributes:
        image (np.array): Fundus image.
        laterality (str): Left or right eye.
        patient_id (str): Patient ID.
        DOB (str): Patient date of birth.
    """

    def __init__(
        self, image, laterality=None, patient_id=None, patient_dob=None
    ):
        self.image = image
        self.laterality = laterality
        self.patient_id = patient_id
        self.DOB = patient_dob
