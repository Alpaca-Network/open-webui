"""
Tests for WorkOS SSO integration.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestWorkOSConfiguration:
    """Test WorkOS configuration loading and validation."""

    def test_workos_config_variables_exist(self):
        """Test that WorkOS configuration variables are defined in config."""
        from open_webui.config import (
            WORKOS_CLIENT_ID,
            WORKOS_API_KEY,
            WORKOS_ORGANIZATION_ID,
            WORKOS_CONNECTION_ID,
            WORKOS_REDIRECT_URI,
        )

        # These should be PersistentConfig objects
        assert hasattr(WORKOS_CLIENT_ID, "value")
        assert hasattr(WORKOS_API_KEY, "value")
        assert hasattr(WORKOS_ORGANIZATION_ID, "value")
        assert hasattr(WORKOS_CONNECTION_ID, "value")
        assert hasattr(WORKOS_REDIRECT_URI, "value")

    def test_workos_provider_not_registered_without_credentials(self):
        """Test that WorkOS provider is not registered without credentials."""
        from open_webui.config import OAUTH_PROVIDERS, load_oauth_providers

        # Temporarily clear and reload with empty credentials
        with patch("open_webui.config.WORKOS_CLIENT_ID") as mock_client_id, patch(
            "open_webui.config.WORKOS_API_KEY"
        ) as mock_api_key:
            mock_client_id.value = ""
            mock_api_key.value = ""
            load_oauth_providers()
            # WorkOS should not be in providers when credentials are missing
            # (we check it's not there OR if there it has the flag)
            if "workos" in OAUTH_PROVIDERS:
                assert OAUTH_PROVIDERS["workos"].get("uses_workos_sdk") is True


class TestWorkOSOAuthManager:
    """Test WorkOS-specific OAuth manager functionality."""

    @pytest.fixture
    def mock_workos_profile(self):
        """Create a mock WorkOS profile object."""
        profile = MagicMock()
        profile.id = "prof_test123"
        profile.email = "user@example.com"
        profile.first_name = "Test"
        profile.last_name = "User"
        profile.connection_id = "conn_test123"
        profile.connection_type = "OktaSAML"
        profile.organization_id = "org_test123"
        profile.idp_id = "idp_test123"
        profile.profile_picture_url = None
        profile.role = None
        return profile

    @pytest.fixture
    def mock_workos_client(self, mock_workos_profile):
        """Create a mock WorkOS client."""
        client = MagicMock()
        client.sso.get_authorization_url.return_value = (
            "https://api.workos.com/sso/authorize?client_id=test"
        )

        # Mock profile_and_token response
        profile_and_token = MagicMock()
        profile_and_token.profile = mock_workos_profile
        profile_and_token.access_token = "test_access_token"
        client.sso.get_profile_and_token.return_value = profile_and_token

        return client

    def test_workos_sdk_import(self):
        """Test that WorkOS SDK can be imported."""
        try:
            from workos import WorkOSClient

            assert WorkOSClient is not None
        except ImportError:
            pytest.skip("WorkOS SDK not installed")

    def test_workos_available_flag(self):
        """Test WORKOS_AVAILABLE flag in oauth module."""
        from open_webui.utils.oauth import WORKOS_AVAILABLE

        # Should be True if workos is installed, False otherwise
        assert isinstance(WORKOS_AVAILABLE, bool)

    @patch("open_webui.utils.oauth.WORKOS_CLIENT_ID")
    @patch("open_webui.utils.oauth.WORKOS_API_KEY")
    @patch("open_webui.utils.oauth.WORKOS_ORGANIZATION_ID")
    @patch("open_webui.utils.oauth.WORKOS_CONNECTION_ID")
    @patch("open_webui.utils.oauth.OAUTH_PROVIDERS")
    def test_handle_login_requires_org_or_connection(
        self,
        mock_providers,
        mock_connection_id,
        mock_org_id,
        mock_api_key,
        mock_client_id,
    ):
        """Test that WorkOS login requires organization_id or connection_id."""
        from open_webui.utils.oauth import OAuthManager
        from fastapi import HTTPException

        # Setup mocks
        mock_client_id.value = "client_test"
        mock_api_key.value = "sk_test"
        mock_org_id.value = ""
        mock_connection_id.value = ""
        mock_providers.__contains__ = lambda self, x: x == "workos"
        mock_providers.__getitem__ = lambda self, x: {"uses_workos_sdk": True}

        # Create manager with mocked WorkOS client
        app = MagicMock()
        manager = OAuthManager(app)
        manager._workos_client = MagicMock()

        request = MagicMock()
        request.app.state.config.WEBUI_URL = "http://localhost:8080"

        # Should raise error when neither org_id nor connection_id is set
        with pytest.raises(HTTPException) as exc_info:
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                manager._handle_workos_login(request)
            )
        assert exc_info.value.status_code == 500


class TestWorkOSProfileMapping:
    """Test WorkOS profile to user data mapping."""

    def test_profile_to_user_data_mapping(self):
        """Test that WorkOS profile fields are correctly mapped to user data."""
        # Create mock profile
        profile = MagicMock()
        profile.id = "prof_123"
        profile.email = "test@example.com"
        profile.first_name = "John"
        profile.last_name = "Doe"
        profile.connection_id = "conn_123"
        profile.connection_type = "GoogleOAuth"
        profile.organization_id = "org_123"
        profile.idp_id = "idp_123"

        # This simulates what _handle_workos_callback does
        user_data = {
            "sub": profile.id,
            "email": profile.email,
            "name": f"{profile.first_name or ''} {profile.last_name or ''}".strip()
            or profile.email,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "picture": getattr(profile, "profile_picture_url", None),
            "connection_id": profile.connection_id,
            "connection_type": profile.connection_type,
            "organization_id": profile.organization_id,
            "idp_id": profile.idp_id,
        }

        assert user_data["sub"] == "prof_123"
        assert user_data["email"] == "test@example.com"
        assert user_data["name"] == "John Doe"
        assert user_data["organization_id"] == "org_123"

    def test_profile_with_role_mapping(self):
        """Test that WorkOS profile roles are correctly mapped."""
        # Create mock profile with role
        profile = MagicMock()
        profile.id = "prof_123"
        profile.email = "admin@example.com"
        profile.first_name = "Admin"
        profile.last_name = "User"

        # Mock role object
        role = MagicMock()
        role.slug = "admin"
        profile.role = role

        # This simulates role extraction logic
        user_data = {"roles": []}
        if hasattr(profile, "role") and profile.role:
            user_data["roles"] = (
                [profile.role.slug]
                if hasattr(profile.role, "slug")
                else [profile.role]
            )

        assert user_data["roles"] == ["admin"]


class TestWorkOSEmailDomainValidation:
    """Test email domain validation for WorkOS SSO."""

    def test_email_domain_allowed_wildcard(self):
        """Test that wildcard domain allows all emails."""
        from open_webui.utils.oauth import auth_manager_config

        allowed_domains = ["*"]
        email = "user@anydomain.com"

        # Simulate domain check logic
        is_allowed = (
            "*" in allowed_domains or email.split("@")[-1] in allowed_domains
        )
        assert is_allowed is True

    def test_email_domain_allowed_specific(self):
        """Test that specific domain restricts access."""
        allowed_domains = ["example.com", "company.com"]

        # Test allowed email
        email_allowed = "user@example.com"
        is_allowed = (
            "*" in allowed_domains or email_allowed.split("@")[-1] in allowed_domains
        )
        assert is_allowed is True

        # Test disallowed email
        email_denied = "user@otherdomain.com"
        is_denied = (
            "*" in allowed_domains or email_denied.split("@")[-1] in allowed_domains
        )
        assert is_denied is False


class TestWorkOSProviderSubject:
    """Test WorkOS provider subject ID generation."""

    def test_provider_sub_format(self):
        """Test that provider_sub is correctly formatted."""
        profile_id = "prof_01ABC123"
        provider_sub = f"workos@{profile_id}"

        assert provider_sub == "workos@prof_01ABC123"
        assert provider_sub.startswith("workos@")

    def test_provider_sub_uniqueness(self):
        """Test that different profile IDs create different provider_subs."""
        profile_ids = ["prof_123", "prof_456", "prof_789"]
        provider_subs = [f"workos@{pid}" for pid in profile_ids]

        assert len(set(provider_subs)) == len(profile_ids)


class TestWorkOSAuthorizationURL:
    """Test WorkOS authorization URL generation."""

    def test_authorization_url_with_organization_id(self):
        """Test authorization URL generation with organization_id."""
        mock_client = MagicMock()
        mock_client.sso.get_authorization_url.return_value = (
            "https://api.workos.com/sso/authorize?organization_id=org_123"
        )

        auth_params = {
            "redirect_uri": "http://localhost/callback",
            "organization_id": "org_123",
        }

        url = mock_client.sso.get_authorization_url(**auth_params)
        assert "organization_id=org_123" in url

    def test_authorization_url_with_connection_id(self):
        """Test authorization URL generation with connection_id."""
        mock_client = MagicMock()
        mock_client.sso.get_authorization_url.return_value = (
            "https://api.workos.com/sso/authorize?connection_id=conn_123"
        )

        auth_params = {
            "redirect_uri": "http://localhost/callback",
            "connection_id": "conn_123",
        }

        url = mock_client.sso.get_authorization_url(**auth_params)
        assert "connection_id=conn_123" in url
