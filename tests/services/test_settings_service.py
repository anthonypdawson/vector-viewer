import json
from pathlib import Path

import pytest

from vector_inspector.services.settings_service import SettingsService


@pytest.fixture()
def temp_home(tmp_path):
    # Monkeypatch Path.home() to point to a temporary directory for isolation
    original_home = Path.home
    Path.home = lambda: tmp_path  # type: ignore
    try:
        yield tmp_path
    finally:
        Path.home = original_home  # restore


def test_last_connection_roundtrip(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()
    assert svc.get_last_connection() is None

    config = {
        "provider": "chromadb",
        "connection_type": "persistent",
        "path": "./data/chroma_db",
    }
    svc.save_last_connection(config)

    # Create a new service to ensure it reads from disk
    svc2 = SettingsService()
    assert svc2.get_last_connection() == config

    # Validate file exists with expected content
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["last_connection"] == config


def test_set_get_and_clear(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()

    assert svc.get("theme", "light") == "light"
    svc.set("theme", "dark")
    assert svc.get("theme") == "dark"

    # Ensure persisted
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"

    # Clear and verify
    svc.clear()
    assert svc.get("theme") is None

    # File should reflect cleared settings (no 'theme' key)
    data2 = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "theme" not in data2


def test_missing_settings_file(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()
    # Remove file if exists
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    if settings_file.exists():
        settings_file.unlink()
    svc._load_settings()
    # Should not contain user keys, but may have defaults
    assert "theme" not in svc.settings or svc.settings["theme"] == "light"


def test_invalid_json_file(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text("{ invalid json }", encoding="utf-8")
    svc = SettingsService()
    # Should fallback to defaults, not user keys
    assert "theme" not in svc.settings or svc.settings["theme"] == "light"


def test_overwrite_key(temp_home):
    svc = SettingsService()
    svc.set("theme", "light")
    svc.set("theme", "dark")
    assert svc.get("theme") == "dark"


def test_highlight_defaults_and_setters(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()

    # Should return an rgba string
    hc = svc.get_highlight_color()
    assert isinstance(hc, str) and hc.startswith("rgba(")

    # Set highlight values and persist
    svc.set_highlight_color("rgba(5,6,7,1)")
    svc.set_highlight_color_bg("rgba(5,6,7,0.05)")

    # Recreate to ensure persisted
    svc2 = SettingsService()
    assert svc2.get_highlight_color() == "rgba(5,6,7,1)"
    assert svc2.get_highlight_color_bg() == "rgba(5,6,7,0.05)"


def test_unicode_and_large_value(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()
    unicode_val = "你好, мир, hello!"
    large_val = "x" * 10000
    svc.set("greeting", unicode_val)
    svc.set("blob", large_val)
    assert svc.get("greeting") == unicode_val
    assert svc.get("blob") == large_val
    # Validate persistence
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["greeting"] == unicode_val
    assert data["blob"] == large_val


# ---------------------------------------------------------------------------
# Helper to create a fresh isolated SettingsService
# ---------------------------------------------------------------------------


def _fresh(temp_home) -> "SettingsService":
    SettingsService._instance = None  # type: ignore[attr-defined]
    SettingsService._initialized = False  # type: ignore[attr-defined]
    return SettingsService()


# ---------------------------------------------------------------------------
# _save_settings exception path
# ---------------------------------------------------------------------------


def test_save_settings_exception_silenced(temp_home):
    """_save_settings logs error but does not raise when write fails."""
    svc = _fresh(temp_home)
    # Make the settings_file into a directory so open() fails
    svc.settings_file.parent.mkdir(parents=True, exist_ok=True)
    svc.settings_file.mkdir(parents=True, exist_ok=True)
    # This should not raise even though the file write fails
    svc._save_settings()


# ---------------------------------------------------------------------------
# Breadcrumb / search settings
# ---------------------------------------------------------------------------


def test_set_breadcrumb_enabled(temp_home):
    svc = _fresh(temp_home)
    svc.set_breadcrumb_enabled(True)
    assert svc.get("breadcrumb.enabled") is True
    svc.set_breadcrumb_enabled(False)
    assert svc.get("breadcrumb.enabled") is False


def test_set_breadcrumb_elide_mode_valid(temp_home):
    svc = _fresh(temp_home)
    svc.set_breadcrumb_elide_mode("middle")
    assert svc.get("breadcrumb.elide_mode") == "middle"


def test_set_breadcrumb_elide_mode_invalid_defaults_to_left(temp_home):
    """Invalid mode value is silently corrected to 'left'."""
    svc = _fresh(temp_home)
    svc.set_breadcrumb_elide_mode("invalid")
    assert svc.get("breadcrumb.elide_mode") == "left"


def test_set_default_n_results(temp_home):
    svc = _fresh(temp_home)
    svc.set_default_n_results(25)
    assert svc.get("search.default_n_results") == 25


# ---------------------------------------------------------------------------
# Embeddings auto-generate
# ---------------------------------------------------------------------------


def test_auto_generate_embeddings_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_auto_generate_embeddings() is True


def test_set_get_auto_generate_embeddings(temp_home):
    svc = _fresh(temp_home)
    svc.set_auto_generate_embeddings(False)
    assert svc.get_auto_generate_embeddings() is False


# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------


def test_set_window_restore_geometry(temp_home):
    svc = _fresh(temp_home)
    svc.set_window_restore_geometry(False)
    assert svc.get_window_restore_geometry() is False


def test_set_window_geometry_with_bytes(temp_home):
    svc = _fresh(temp_home)
    svc.set_window_geometry(b"hello")
    assert svc.get_window_geometry() == b"hello"


def test_set_window_geometry_with_string_b64(temp_home):
    """String input is stored as-is (already base64)."""
    import base64

    svc = _fresh(temp_home)
    b64 = base64.b64encode(b"test-geom").decode("ascii")
    svc.set_window_geometry(b64)
    assert svc.get_window_geometry() == b"test-geom"


def test_set_window_geometry_exception_silenced(temp_home):
    """set_window_geometry with un-encodable input is silenced."""
    svc = _fresh(temp_home)
    # Pass None to trigger a TypeError inside the try block — should not raise
    svc.set_window_geometry(None)  # type: ignore[arg-type]


def test_get_window_geometry_invalid_b64_returns_none(temp_home):
    """get_window_geometry returns None when stored b64 is invalid."""
    svc = _fresh(temp_home)
    svc.settings["window.geometry"] = "!!! not valid base64 !!!"
    result = svc.get_window_geometry()
    assert result is None


# ---------------------------------------------------------------------------
# Cache / telemetry
# ---------------------------------------------------------------------------


def test_set_get_cache_enabled(temp_home):
    svc = _fresh(temp_home)
    svc.set_cache_enabled(False)
    assert svc.get_cache_enabled() is False
    svc.set_cache_enabled(True)
    assert svc.get_cache_enabled() is True


def test_get_telemetry_enabled_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_telemetry_enabled() is True


def test_set_get_telemetry_enabled(temp_home):
    svc = _fresh(temp_home)
    svc.set_telemetry_enabled(False)
    assert svc.get_telemetry_enabled() is False


# ---------------------------------------------------------------------------
# set() signal emit — lines 174-175 are triggered when emit raises but caught
# We cover them by making the signal's connected slot throw, captured via pytest-qt.
# Skipped here since Qt's exception handling conflicts with pytest-qt's reporter.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# save_embedding_model / get / remove
# ---------------------------------------------------------------------------


def test_save_and_get_embedding_model(temp_home):
    svc = _fresh(temp_home)
    svc.save_embedding_model("profile1", "col1", "all-MiniLM-L6-v2", "sentence-transformer")
    result = svc.get_embedding_model("profile1", "col1")
    assert result is not None
    assert result["model"] == "all-MiniLM-L6-v2"
    assert result["type"] == "sentence-transformer"
    assert "timestamp" in result


def test_get_embedding_model_not_set_returns_none(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_embedding_model("p", "c") is None


def test_remove_embedding_model(temp_home):
    svc = _fresh(temp_home)
    svc.save_embedding_model("profile1", "col1", "model-x")
    svc.remove_embedding_model("profile1", "col1")
    assert svc.get_embedding_model("profile1", "col1") is None


def test_remove_embedding_model_no_key_exists(temp_home):
    """remove_embedding_model with no 'collection_embedding_models' key doesn't crash."""
    svc = _fresh(temp_home)
    svc.remove_embedding_model("profile1", "col_missing")  # should not raise


# ---------------------------------------------------------------------------
# remove_profile_settings
# ---------------------------------------------------------------------------


def test_remove_profile_settings(temp_home):
    svc = _fresh(temp_home)
    svc.save_embedding_model("my-profile", "col1", "model-a")
    svc.save_embedding_model("my-profile", "col2", "model-b")
    svc.save_embedding_model("other", "col3", "model-c")
    svc.remove_profile_settings("my-profile")
    assert svc.get_embedding_model("my-profile", "col1") is None
    assert svc.get_embedding_model("my-profile", "col2") is None
    assert svc.get_embedding_model("other", "col3") is not None


def test_remove_profile_settings_no_key(temp_home):
    """remove_profile_settings is safe when no embedding models key exists."""
    svc = _fresh(temp_home)
    svc.remove_profile_settings("p")  # should not raise


# ---------------------------------------------------------------------------
# add_custom_embedding_model / get / remove
# ---------------------------------------------------------------------------


def test_add_and_get_custom_embedding_model(temp_home):
    svc = _fresh(temp_home)
    svc.add_custom_embedding_model("my-model", 768, "sentence-transformer", "A custom model")
    models = svc.get_custom_embedding_models()
    assert len(models) == 1
    assert models[0]["name"] == "my-model"
    assert models[0]["dimension"] == 768


def test_add_custom_embedding_model_updates_existing(temp_home):
    """Adding a model with same name+dimension updates rather than duplicates."""
    svc = _fresh(temp_home)
    svc.add_custom_embedding_model("my-model", 768, "sentence-transformer", "v1")
    svc.add_custom_embedding_model("my-model", 768, "sentence-transformer", "v2")
    models = svc.get_custom_embedding_models()
    assert len(models) == 1
    assert models[0]["description"] == "v2"


def test_get_custom_embedding_models_filtered_by_dimension(temp_home):
    svc = _fresh(temp_home)
    svc.add_custom_embedding_model("model-384", 384, "sentence-transformer", "A")
    svc.add_custom_embedding_model("model-768", 768, "sentence-transformer", "B")
    models_384 = svc.get_custom_embedding_models(dimension=384)
    assert len(models_384) == 1
    assert models_384[0]["name"] == "model-384"


def test_remove_custom_embedding_model(temp_home):
    svc = _fresh(temp_home)
    svc.add_custom_embedding_model("my-model", 512, "sentence-transformer", "X")
    svc.remove_custom_embedding_model("my-model", 512)
    assert svc.get_custom_embedding_models() == []


def test_remove_custom_embedding_model_no_key(temp_home):
    """remove_custom_embedding_model is safe when no custom_embedding_models key."""
    svc = _fresh(temp_home)
    svc.remove_custom_embedding_model("nonexistent", 512)  # should not raise


# ---------------------------------------------------------------------------
# Embedding cache settings
# ---------------------------------------------------------------------------


def test_get_embedding_cache_enabled_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_embedding_cache_enabled() is True


def test_set_get_embedding_cache_enabled(temp_home):
    svc = _fresh(temp_home)
    svc.set_embedding_cache_enabled(False)
    assert svc.get_embedding_cache_enabled() is False


def test_get_embedding_cache_dir_default_none(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_embedding_cache_dir() is None


def test_set_get_embedding_cache_dir(temp_home):
    svc = _fresh(temp_home)
    svc.set_embedding_cache_dir("/custom/path")
    assert svc.get_embedding_cache_dir() == "/custom/path"


def test_set_embedding_cache_dir_none_removes_key(temp_home):
    """set_embedding_cache_dir(None) removes the key."""
    svc = _fresh(temp_home)
    svc.set_embedding_cache_dir("/some/path")
    svc.set_embedding_cache_dir(None)
    assert svc.get_embedding_cache_dir() is None


# ---------------------------------------------------------------------------
# get_highlight_color_bg without a stored value
# ---------------------------------------------------------------------------


def test_get_highlight_color_bg_default_fallback(temp_home):
    """get_highlight_color_bg returns fallback when no value stored."""
    svc = _fresh(temp_home)
    # No value set → falls through to HIGHLIGHT_COLOR_BG import or hard-coded default
    result = svc.get_highlight_color_bg()
    assert isinstance(result, str)
    assert "rgba" in result


# ---------------------------------------------------------------------------
# get_use_accent_enabled / set_use_accent_enabled
# ---------------------------------------------------------------------------


def test_get_use_accent_enabled_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_use_accent_enabled() is False


def test_set_get_use_accent_enabled(temp_home):
    svc = _fresh(temp_home)
    svc.set_use_accent_enabled(True)
    assert svc.get_use_accent_enabled() is True


# ---------------------------------------------------------------------------
# Item 13 — LLM provider settings getters / setters
# ---------------------------------------------------------------------------


def test_llm_provider_default_is_auto(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_provider() == "auto"


def test_llm_provider_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_provider("ollama")
    assert svc.get_llm_provider() == "ollama"


def test_llm_model_path_default_empty(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_model_path() == ""


def test_llm_model_path_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_model_path("/models/phi3.gguf")
    assert svc.get_llm_model_path() == "/models/phi3.gguf"


def test_llm_ollama_url_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_ollama_url() == "http://localhost:11434"


def test_llm_ollama_url_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_ollama_url("http://192.168.1.10:11434")
    assert svc.get_llm_ollama_url() == "http://192.168.1.10:11434"


def test_llm_ollama_model_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_ollama_model() == "llama3.2"


def test_llm_ollama_model_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_ollama_model("mistral")
    assert svc.get_llm_ollama_model() == "mistral"


def test_llm_openai_url_default_empty(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_openai_url() == ""


def test_llm_openai_url_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_openai_url("https://api.openai.com/v1")
    assert svc.get_llm_openai_url() == "https://api.openai.com/v1"


def test_llm_openai_api_key_default_empty(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_openai_api_key() == ""


def test_llm_openai_api_key_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_openai_api_key("sk-test-1234")
    assert svc.get_llm_openai_api_key() == "sk-test-1234"


def test_llm_openai_model_default_empty(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_openai_model() == ""


def test_llm_openai_model_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_openai_model("gpt-4o-mini")
    assert svc.get_llm_openai_model() == "gpt-4o-mini"


def test_llm_context_length_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_context_length() == 4096


def test_llm_context_length_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_context_length(8192)
    assert svc.get_llm_context_length() == 8192


def test_llm_temperature_default(temp_home):
    svc = _fresh(temp_home)
    assert svc.get_llm_temperature() == pytest.approx(0.1)


def test_llm_temperature_roundtrip(temp_home):
    svc = _fresh(temp_home)
    svc.set_llm_temperature(0.7)
    assert svc.get_llm_temperature() == pytest.approx(0.7)
