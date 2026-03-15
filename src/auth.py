"""
IbexDB API Key Authentication & Authorization

Validates API keys, enforces tenant scoping, and provides row-level policy context.

Key registry loaded from config/api_keys.json (with env var substitution).
Controlled by IBEX_AUTH_ENABLED env var — when "false", auth is skipped.

Security layers:
  1. API key validation — reject unknown/disabled keys
  2. Tenant scoping — key can only access its allowed tenant_ids
  3. Permission enforcement — read_only keys cannot write/update/delete
  4. Row-level policy — provides user_id context for scoped queries
"""

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Key Registry (loaded once, cached) ───────────────────────────────────────

_key_registry: Optional[Dict[str, Dict]] = None
_auth_enabled: Optional[bool] = None


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    pattern = r'\$\{([A-Z_]+)\}'
    def replacer(match):
        var = match.group(1)
        return os.environ.get(var, '')
    return re.sub(pattern, replacer, value)


def _load_registry() -> Tuple[bool, Dict[str, Dict]]:
    """Load API key registry from config file. Returns (auth_enabled, key_map)."""
    global _key_registry, _auth_enabled
    if _key_registry is not None:
        return _auth_enabled, _key_registry

    # Check env override first — env var takes priority over config file
    env_auth = os.environ.get('IBEX_AUTH_ENABLED', '').lower()
    if env_auth == 'false':
        _auth_enabled = False
        _key_registry = {}
        print("Auth: Disabled via IBEX_AUTH_ENABLED=false")
        return _auth_enabled, _key_registry
    env_force_enabled = env_auth == 'true'

    config_path = Path(__file__).parent.parent / 'config' / 'api_keys.json'
    if not config_path.exists():
        print(f"Auth: No api_keys.json found at {config_path} — auth disabled")
        _auth_enabled = False
        _key_registry = {}
        return _auth_enabled, _key_registry

    try:
        with open(config_path) as f:
            config = json.load(f)

        _auth_enabled = env_force_enabled or config.get('auth_enabled', False)
        _key_registry = {}

        for entry in config.get('keys', []):
            if not entry.get('enabled', True):
                continue
            # Resolve env vars in the key value
            resolved_key = _substitute_env_vars(entry.get('key', ''))
            if not resolved_key:
                continue
            _key_registry[resolved_key] = {
                'key_id': entry.get('key_id', 'unknown'),
                'description': entry.get('description', ''),
                'tenant_ids': entry.get('tenant_ids', []),
                'permissions': entry.get('permissions', 'read_write'),
                'row_policy': entry.get('row_policy'),
            }

        print(f"Auth: Loaded {len(_key_registry)} API key(s), auth_enabled={_auth_enabled}")
        return _auth_enabled, _key_registry

    except Exception as e:
        print(f"Auth: Failed to load api_keys.json: {e} — auth disabled")
        _auth_enabled = False
        _key_registry = {}
        return _auth_enabled, _key_registry


# ── Auth Context ─────────────────────────────────────────────────────────────

class AuthContext:
    """Encapsulates the authenticated caller's permissions and context."""

    def __init__(
        self,
        authenticated: bool = False,
        key_id: str = '__none__',
        tenant_ids: List[str] = None,
        permissions: str = 'read_write',
        row_policy: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ):
        self.authenticated = authenticated
        self.key_id = key_id
        self.tenant_ids = tenant_ids or []
        self.permissions = permissions
        self.row_policy = row_policy
        self.user_id = user_id

    def can_access_tenant(self, tenant_id: str) -> bool:
        """Check if this key is allowed to access the given tenant_id."""
        if '*' in self.tenant_ids:
            return True
        return tenant_id in self.tenant_ids

    def is_read_only(self) -> bool:
        return self.permissions == 'read_only'

    def is_write_operation(self, operation: str) -> bool:
        """Check if the operation is a write/mutating operation."""
        write_ops = {
            'WRITE', 'UPDATE', 'DELETE', 'HARD_DELETE', 'UPSERT',
            'CREATE_TABLE', 'DROP_TABLE', 'DROP_NAMESPACE', 'COMPACT',
            'VECTOR_WRITE', 'VECTOR_INDEX',
        }
        return operation.upper() in write_ops

    def get_row_filter_column(self) -> Optional[str]:
        """Get the column name for row-level filtering, if policy is set."""
        if self.row_policy and self.user_id:
            return self.row_policy.get('column')
        return None

    def get_row_filter_value(self) -> Optional[str]:
        """Get the value to filter by (user_id from request context)."""
        return self.user_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key_id': self.key_id,
            'tenant_ids': self.tenant_ids,
            'permissions': self.permissions,
            'has_row_policy': self.row_policy is not None,
            'user_id': self.user_id,
        }


# ── Public API ───────────────────────────────────────────────────────────────

def authenticate(event: Dict[str, Any], request_data: Dict[str, Any] = None) -> AuthContext:
    """
    Authenticate a request and return an AuthContext.

    Extracts API key from:
      1. x-api-key header (HTTP requests)
      2. api_key field in request body (direct Lambda invocation)

    Extracts user_id context from:
      1. user_id field in request body (for row-level policies)

    Returns AuthContext with permissions and constraints.
    """
    auth_enabled, registry = _load_registry()

    if not auth_enabled:
        return AuthContext(
            authenticated=True,
            key_id='__auth_disabled__',
            tenant_ids=['*'],
            permissions='read_write',
        )

    # Extract API key from headers or body
    api_key = None

    # HTTP headers (API Gateway / Function URL)
    headers = event.get('headers') or {}
    api_key = (
        headers.get('x-api-key')
        or headers.get('X-API-Key')
        or headers.get('X-Api-Key')
    )

    # Query string parameter
    if not api_key:
        qsp = event.get('queryStringParameters') or {}
        api_key = qsp.get('api_key')

    # Direct Lambda invocation — key in body
    if not api_key and request_data:
        api_key = request_data.get('api_key')

    if not api_key:
        return AuthContext(authenticated=False)

    # Look up key
    entry = registry.get(api_key)
    if not entry:
        return AuthContext(authenticated=False)

    # Extract user_id from request context (for row-level policies)
    user_id = None
    if request_data:
        user_id = request_data.get('user_id') or request_data.get('user_context', {}).get('user_id')

    return AuthContext(
        authenticated=True,
        key_id=entry['key_id'],
        tenant_ids=entry['tenant_ids'],
        permissions=entry['permissions'],
        row_policy=entry.get('row_policy'),
        user_id=user_id,
    )


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(32)
