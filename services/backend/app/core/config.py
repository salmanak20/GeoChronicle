from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
 model_config=SettingsConfigDict(env_prefix="GEOCHRONICLE_",extra="ignore")
 app_name:str="GeoChronicle"
 database_url:str=""
 auth_token:str=""
 port:int=8765
 search_provider:str="none"
 search_endpoint:str="https://api.tavily.com/search"
 ai_provider:str="none"
 ai_endpoint:str="https://api.openai.com/v1/chat/completions"
 ai_model:str="gpt-4o-mini"
 provider_timeout_seconds:float=30
 narration_words_per_minute:int=145
 def resolved_database_url(self):
  if self.database_url:return self.database_url
  path=Path.home()/"AppData"/"Local"/"GeoChronicle"/"geochronicle.db"
  path.parent.mkdir(parents=True,exist_ok=True)
  return "sqlite:///"+path.as_posix()
settings=Settings()
