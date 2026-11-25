from sqlalchemy import inspect
from app.db.session import configure_database,init_db
from app.models import Project,ApplicationSettings,ProviderConfiguration

def test_models_and_constraints(tmp_path):
 engine=configure_database(f"sqlite:///{tmp_path/'models.db'}");init_db()
 assert set(inspect(engine).get_table_names())=={'projects','application_settings','provider_configurations','research_sessions','research_sources','claims','claim_sources','fact_check_results','script_documents','script_sections','script_versions','storyboards','storyboard_scenes','narration_segments'}
