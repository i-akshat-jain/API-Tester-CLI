"""
Utility functions
"""

import os
import re
from typing import Any, Dict


def deep_get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get nested dictionary value using dot notation
    
    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "components.securitySchemes")
        default: Default value if path not found
        
    Returns:
        Value at path or default
    """
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1.5s", "250ms")
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    else:
        return f"{seconds:.2f}s"


def expand_env_vars(value: str) -> str:
    """
    Expand environment variables in a string
    
    Supports:
    - $VAR
    - ${VAR}
    - ${VAR:-default}
    
    Args:
        value: String that may contain environment variable references
        
    Returns:
        String with environment variables expanded
    """
    if not isinstance(value, str):
        return value
    
    def replace_env(match):
        var_name = match.group(1)
        default = match.group(2) if match.lastindex >= 2 else None
        
        env_value = os.getenv(var_name)
        if env_value is not None:
            return env_value
        elif default is not None:
            return default
        else:
            # Return original if not found and no default
            return match.group(0)
    
    # Support ${VAR:-default} format
    value = re.sub(r'\$\{([^}:]+)(?::-([^}]*))?\}', replace_env, value)
    # Support $VAR format
    value = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', lambda m: os.getenv(m.group(1), m.group(0)), value)
    
    return value

