import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient

# Ensure backend root is on Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
