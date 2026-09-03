import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth_router, router, ws_router
from app.cli.shell import shell_loop
from app.config import settings
from app.tcp.server import start_tcp_server_action, stop_tcp_server_action


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_tcp_server_action()
    yield
    await stop_tcp_server_action()


app = FastAPI(title="drink server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)
app.include_router(ws_router)

dist_path = Path(__file__).resolve().parent.parent / "interface" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="interface")
else:
    @app.get("/")
    async def root_fallback():
        return {
            "status": "ok",
            "server": "drink",
            "message": "interface dist not built",
        }


async def main() -> None:
    config = uvicorn.Config(
        app=app,
        host=settings.web_host,
        port=settings.web_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    print(f"drink server - web UI at http://{settings.web_host}:{settings.web_port}")
    print("type help for commands")

    shell_task = asyncio.create_task(shell_loop())
    try:
        await server.serve()
    finally:
        shell_task.cancel()
        try:
            await shell_task
        except (asyncio.CancelledError, Exception):
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye.")
