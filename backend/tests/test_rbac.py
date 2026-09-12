import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.auth.rbac import rbac, RBACService


def test_extract_role_ids():
    """Test extracting role_ids with both plural role_ids and legacy role_id."""
    # Plural role_ids
    user1 = {"role_ids": ["role1", "role2"]}
    assert rbac.extract_role_ids(user1) == ["role1", "role2"]

    # Legacy role_id as list
    user2 = {"role_id": ["role3"]}
    assert rbac.extract_role_ids(user2) == ["role3"]

    # Legacy role_id as single string
    user3 = {"role_id": "role4"}
    assert rbac.extract_role_ids(user3) == ["role4"]

    # Empty user
    assert rbac.extract_role_ids({}) == []
    assert rbac.extract_role_ids(None) == []


def test_primary_role_hierarchy():
    """Test primary role hierarchy determination."""
    assert rbac.get_primary_role_name(["user", "admin"]) == "admin"
    assert rbac.get_primary_role_name(["admin", "superadmin"]) == "superadmin"
    assert rbac.get_primary_role_name(["user"]) == "user"
    assert rbac.get_primary_role_name([]) == "user"


def test_superadmin_access_flow():
    """Test superadmin has full access across endpoints."""
    # Mock user object with superadmin
    class MockSuperadminRBAC(RBACService):
        @classmethod
        def get_role_names(cls, user):
            return ["superadmin"]

    res = MockSuperadminRBAC.check_access({"role_ids": ["superadmin_id"]}, "/datastore/create")
    assert res.viewer is True
    assert res.contributor is True
    assert res.admin is True
    assert res.role_name == "superadmin"


def test_admin_access_flow():
    """Test admin has full access across standard dashboard and dataset endpoints."""
    class MockAdminRBAC(RBACService):
        @classmethod
        def get_role_names(cls, user):
            return ["admin"]

    res = MockAdminRBAC.check_access({"role_ids": ["admin_id"]}, "/dashboard")
    assert res.viewer is True
    assert res.contributor is True
    assert res.admin is True
    assert res.role_name == "admin"


if __name__ == "__main__":
    test_extract_role_ids()
    test_primary_role_hierarchy()
    test_superadmin_access_flow()
    test_admin_access_flow()
    print("All RBAC tests passed successfully!")
