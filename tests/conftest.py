import urllib.request

import pytest

from tests import RESOURCE_PATH


def pytest_addoption(parser):
    parser.addoption(
        "--download-files",
        action="store_true",
        default=False,
        help="Download large test files.",
    )


@pytest.fixture(scope="session")
def download_files(request):
    return request.config.getoption("--download-files")


@pytest.fixture(scope="session", autouse=True)
def downloaded_isyntax_image(download_files):
    url = "https://zenodo.org/record/5037046/files/testslide.isyntax"
    image_path = RESOURCE_PATH / "isyntax_wsi" / "testslide.isyntax"

    if not image_path.exists() and download_files:
        image_path.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(url, image_path)

    return image_path
