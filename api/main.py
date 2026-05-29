from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Career Agent API",
        description="智能选岗及简历定制 Agent 后端 API",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": f"服务器内部错误: {type(exc).__name__}: {exc}"})

    from api.routes import (
        profile,
        evidence,
        jobs,
        analyses,
        resume_versions,
        applications,
        library,
        history,
    )

    app.include_router(profile.router, prefix="/api")
    app.include_router(evidence.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")
    app.include_router(resume_versions.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(history.router, prefix="/api")

    return app


app = create_app()
