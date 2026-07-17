"""FastAPI 应用入口

启动方式：uvicorn server.main:app --host 0.0.0.0 --port 7860
"""

from contextlib import asynccontextmanager
from pathlib import Path

import anyio.to_thread
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from config import config
from server.database import init_db
from server.routes.auth_routes import router as auth_router
from server.routes.task_routes import router as task_router
from server.services.cleaner import start_scheduler
from server.services.task_queue import task_queue

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置，请在 .env 中设置强随机值（如 openssl rand -hex 32）")
    if len(config.jwt_secret) < 16:
        raise RuntimeError("JWT_SECRET 过短（< 16 字节），请使用至少 32 字节的强随机值")
    # SSE 同步 generator 每个连接占用一个线程池线程（anyio 默认 40），
    # 扩容避免长连接挤占其他同步接口
    anyio.to_thread.current_default_thread_limiter().total_tokens = 100
    init_db()
    task_queue.start()
    scheduler = start_scheduler()
    logger.info("服务已启动，前端目录: {}", FRONTEND_DIST)
    yield
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title="视频分镜分析", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(task_router)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """静态文件 + SPA history 路由回退（/api 已被上面的路由优先匹配）"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        if not FRONTEND_DIST.exists():
            raise HTTPException(
                status_code=404,
                detail="前端未构建，请先执行 cd frontend && npm run build",
            )
        resolved_dist = FRONTEND_DIST.resolve()
        candidate = (resolved_dist / full_path).resolve()
        if not candidate.is_relative_to(resolved_dist):
            return FileResponse(FRONTEND_DIST / "index.html")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
