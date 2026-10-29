import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from ta_backend.config import Settings
from ta_backend.db import Base, make_engine
from ta_backend.main import create_app
from ta_backend.seed import seed_demo


@pytest.fixture(autouse=True)
def no_real_generation_requests(monkeypatch):
    """业务测试仅用进程内客户端或 MockTransport，禁止误用本机 API 配置。"""

    async def blocked(self, request):
        pytest.fail("离线测试禁止真实 HTTP 请求；请使用 httpx.MockTransport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


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
