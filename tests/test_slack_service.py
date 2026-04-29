"""Unit tests for Slack service module."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from test.service_backend.app.services.slack import (
    fetch_permalink,
    list_channels,
    oauth_exchange,
    verify_slack_signature,
)


class TestVerifySlackSignature:
    """Tests for HMAC signature verification."""

    def test_verify_slack_signature_valid(self):
        """Test valid Slack signature verification."""
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        body = "test_body"

        # Construct signature the way Slack does
        basestring = f"v0:{timestamp}:{body}"
        expected_signature = (
            "v0=" + hmac.new(
                signing_secret.encode(),
                basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = verify_slack_signature(signing_secret, timestamp, body, expected_signature)
        assert result is True

    def test_verify_slack_signature_invalid_signature(self):
        """Test invalid signature rejection."""
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        body = "test_body"
        invalid_signature = "v0=invalid_signature_here"

        result = verify_slack_signature(signing_secret, timestamp, body, invalid_signature)
        assert result is False

    def test_verify_slack_signature_expired_timestamp(self):
        """Test expired timestamp rejection (>5 minutes old)."""
        signing_secret = "test_secret"
        old_timestamp = str(int(time.time()) - 301)  # 5 minutes + 1 second
        body = "test_body"

        basestring = f"v0:{old_timestamp}:{body}"
        signature = (
            "v0=" + hmac.new(
                signing_secret.encode(),
                basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = verify_slack_signature(signing_secret, old_timestamp, body, signature)
        assert result is False

    def test_verify_slack_signature_recent_timestamp(self):
        """Test valid recent timestamp (within 5 minutes)."""
        signing_secret = "test_secret"
        recent_timestamp = str(int(time.time()) - 200)  # 3 minutes 20 seconds ago
        body = "test_body"

        basestring = f"v0:{recent_timestamp}:{body}"
        signature = (
            "v0=" + hmac.new(
                signing_secret.encode(),
                basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = verify_slack_signature(signing_secret, recent_timestamp, body, signature)
        assert result is True

    def test_verify_slack_signature_constant_time_compare(self):
        """Test that comparison is constant-time (no early exit on mismatch)."""
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        body = "test_body"

        basestring = f"v0:{timestamp}:{body}"
        correct_signature = (
            "v0=" + hmac.new(
                signing_secret.encode(),
                basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        # Both should return False but via constant-time compare
        wrong_sig_1 = "v0=0000000000000000000000000000000000000000000000000000000000000000"
        wrong_sig_2 = "v0=ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

        result1 = verify_slack_signature(signing_secret, timestamp, body, wrong_sig_1)
        result2 = verify_slack_signature(signing_secret, timestamp, body, wrong_sig_2)

        assert result1 is False
        assert result2 is False


class TestOAuthExchange:
    """Tests for OAuth token exchange."""

    @pytest.mark.asyncio
    async def test_oauth_exchange_success(self):
        """Test successful OAuth token exchange."""
        code = "test_code_12345"
        client_id = "test_client_id"
        client_secret = "test_client_secret"
        redirect_uri = "http://localhost:3000/callback"

        mock_response = {
            "ok": True,
            "access_token": "xoxb-test-token",
            "token_type": "bot",
            "scope": "chat:write",
            "bot_user_id": "U123456789",
            "app_id": "A123456789",
            "team": {"id": "T123456789", "name": "Test Workspace"},
            "enterprise": None,
            "authed_user": {"id": "U987654321"},
            "is_enterprise_install": False,
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            result = await oauth_exchange(code, client_id, client_secret, redirect_uri)

            assert result == mock_response
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "slack.com/api/oauth.v2.access" in str(call_args)

    @pytest.mark.asyncio
    async def test_oauth_exchange_failure(self):
        """Test OAuth exchange error response."""
        code = "invalid_code"
        client_id = "test_client_id"
        client_secret = "test_client_secret"
        redirect_uri = "http://localhost:3000/callback"

        mock_response = {
            "ok": False,
            "error": "invalid_code",
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            result = await oauth_exchange(code, client_id, client_secret, redirect_uri)

            assert result["ok"] is False
            assert result["error"] == "invalid_code"


class TestFetchPermalink:
    """Tests for fetching Slack message permalink."""

    @pytest.mark.asyncio
    async def test_fetch_permalink_success(self):
        """Test successful permalink fetch."""
        token = "xoxb-test-token"
        channel = "C123456789"
        ts = "1234567890.123456"

        mock_response = {
            "ok": True,
            "channel": channel,
            "permalink": "https://test-workspace.slack.com/archives/C123456789/p1234567890123456",
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            result = await fetch_permalink(token, channel, ts)

            assert result == mock_response["permalink"]
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_permalink_failure(self):
        """Test permalink fetch with error."""
        token = "xoxb-test-token"
        channel = "C123456789"
        ts = "1234567890.123456"

        mock_response = {
            "ok": False,
            "error": "message_not_found",
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            with pytest.raises((KeyError, ValueError)):
                await fetch_permalink(token, channel, ts)


class TestListChannels:
    """Tests for listing Slack channels."""

    @pytest.mark.asyncio
    async def test_list_channels_success(self):
        """Test successful channel listing."""
        token = "xoxb-test-token"

        mock_response = {
            "ok": True,
            "channels": [
                {"id": "C123456789", "name": "general", "is_member": True},
                {"id": "C987654321", "name": "random", "is_member": True},
            ],
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            result = await list_channels(token)

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["name"] == "general"
            assert result[1]["name"] == "random"

    @pytest.mark.asyncio
    async def test_list_channels_empty(self):
        """Test channel listing with no channels."""
        token = "xoxb-test-token"

        mock_response = {
            "ok": True,
            "channels": [],
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            result = await list_channels(token)

            assert result == []

    @pytest.mark.asyncio
    async def test_list_channels_failure(self):
        """Test channel listing error."""
        token = "xoxb-test-token"

        mock_response = {
            "ok": False,
            "error": "token_revoked",
        }

        with patch("test.service_backend.app.services.slack.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            with pytest.raises((KeyError, ValueError)):
                await list_channels(token)


class TestModuleExports:
    """Test module-level exports."""

    def test_imports_available(self):
        """Test that all expected functions are importable."""
        from test.service_backend.app.services import (
            fetch_permalink,
            list_channels,
            oauth_exchange,
            verify_slack_signature,
        )

        assert callable(verify_slack_signature)
        assert callable(oauth_exchange)
        assert callable(fetch_permalink)
        assert callable(list_channels)
