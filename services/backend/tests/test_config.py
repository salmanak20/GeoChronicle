from app.core.config import Settings

def test_config_overrides():
 settings=Settings(database_url="sqlite:///test.db",port=9012)
 assert settings.port==9012 and settings.database_url.endswith("test.db")
