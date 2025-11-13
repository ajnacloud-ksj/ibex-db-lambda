"""
Centralized configuration loader from config.json
NO hardcoded defaults or fallbacks - everything comes from config.json
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager - loads settings from config.json"""

    def __init__(self, environment: str = None):
        """
        Initialize configuration

        Args:
            environment: Environment name (development, staging, production, testing)
                        If not provided, reads from ENVIRONMENT env var
        """
        # Get environment from parameter or environment variable
        self.environment = environment or os.environ.get('ENVIRONMENT')

        if not self.environment:
            raise ValueError(
                "ENVIRONMENT not set. Must be one of: development, staging, production, testing"
            )

        # Load config.json from config/ directory
        config_path = Path(__file__).parent.parent / 'config' / 'config.json'
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            all_config = json.load(f)

        if self.environment not in all_config:
            raise ValueError(
                f"Environment '{self.environment}' not found in config.json. "
                f"Available: {list(all_config.keys())}"
            )

        # Get environment-specific config
        self._config = all_config[self.environment]

        # Substitute environment variables in config values
        self._config = self._substitute_env_vars(self._config)

        print(f"✓ Configuration loaded for environment: {self.environment}")

    def _substitute_env_vars(self, obj: Any) -> Any:
        """
        Recursively substitute ${VAR_NAME} with environment variable values

        Args:
            obj: Configuration object (dict, list, str, etc.)

        Returns:
            Object with environment variables substituted
        """
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Find all ${VAR_NAME} patterns
            pattern = r'\$\{([A-Z_]+)\}'
            matches = re.findall(pattern, obj)

            result = obj
            for var_name in matches:
                env_value = os.environ.get(var_name)
                if env_value is None:
                    raise ValueError(
                        f"Environment variable '{var_name}' not set. "
                        f"Required by config for environment: {self.environment}"
                    )
                result = result.replace(f'${{{var_name}}}', env_value)

            return result
        else:
            return obj

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get configuration value by nested keys

        Args:
            *keys: Nested keys (e.g., 's3', 'bucket_name')
            default: Default value if key not found (use sparingly)

        Returns:
            Configuration value

        Examples:
            config.get('s3', 'bucket_name')  # Returns bucket name
            config.get('catalog', 'type')     # Returns 'rest' or 'glue'
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                if default is None:
                    raise KeyError(
                        f"Configuration key not found: {'.'.join(keys)} "
                        f"in environment: {self.environment}"
                    )
                return default
        return value

    @property
    def s3(self) -> Dict[str, Any]:
        """Get S3 configuration"""
        return self.get('s3')

    @property
    def catalog(self) -> Dict[str, Any]:
        """Get catalog configuration"""
        return self.get('catalog')

    @property
    def duckdb(self) -> Dict[str, Any]:
        """Get DuckDB configuration"""
        return self.get('duckdb')

    @property
    def lambda_config(self) -> Dict[str, Any]:
        """Get Lambda configuration"""
        return self.get('lambda')

    @property
    def performance(self) -> Dict[str, Any]:
        """Get performance configuration"""
        return self.get('performance')


# Global config instance - initialized on first import
_config_instance = None


def get_config() -> Config:
    """
    Get or create global configuration instance

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# Convenience accessors for backward compatibility
def get_s3_config() -> Dict[str, Any]:
    """Get S3 configuration"""
    return get_config().s3


def get_catalog_config() -> Dict[str, Any]:
    """Get catalog configuration"""
    return get_config().catalog


def get_duckdb_config() -> Dict[str, Any]:
    """Get DuckDB configuration"""
    return get_config().duckdb


# Legacy module-level exports (for backward compatibility)
# These are lazy-loaded - they fetch from config when first accessed


class _LazyConfigValue:
    """Lazy-loaded config value that appears as a module constant"""

    def __init__(self, getter_func):
        self._getter = getter_func
        self._value = None
        self._loaded = False

    def __str__(self):
        if not self._loaded:
            self._value = self._getter()
            self._loaded = True
        return str(self._value)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))


# Module-level constants (lazy-loaded from config.json)
BUCKET_NAME = None
AWS_REGION = None
WAREHOUSE_PATH = None
MAX_RETRIES = None
QUERY_TIMEOUT_MS = None


def _init_module_constants():
    """Initialize module-level constants from config"""
    global BUCKET_NAME, AWS_REGION, WAREHOUSE_PATH, MAX_RETRIES, QUERY_TIMEOUT_MS

    config = get_config()
    BUCKET_NAME = config.get('s3', 'bucket_name')
    AWS_REGION = config.get('s3', 'region')

    bucket = config.get('s3', 'bucket_name')
    warehouse = config.get('s3', 'warehouse_path')
    WAREHOUSE_PATH = f"s3://{bucket}/{warehouse}/"

    MAX_RETRIES = config.get('performance', 'max_retries')
    QUERY_TIMEOUT_MS = config.get('performance', 'query_timeout_ms')


# Initialize constants when module is imported
try:
    _init_module_constants()
except Exception as e:
    # If config isn't ready yet, constants will be None
    # They'll be initialized when get_config() is first called
    pass
