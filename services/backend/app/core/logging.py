import json,logging
class JsonFormatter(logging.Formatter):
 def format(self,r):return json.dumps({"level":r.levelname,"logger":r.name,"message":r.getMessage()})
def configure_logging():
 h=logging.StreamHandler();h.setFormatter(JsonFormatter());logging.basicConfig(level=logging.INFO,handlers=[h],force=True)
