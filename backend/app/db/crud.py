from uuid import UUID
from datetime import datetime
from ..schemas.models import User, CreateUserFromOAuth, Role
from .database import users_collection, datasets_collection, roles_collection, endpoint_access_collection
from bson import ObjectId


def user_to_dict(user: User):
    """Convert User model to a Mongo-storable dict.

    - Do not set `_id`; let MongoDB auto-generate ObjectId
    - Exclude `id` if None
    - Convert role_ids / role_id strings to ObjectIds for MongoDB storage
    """
    user_dict = user.model_dump(exclude_none=True)
    # Convert role_ids / role_id strings to ObjectIds for MongoDB storage
    for key in ('role_ids', 'role_id'):
        if key in user_dict and user_dict[key]:
            converted = []
            for r_id in user_dict[key]:
                try:
                    converted.append(ObjectId(str(r_id)))
                except Exception:
                    converted.append(str(r_id))
            user_dict[key] = converted

    # Maintain dual field compatibility in MongoDB
    if 'role_ids' in user_dict and 'role_id' not in user_dict:
        user_dict['role_id'] = user_dict['role_ids']
    elif 'role_id' in user_dict and 'role_ids' not in user_dict:
        user_dict['role_ids'] = user_dict['role_id']

    return user_dict


def role_to_dict(role: Role):
    """Convert Role model to a Mongo-storable dict.

    - Do not set `_id`; let MongoDB auto-generate ObjectId
    - Exclude `id` if present
    """
    role_dict = role.model_dump(exclude_none=True)
    role_dict.pop("id", None)
    return role_dict


def mongo_user_doc_to_dict(doc: dict):
    """Normalize a MongoDB user document to a response-friendly dict.

    - Ensures `_id` is a string
    - Converts role_id ObjectIds to strings for API compatibility
    - Leaves other fields as-is
    """
    if doc is None:
        return None
    normalized = dict(doc)
    if "_id" in normalized:
        normalized["_id"] = str(normalized["_id"])
    # Convert role_ids / role_id ObjectIds to strings for API responses
    raw_roles = normalized.get("role_ids")
    if raw_roles is None:
        raw_roles = normalized.get("role_id")
    if raw_roles:
        if not isinstance(raw_roles, list):
            raw_roles = [raw_roles]
        normalized["role_ids"] = [str(r) for r in raw_roles]
        normalized["role_id"] = normalized["role_ids"]
    return normalized


# User Operations
def create_user(user: User):
    users_collection.insert_one(user_to_dict(user))


def create_user_from_oauth(user_data: CreateUserFromOAuth):
    """Create a new user from OAuth provider data."""
    now = datetime.now()
    # Ensure default role exists and get its id
    default_role_id = ensure_default_role_and_get_id()

    user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        phone=user_data.phone,
        external_id=user_data.external_id,
        role_ids=[str(default_role_id)] if default_role_id else [],
        created_at=now,
        updated_at=now,
    )

    print(user)
    result = users_collection.insert_one(user_to_dict(user))
    # Return a combined object with generated id for caller convenience
    return {"_id": str(result.inserted_id), **user.model_dump()}


def get_user(user_id: UUID):
    # Accept both UUID strings and ObjectId strings; try ObjectId first
    query_id = None
    try:
        query_id = ObjectId(str(user_id))
    except Exception:
        query_id = str(user_id)
    result = users_collection.find_one({"_id": query_id})
    return result


def get_user_by_external_id(external_id: str):
    """Find user by external ID (OAuth provider sub)."""
    result = users_collection.find_one({"external_id": external_id})
    return result


def delete_user(user_id: UUID):
    try:
        query_id = ObjectId(str(user_id))
    except Exception:
        query_id = str(user_id)
    result = users_collection.delete_one({"_id": query_id})
    return result.deleted_count


def find_or_create_user_from_oauth(user_data: CreateUserFromOAuth):

    # First, try to find existing user by external_id
    existing_user = get_user_by_external_id(user_data.external_id)
    print(existing_user)

    if existing_user:
        return mongo_user_doc_to_dict(existing_user)
    else:
        # Create new user with role_id set
        new_user_dict = create_user_from_oauth(user_data)
        print(new_user_dict)
        return new_user_dict


# Role Operations
def get_role_by_name(role_name: str):
    # Prefer new schema field name; fallback to legacy stored alias if present
    role = roles_collection.find_one({"role_name": role_name})
    if role is None:
        role = roles_collection.find_one({"role-name": role_name})
    return role


def get_role_by_id(role_id: str):
    """Get a role document by its _id.

    Handles both ObjectId strings and legacy string ids.
    """
    if not role_id:
        return None
    # Try ObjectId
    role = None
    try:
        role = roles_collection.find_one({"_id": ObjectId(role_id)})
    except Exception:
        # Fallback to legacy string _id
        role = roles_collection.find_one({"_id": role_id})
    return role


def create_role(role: Role):
    roles_collection.insert_one(role_to_dict(role))


def ensure_default_role_and_get_id() -> str:
    """Ensure a default 'user' role exists and return its id as a string."""
    existing = get_role_by_name("user")
    if existing:
        return str(existing["_id"])

    now = datetime.now()
    role = Role(
        role_name="user",
        description="Default role for regular users",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    result = roles_collection.insert_one(role_to_dict(role))
    return str(result.inserted_id)


# Endpoint Access Control CRUD operations
def endpoint_access_to_dict(endpoint_access):
    """Convert EndpointAccess object to dictionary for MongoDB storage."""
    # Exclude None fields; MongoDB will generate _id automatically
    access_dict = endpoint_access.model_dump(exclude_none=True)
    return access_dict


def create_endpoint_access(endpoint_access):
    """Create a new endpoint access control entry."""
    access_dict = endpoint_access_to_dict(endpoint_access)
    result = endpoint_access_collection.insert_one(access_dict)
    return result.inserted_id


def get_endpoint_access_by_role_and_endpoint(role: str, endpoint: str):
    """Get endpoint access control by role and endpoint."""
    return endpoint_access_collection.find_one({"role": role, "endpoint": endpoint})


def get_all_endpoint_access_by_role(role: str):
    """Get all endpoint access controls for a specific role."""
    return list(endpoint_access_collection.find({"role": role}))


def update_endpoint_access(role: str, endpoint: str, access_data):
    """Update endpoint access control."""
    return endpoint_access_collection.update_one({"role": role, "endpoint": endpoint}, {"$set": access_data})


def delete_endpoint_access(role: str, endpoint: str):
    """Delete endpoint access control."""
    return endpoint_access_collection.delete_one({"role": role, "endpoint": endpoint})


def initialize_default_endpoint_access():
    """Initialize default endpoint access controls for all roles."""
    from ..schemas.models import EndpointAccess

    # Define default access patterns
    default_access = [
        # User role access
        {"role": "user", "endpoint": "/dashboard",
            "viewer": True, "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/datastore/browse",
            "viewer": True, "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/datastore/manage",
            "viewer": True, "contributor": True, "admin": False},
        {"role": "user", "endpoint": "/datastore/create",
            "viewer": True, "contributor": True, "admin": False},
        {"role": "user", "endpoint": "/settings", "viewer": True,
            "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/about", "viewer": True,
            "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/support", "viewer": True,
            "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/pipeline", "viewer": True,
            "contributor": False, "admin": False},
        {"role": "user", "endpoint": "/usermanagement",
            "viewer": False, "contributor": False, "admin": False},
        # Admin role access (can access everything except superadmin features)
        {"role": "admin", "endpoint": "/dashboard",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/datastore/browse",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/datastore/manage",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/datastore/create",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/settings",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/about", "viewer": True,
            "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/support",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/pipeline",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "admin", "endpoint": "/usermanagement",
            "viewer": True, "contributor": True, "admin": True},
        # Superadmin role access (can access everything)
        {"role": "superadmin", "endpoint": "/dashboard",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/datastore/browse",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/datastore/manage",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/datastore/create",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/settings",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/about",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/support",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/pipeline",
            "viewer": True, "contributor": True, "admin": True},
        {"role": "superadmin", "endpoint": "/usermanagement",
            "viewer": True, "contributor": True, "admin": True},
    ]

    # Insert default access controls if they don't exist
    for access_data in default_access:
        existing = get_endpoint_access_by_role_and_endpoint(
            access_data["role"], access_data["endpoint"])
        if not existing:
            endpoint_access = EndpointAccess(**access_data)
            create_endpoint_access(endpoint_access)

    return True
