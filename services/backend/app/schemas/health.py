from pydantic import BaseModel
class HealthResponse(BaseModel):status:str;application:str;api_version:str;database:str
