"""
Enterprise Intelligence Platform Configuration

Centralized configuration management for EIP.
"""

from typing import Any, Dict, Optional
import frappe

from .constants import DEFAULT_CONFIG


class EIPConfig:
    """
    Centralized configuration management for Enterprise Intelligence Platform.
    
    Loads configuration from multiple sources in priority order:
    1. Environment variables
    2. Site config (frappe.conf.json)
    3. Database (Assistant Core Settings DocType)
    4. Built-in defaults
    """

    _instance = None
    _config_cache = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize configuration"""
        if self._config_cache is None:
            self._load_config()

    def _load_config(self) -> None:
        """Load and merge configuration from all sources."""
        self._config_cache = DEFAULT_CONFIG.copy()
        self._load_from_environment()
        self._load_from_site_config()
        self._load_from_database()

    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        import os

        env_config = {}
        for key, value in os.environ.items():
            if key.startswith("EIP_"):
                config_key = key[4:].lower()
                env_config[config_key] = self._parse_env_value(value)

        self._config_cache.update(env_config)

    def _load_from_site_config(self) -> None:
        """Load configuration from Frappe site config."""
        try:
            if hasattr(frappe, "conf"):
                eip_config = frappe.conf.get("eip", {})
                if isinstance(eip_config, dict):
                    self._config_cache.update(eip_config)
        except Exception as e:
            frappe.logger().warning(f"Failed to load site config: {e}")

    def _load_from_database(self) -> None:
        """Load configuration from database."""
        try:
            if frappe.db.exists("Assistant Core Settings", {"name": "EIP Configuration"}):
                doc = frappe.get_doc("Assistant Core Settings", "EIP Configuration")
                if hasattr(doc, "configuration") and doc.configuration:
                    import json
                    db_config = json.loads(doc.configuration)
                    self._config_cache.update(db_config)
        except Exception as e:
            frappe.logger().warning(f"Failed to load database config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        if "." in key:
            keys = key.split(".")
            value = self._config_cache
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
            return value if value is not None else default
        else:
            return self._config_cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config_cache[key] = value
        frappe.logger().debug(f"EIP Config set: {key} = {value}")

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration."""
        return self._config_cache.copy()

    def reload(self) -> None:
        """Reload configuration from all sources."""
        self._config_cache = None
        self._load_config()

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False

        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        return value


# Global config instance
config = EIPConfig()
