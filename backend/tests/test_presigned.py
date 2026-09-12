import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.api.endpoints.datasets.datasets import get_presigned_url


def test_presigned_url_generation():
    """Test generating a presigned upload URL from the datasets endpoint."""
    mock_user = {
        "_id": "6a43a0a0c91c0e9fcdd045ac",
        "email": "test@example.com",
        "external_id": "114273893325363479564",
        "role_ids": ["6a54b78eac3a8e2764706369"],
    }
    resp = get_presigned_url("test_upload.csv", current_user=mock_user)
    assert resp.upload_url, "Response missing upload_url"
    assert resp.object_name, "Response missing object_name"
    assert "test_upload" in resp.object_name, "Object name should contain filename prefix"
    assert len(resp.upload_url) > 0, "upload_url should not be empty"
    print("✓ Presigned URL generation passed successfully!")


if __name__ == "__main__":
    test_presigned_url_generation()
