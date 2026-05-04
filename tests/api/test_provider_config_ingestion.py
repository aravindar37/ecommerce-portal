import os

from tests.helpers.test_client import admin_client, chat_client, expect_ok, search_client


def test_all_three_fastapi_services_report_health() -> None:
    core_health = expect_ok(admin_client().get("/api/health"))
    search_health = expect_ok(search_client().get("/api/health"))
    chat_health = expect_ok(chat_client().get("/api/health"))

    assert core_health["service"] == "core"
    assert search_health["service"] == "search"
    assert chat_health["service"] == "chat"
    assert core_health["backend"]["framework"] == "fastapi"
    assert search_health["backend"]["framework"] == "fastapi"
    assert chat_health["backend"]["framework"] == "fastapi"


def test_admin_config_exposes_provider_choices_without_secrets() -> None:
    config = expect_ok(admin_client().get("/api/admin/config"))

    assert config["services"]["core"]["runtime"] == "python"
    assert config["services"]["core"]["framework"] == "fastapi"
    assert config["services"]["search"]["framework"] == "fastapi"
    assert config["services"]["chat"]["framework"] == "fastapi"
    assert config["llm"]["provider"] == os.getenv("EXPECTED_LLM_PROVIDER", "openai")
    assert config["llm"]["model"] == os.getenv("EXPECTED_LLM_MODEL", "gpt-5.4")
    assert config["embedding"]["provider"] == os.getenv("EXPECTED_EMBEDDING_PROVIDER", "ollama")
    assert config["embedding"]["model"] == os.getenv("EXPECTED_EMBEDDING_MODEL", "nomic-embed-text:v1.5")
    assert config["embedding"]["dimensions"] == int(os.getenv("EXPECTED_EMBEDDING_DIMENSIONS", "768"))
    assert config["imageStorage"]["provider"] == os.getenv("EXPECTED_IMAGE_STORAGE", "local_filesystem")
    assert config["checkout"]["currency"] == "INR"
    assert config["auth"]["googleEnabled"] is False
    assert config["codexMcp"]["enabled"] is True
    assert config["admin"]["seedUserConfigured"] is True
    assert config["serviceBoundaries"]["searchOwnsProductSearch"] is True
    assert config["serviceBoundaries"]["chatUsesCoreAndSearchApis"] is True

    serialized = str(config).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
    assert "password" not in serialized
    assert "token" not in serialized


def test_ingestion_status_reports_kaggle_dataset_local_filesystem_and_embeddings() -> None:
    status = expect_ok(admin_client().get("/api/admin/ingestion/status"))

    assert status["datasetName"] == "kaggle-fashion-product-images"
    assert int(status["productsImported"]) > 0
    assert int(status["embeddingsGenerated"]) > 0
    assert status["imageStorage"] == "local_filesystem"
    assert status["datasetPath"].endswith("dataset")
    assert status["stylesCsvRows"] == 44446
    assert status["imagesCsvRows"] == 44446
    assert status["jsonMetadataFiles"] == 44446
    assert status["localImageFiles"] == 44441
    assert set(status["missingLocalImageIds"]) == {"12347", "39401", "39403", "39410", "39425"}
    assert status["imageLocalRoot"].endswith("dataset/images")
    assert status.get("s3Enabled") is False


def test_embedding_index_metadata_matches_configured_provider_model_dimensions_and_template() -> None:
    status = expect_ok(admin_client().get("/api/admin/ingestion/status"))
    embedding = status["embedding"]

    assert embedding["provider"] == os.getenv("EXPECTED_EMBEDDING_PROVIDER", "ollama")
    assert embedding["model"] == os.getenv("EXPECTED_EMBEDDING_MODEL", "nomic-embed-text:v1.5")
    assert embedding["dimensions"] == int(os.getenv("EXPECTED_EMBEDDING_DIMENSIONS", "768"))
    assert embedding["textTemplateVersion"] == "product-v1"
    assert embedding["vectorIndexName"]
