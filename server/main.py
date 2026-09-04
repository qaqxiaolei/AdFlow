import os
import sys
import io

# 优先加载 server/.env，供微信支付等配置使用
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except Exception:
    pass

# Ensure stdout and stderr use utf-8 encoding to prevent emoji logs from crashing python server
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
print('Importing websocket_router')
from routers.websocket_router import *  # DO NOT DELETE THIS LINE, OTHERWISE, WEBSOCKET WILL NOT WORK
print('Importing routers')
from routers import config_router, image_router, root_router, workspace, canvas, ssl_test, chat_router, settings, tool_confirmation, auth_router, billing_router
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import argparse
from contextlib import asynccontextmanager
from starlette.types import Scope
from starlette.responses import Response
import socketio # type: ignore
print('Importing websocket_state')
from services.websocket_state import sio
print('Importing websocket_service')
from services.websocket_service import broadcast_init_done
print('Importing config_service')
from services.config_service import config_service
print('Importing tool_service')
from services.tool_service import tool_service

async def initialize():
    print('Initializing config_service')
    await config_service.initialize()
    print('Initializing broadcast_init_done')
    await broadcast_init_done()

root_dir = os.path.dirname(__file__)

async def _warmup_agents():
    """预热智能体缓存，减少首次请求延迟"""
    try:
        from services.langgraph_service.agent_cache import agent_cache
        from services.langgraph_service.agent_service import _create_text_model
        from services.langgraph_service.agent_manager import AgentManager

        print('🔥 开始预热智能体缓存...')

        config = config_service.get_config()
        ollama_url = config.get('ollama', {}).get('url', '')
        openai_url = config.get('openai', {}).get('url', '')

        if ollama_url:
            first_model = {
                'provider': 'ollama',
                'model': 'llama3.1',
                'url': ollama_url,
                'type': 'text'
            }
            model_instance = _create_text_model(first_model)
            agent_cache.set_model(first_model, model_instance)
            print(f'✅ 预热模型: ollama/{first_model["model"]}')

            tool_list = [
                {'id': 'write_plan', 'provider': 'system', 'type': 'system'},
                {'id': 'search_video_by_platform', 'provider': 'system', 'type': 'search'},
                {'id': 'generate_image_by_agnes', 'provider': 'agnes', 'type': 'image'},
                {'id': 'generate_video_by_agnes', 'provider': 'volces', 'type': 'video'},
            ]
            agents = AgentManager.create_agents(model_instance, tool_list)
            agent_cache.set_agents(first_model, tool_list, agents)
            print(f'✅ 预热智能体: {[a.name for a in agents]}')
        elif openai_url:
            first_model = {
                'provider': 'openai',
                'model': 'gpt-4o',
                'url': openai_url,
                'type': 'text'
            }
            model_instance = _create_text_model(first_model)
            agent_cache.set_model(first_model, model_instance)
            print(f'✅ 预热模型: openai/{first_model["model"]}')

            tool_list = [
                {'id': 'write_plan', 'provider': 'system', 'type': 'system'},
                {'id': 'search_video_by_platform', 'provider': 'system', 'type': 'search'},
                {'id': 'generate_image_by_agnes', 'provider': 'agnes', 'type': 'image'},
                {'id': 'generate_video_by_agnes', 'provider': 'volces', 'type': 'video'},
            ]
            agents = AgentManager.create_agents(model_instance, tool_list)
            agent_cache.set_agents(first_model, tool_list, agents)
            print(f'✅ 预热智能体: {[a.name for a in agents]}')

        print('🔥 智能体缓存预热完成')
    except Exception as e:
        print(f'⚠️ 预热失败（不影响正常使用）: {e}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # onstartup
    await initialize()
    await tool_service.initialize()
    await _warmup_agents()
    try:
        from services.oss_service import log_oss_status

        log_oss_status(force=True)
    except Exception as e:
        print(f"[oss] 启动自检失败: {e}")
    yield
    # onshutdown

print('Creating FastAPI app')
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
print('Including routers')
app.include_router(config_router.router)
app.include_router(settings.router)
app.include_router(root_router.router)
app.include_router(canvas.router)
app.include_router(workspace.router)
app.include_router(image_router.router)
# SSL 诊断路由默认关闭；需要时设置环境变量 ENABLE_SSL_TEST=1
if os.environ.get("ENABLE_SSL_TEST", "").strip() in ("1", "true", "TRUE", "yes"):
    app.include_router(ssl_test.router)
app.include_router(chat_router.router)
app.include_router(tool_confirmation.router)
app.include_router(auth_router.router)
app.include_router(billing_router.router)

# Mount the React build directory
react_build_dir = os.environ.get('UI_DIST_DIR', os.path.join(
    os.path.dirname(root_dir), "react", "dist"))

# Vite 产物带 hash，可长期缓存；首页视频/图片也允许缓存，避免域名重复慢加载
_CACHEABLE_SUFFIXES = (
    ".js", ".css", ".woff", ".woff2", ".ttf", ".eot",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
    ".mp4", ".webm", ".mov",
)


class CachedStaticFiles(StaticFiles):
    """带长期缓存的静态资源（适用于带 hash 的 /assets 与首页媒体）"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _dist_file_response(rel_path: str) -> FileResponse | None:
    """安全读取 react/dist 下的文件，禁止路径穿越。"""
    if not rel_path or ".." in rel_path.replace("\\", "/").split("/"):
        return None
    full = os.path.normpath(os.path.join(react_build_dir, rel_path))
    if not full.startswith(os.path.normpath(react_build_dir)):
        return None
    if not os.path.isfile(full):
        return None
    response = FileResponse(full)
    lower = rel_path.lower()
    if any(lower.endswith(suf) for suf in _CACHEABLE_SUFFIXES):
        response.headers["Cache-Control"] = "public, max-age=604800"
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


static_site = os.path.join(react_build_dir, "assets")
if os.path.exists(static_site):
    # 带 content hash 的打包资源：长期缓存
    app.mount("/assets", CachedStaticFiles(directory=static_site), name="assets")


@app.get("/")
async def serve_react_app():
    response = FileResponse(os.path.join(react_build_dir, "index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/{full_path:path}")
async def serve_spa_or_static(full_path: str):
    """提供 dist 根目录媒体（如 /backgroudVideo1.mp4），其余回退到 SPA。"""
    # API / 已注册路由优先；此处仅兜底静态与前端路由
    static_resp = _dist_file_response(full_path)
    if static_resp is not None:
        return static_resp
    index_path = os.path.join(react_build_dir, "index.html")
    if os.path.isfile(index_path):
        response = FileResponse(index_path)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response
    return Response(status_code=404)


print('Creating socketio app')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path='/socket.io')

if __name__ == "__main__":
    # bypass localhost / 火山方舟等直连域名，避免系统代理干扰
    _bypass = {
        "127.0.0.1", "localhost", "::1",
        ".volces.com", "ark.cn-beijing.volces.com",
    }
    current = set(os.environ.get("no_proxy", "").split(",")) | set(
        os.environ.get("NO_PROXY", "").split(","))
    os.environ["no_proxy"] = os.environ["NO_PROXY"] = ",".join(
        sorted(_bypass | current - {""}))

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=57988,
                        help='Port to run the server on')
    args = parser.parse_args()
    import uvicorn
    print("🌟Starting server, UI_DIST_DIR:", os.environ.get('UI_DIST_DIR'))

    uvicorn.run(
        socket_app,
        host="0.0.0.0",
        port=args.port,
        timeout_keep_alive=600
    )
