from alembic import context
from ta_backend import models  # noqa: F401
from ta_backend.config import PROJECT_ROOT, Settings
from ta_backend.db import Base, make_engine

settings = Settings.from_env()

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    (PROJECT_ROOT / "data/runtime").mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=settings.database_url.startswith("sqlite:"),
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
