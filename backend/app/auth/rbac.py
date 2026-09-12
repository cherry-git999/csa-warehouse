"""
Centralized Role-Based Access Control (RBAC) service.
Provides role resolution, hierarchy determination, and endpoint access evaluation.
"""
import logging
from typing import List, Optional, Dict, Any
from app.schemas.models import RoleCheckResponse
from app.db.crud import get_role_by_id, initialize_default_endpoint_access
from app.db.database import endpoint_access_collection

logger = logging.getLogger(__name__)

# Role hierarchy ordered from most privileged to least privileged
ROLE_HIERARCHY = ["superadmin", "admin", "contributor", "viewer", "user"]


class RBACService:
    """Centralized RBAC service for permission checking and role management."""

    @staticmethod
    def extract_role_ids(user: Optional[Dict[str, Any]]) -> List[str]:
        """Extract plural role_ids from a user document, falling back to legacy role_id."""
        if not user:
            return []

        # Support both role_ids and role_id property names
        raw_ids = user.get("role_ids")
        if raw_ids is None:
            raw_ids = user.get("role_id")

        if not raw_ids:
            return []

        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]

        # Convert all to string format for consistent querying
        return [str(r_id) for r_id in raw_ids if r_id is not None]

    @classmethod
    def resolve_roles(cls, user: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve full role documents from user's role_ids."""
        role_ids = cls.extract_role_ids(user)
        roles = []
        for r_id in role_ids:
            try:
                role = get_role_by_id(r_id)
                if role and role.get("is_active", True):
                    roles.append(role)
            except Exception as e:
                logger.warning("Failed to resolve role id %s: %s", r_id, e)
        return roles

    @classmethod
    def get_role_names(cls, user: Optional[Dict[str, Any]]) -> List[str]:
        """Get all active role names for the user."""
        roles = cls.resolve_roles(user)
        names = []
        for r in roles:
            name = r.get("role_name") or r.get("role-name")
            if name:
                names.append(name.lower())
        return names

    @classmethod
    def get_primary_role_name(cls, role_names: List[str]) -> str:
        """Determine the primary role name based on hierarchy."""
        normalized = [name.lower() for name in role_names]
        for role in ROLE_HIERARCHY:
            if role in normalized:
                return role
        return normalized[0] if normalized else "user"

    @staticmethod
    def find_matching_endpoint_access(role: str, path: str) -> Optional[Dict[str, Any]]:
        """Find the most specific endpoint access rule matching the given path for a role."""
        all_access = list(endpoint_access_collection.find({"role": role}))
        if not all_access:
            return None

        # Sort by endpoint specificity (longer path prefix first)
        sorted_access = sorted(
            all_access,
            key=lambda x: len(x.get("endpoint", "")),
            reverse=True,
        )

        for access in sorted_access:
            endpoint_pattern = access.get("endpoint", "")
            if path.startswith(endpoint_pattern):
                return access

        return None

    @classmethod
    def check_access(cls, user: Optional[Dict[str, Any]], path: str) -> RoleCheckResponse:
        """
        Evaluate access for a user on a given path.
        Centralizes flow for superadmin, admin, and multi-role users.
        """
        initialize_default_endpoint_access()

        role_names = cls.get_role_names(user)
        primary_role = cls.get_primary_role_name(role_names)
        logger.debug("Evaluating RBAC access: user_roles=%s primary_role=%s path=%s", role_names, primary_role, path)

        # 1. Superadmin flow: complete unrestricted access
        if "superadmin" in role_names:
            return RoleCheckResponse(
                viewer=True,
                contributor=True,
                admin=True,
                role_name="superadmin",
            )

        # 2. Admin flow: check explicit admin access or default to full admin privileges
        if "admin" in role_names:
            access_rule = cls.find_matching_endpoint_access("admin", path)
            if access_rule:
                return RoleCheckResponse(
                    viewer=access_rule.get("viewer", True),
                    contributor=access_rule.get("contributor", True),
                    admin=access_rule.get("admin", True),
                    role_name="admin",
                )
            return RoleCheckResponse(
                viewer=True,
                contributor=True,
                admin=True,
                role_name="admin",
            )

        # 3. Standard / multi-role flow: aggregate permissions across all assigned roles
        can_view = False
        can_contribute = False
        can_admin = False
        matched_any = False

        effective_roles = role_names if role_names else ["user"]
        for role_name in effective_roles:
            access_rule = cls.find_matching_endpoint_access(role_name, path)
            if access_rule:
                matched_any = True
                can_view = can_view or access_rule.get("viewer", False)
                can_contribute = can_contribute or access_rule.get("contributor", False)
                can_admin = can_admin or access_rule.get("admin", False)

        if not matched_any:
            logger.info("No RBAC endpoint access rule matched: roles=%s path=%s", effective_roles, path)
            return RoleCheckResponse(
                viewer=False,
                contributor=False,
                admin=False,
                role_name=primary_role,
            )

        return RoleCheckResponse(
            viewer=can_view,
            contributor=can_contribute,
            admin=can_admin,
            role_name=primary_role,
        )


rbac = RBACService()
