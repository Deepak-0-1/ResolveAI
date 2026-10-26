from resolveai_common.settings import Settings


def test_cors_origins_parsed() -> None:
    settings = Settings(api_cors_origins="http://a, http://b")
    assert settings.cors_origins == ["http://a", "http://b"]


def test_qdrant_url() -> None:
    settings = Settings(qdrant_host="qdrant", qdrant_port=6333)
    assert settings.qdrant_url == "http://qdrant:6333"


def test_log_level_normalized() -> None:
    settings = Settings(log_level="debug")
    assert settings.log_level == "DEBUG"
