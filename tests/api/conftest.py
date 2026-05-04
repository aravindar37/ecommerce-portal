import pytest

from tests.helpers.test_client import reset_and_seed


@pytest.fixture(scope="module", autouse=True)
def seeded_demo_data() -> None:
    reset_and_seed()

