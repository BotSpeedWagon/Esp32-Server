import asyncio
import websockets
import aiohttp
from aiohttp import web
import os

esp32_conn = None
clients = set()


# WebSocket handler
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    global esp32_conn
    setattr(ws, "is_esp32", False)
    clients.add(ws)

    print("Nova conexão recebida")

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            message = msg.data.strip()
            print(f"Mensagem recebida de {request.remote}: {message}")

            if message == "esp32":
                if esp32_conn and not esp32_conn.closed:
                    print(
                        "Outra conexão tentou se identificar como ESP32, ignorado."
                    )
                else:
                    esp32_conn = ws
                    setattr(ws, "is_esp32", True)
                    print(f"ESP32 conectada: {request.remote}")

            elif message in ("toggle_led", "girar", "parar",
                             "velocidade:rapida", "velocidade:lenta"):
                if esp32_conn and not esp32_conn.closed and getattr(
                        esp32_conn, "is_esp32", False):
                    await esp32_conn.send_str(message)
                    print(f"Comando '{message}' enviado para ESP32")
                else:
                    print("ESP32 não conectada ou conexão inválida")
                    await esp32_conn.send_str(message)

            for client in clients:
                if client != ws:
                    await client.send_str(message)

        elif msg.type == aiohttp.WSMsgType.ERROR:
            print(f"Erro WebSocket: {ws.exception()}")

    clients.discard(ws)
    if ws == esp32_conn:
        esp32_conn = None
        print("ESP32 desconectada")

    print("Conexão encerrada")
    return ws


# Servir HTML
async def index(request):
    return web.FileResponse('./static/index.html')


# Inicializar app
async def start_servers():
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/ws', websocket_handler)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Servidor rodando na porta {port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(start_servers())
