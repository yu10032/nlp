from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from ta_backend.api import courses, coverage, documents, drafts, graph, matching, questions
from ta_backend.config import Settings
from ta_backend.db import make_engine
from ta_backend.models import IngestionJob, Material
from ta_backend.services.generation import make_provider


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
        app.state.settings = settings
        app.state.generation_provider = make_provider(settings)
        with app.state.session_factory() as session:
            interrupted = session.scalars(
                select(IngestionJob).where(
                    IngestionJob.status.in_(["queued", "running"]),
                )
            ).all()
            for job in interrupted:
                job.status = "failed"
                job.error = "服务重启中断了解析，请重新上传该资料"
                material = session.get(Material, job.material_id)
                material.status = "failed"
                material.warnings = [job.error]
            session.commit()
        yield
        engine.dispose()

    app = FastAPI(title="课程智能助教 API", version="0.1.0", lifespan=lifespan)
    for router in (
        courses.router,
        documents.router,
        graph.router,
        matching.router,
        questions.router,
        drafts.router,
        coverage.router,
    ):
        app.include_router(router, prefix="/api/v1")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException):
        detail = (
            error.detail
            if isinstance(error.detail, dict)
            else {
                "code": {
                    404: "not_found",
                    409: "conflict",
                    413: "file_too_large",
                    415: "unsupported_file",
                }.get(error.status_code, "request_error"),
                "message": str(error.detail),
            }
        )
        return JSONResponse(status_code=error.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_input",
                    "message": "输入内容不符合要求，请检查必填项、长度与格式",
                }
            },
        )

    @app.get("/api/v1/health", tags=["system"])
    def health():
        return {
            "status": "ok",
            "generation": {
                "provider": settings.generation_provider,
                "available": settings.generation_provider == "external"
                and bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model),
                "model": settings.llm_model if settings.generation_provider == "external" else None,
            },
            "matcher": {"active": "name/tfidf baseline", "trained_model_loaded": False},
        }

    return app


app = create_app()
