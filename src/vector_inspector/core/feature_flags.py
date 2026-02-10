"""Feature flag management for vector-inspector.

This module provides utilities to detect and manage feature flags,
particularly for premium features that are enabled when vector-studio is active.
"""

_advanced_features_enabled = False


def enable_advanced_features():
    """Enable advanced features (called by vector-studio on startup)."""
    global _advanced_features_enabled
    _advanced_features_enabled = True


def are_advanced_features_enabled() -> bool:
    """Check if advanced features are enabled.

    Returns:
        bool: True if vector-studio is active or advanced features were manually enabled.
    """
    global _advanced_features_enabled

    # Check if already enabled
    if _advanced_features_enabled:
        return True

    # Try to detect if vector-studio is installed
    try:
        import vector_studio  # noqa: F401

        return True
    except ImportError:
        return False


def get_feature_tooltip(feature_name: str = "Advanced options") -> str:
    """Get tooltip text for a disabled premium feature.

    Args:
        feature_name: Name of the feature to display in the tooltip.

    Returns:
        str: Tooltip text explaining how to enable the feature.
    """
    return f"{feature_name} available in Vector Studio"
