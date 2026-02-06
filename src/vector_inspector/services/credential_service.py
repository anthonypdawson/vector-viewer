"""Service for secure credential storage using system keychains."""

import json
from typing import Optional

from vector_inspector.core.logging import log_error, log_info


class CredentialService:
    """Handles secure storage and retrieval of credentials using system keychains.

    Falls back to in-memory storage if keyring is not available (not recommended for production).
    """

    SERVICE_NAME = "vector-inspector"

    def __init__(self):
        """Initialize credential service with keyring if available."""
        self._use_keyring = False
        self._memory_store = {}  # Fallback in-memory storage

        try:
            import keyring

            self._keyring = keyring
            self._use_keyring = True
        except ImportError:
            log_info(
                "Warning: keyring module not available. Credentials will not be persisted securely."
            )
            self._keyring = None

    def store_credentials(self, profile_id: str, credentials: dict) -> bool:
        """
        Store credentials for a profile.

        Args:
            profile_id: Unique profile identifier
            credentials: Dictionary of credential data (api_key, password, etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            credential_key = f"profile:{profile_id}"
            credential_json = json.dumps(credentials)

            if self._use_keyring and self._keyring:
                self._keyring.set_password(self.SERVICE_NAME, credential_key, credential_json)
            else:
                # Fallback to in-memory (not persistent)
                self._memory_store[credential_key] = credential_json

            return True
        except Exception as e:
            log_error("Failed to store credentials: %s", e)
            return False

    def get_credentials(self, profile_id: str) -> Optional[dict]:
        """
        Retrieve credentials for a profile.

        Args:
            profile_id: Unique profile identifier

        Returns:
            Dictionary of credential data, or None if not found
        """
        try:
            credential_key = f"profile:{profile_id}"

            if self._use_keyring and self._keyring:
                credential_json = self._keyring.get_password(self.SERVICE_NAME, credential_key)
            else:
                # Fallback to in-memory
                credential_json = self._memory_store.get(credential_key)

            if credential_json:
                return json.loads(credential_json)
            return None
        except Exception as e:
            log_error("Failed to retrieve credentials: %s", e)
            return None

    def delete_credentials(self, profile_id: str) -> bool:
        """
        Delete stored credentials for a profile.

        Args:
            profile_id: Unique profile identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            credential_key = f"profile:{profile_id}"

            if self._use_keyring:
                try:
                    self._keyring.delete_password(self.SERVICE_NAME, credential_key)
                except self._keyring.errors.PasswordDeleteError:
                    # Credential doesn't exist, that's okay
                    pass
            else:
                # Fallback to in-memory
                self._memory_store.pop(credential_key, None)

            return True
        except Exception as e:
            log_error("Failed to delete credentials: %s", e)
            return False

    def is_keyring_available(self) -> bool:
        """Check if system keyring is available."""
        return self._use_keyring

    def clear_all_credentials(self):
        """Clear all stored credentials. Use with caution!"""
        if not self._use_keyring:
            self._memory_store.clear()
        else:
            # For keyring, we'd need to track all profile IDs
            # This is typically not needed, but can be implemented if required
            log_info("Warning: clear_all_credentials not implemented for keyring backend")
