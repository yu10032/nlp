import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from ta_backend.config import Settings
from ta_backend.db import Base, make_engine
from ta_backend.main import create_app
from ta_backend.seed import seed_demo


@pytest.fixture
def api(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo(session)
    with TestClient(
        create_app(Settings(database_url=url, storage_dir=tmp_path / "uploads"))
    ) as client:
        yield client, engine
    engine.dispose()
