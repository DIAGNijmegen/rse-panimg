import urllib.request

import pytest

from tests import RESOURCE_PATH


@pytest.fixture(scope="session", autouse=True)
def downloaded_isyntax_image():
    url = "https://zenodo.org/record/5037046/files/testslide.isyntax"
    image_path = RESOURCE_PATH / "isyntax_wsi" / "testslide.isyntax"
    image_path.parent.mkdir(exist_ok=True)

    if not image_path.exists():
        urllib.request.urlretrieve(url, image_path)

    return image_path
