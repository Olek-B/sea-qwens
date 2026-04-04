import pytest
import tempfile
from pathlib import Path
from scripts.installer.qwen_profiles import (
    scan_qwen_accounts,
    get_profile_display_name,
    check_oauth_status,
    ProfileInfo,
)


class TestGetProfileDisplayName:
    def test_simple_title_case(self):
        assert get_profile_display_name("adalovelace") == "Ada Lovelace"

    def test_known_name_mitchel(self):
        assert get_profile_display_name("mitchelbaker") == "Mitchel"

    def test_single_word(self):
        assert get_profile_display_name("turing") == "Turing"

    def test_already_spaced(self):
        assert get_profile_display_name("Twoja Stara") == "Twoja Stara"


class TestCheckOauthStatus:
    def test_oauth_active(self, tmp_path):
        profile_dir = tmp_path / "testprofile"
        profile_dir.mkdir()
        (profile_dir / "oauth_creds.json").write_text("{}")
        assert check_oauth_status(profile_dir) is True

    def test_oauth_missing(self, tmp_path):
        profile_dir = tmp_path / "testprofile"
        profile_dir.mkdir()
        assert check_oauth_status(profile_dir) is False


class TestScanQwenAccounts:
    def test_no_accounts_dir(self, monkeypatch):
        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", "/nonexistent/path")
        result = scan_qwen_accounts()
        assert result == []

    def test_finds_profiles(self, tmp_path, monkeypatch):
        # Create fake accounts
        ada = tmp_path / "adalovelace"
        ada.mkdir()
        (ada / "oauth_creds.json").write_text("{}")

        turing = tmp_path / "turing"
        turing.mkdir()
        # No oauth file

        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", str(tmp_path))
        result = scan_qwen_accounts()

        assert len(result) == 2
        assert result[0].name == "adalovelace"
        assert result[0].display_name == "Ada Lovelace"
        assert result[0].oauth_active is True
        assert result[1].name == "turing"
        assert result[1].oauth_active is False

    def test_empty_accounts_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QWEN_ACCOUNTS_DIR", str(tmp_path))
        result = scan_qwen_accounts()
        assert result == []
