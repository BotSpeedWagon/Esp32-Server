import asyncio
from aiohttp import web
import os

# Conexões para controle
esp32_conn = None
control_clients = set()

# Conexões para a webcam
webcam_sender = None
webcam_viewers = set()


##############################
#  Handlers de Controle (/ws)
##############################
async def control_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    global esp32_conn
    setattr(ws, "is_esp32", False)
    control_clients.add(ws)
    print("Nova conexão de controle:", request.remote)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            message = msg.data.strip()
            print(
                f"Mensagem de controle recebida de {request.remote}: {message}"
            )

            # Identificação da ESP32
            if message == "esp32":
                if esp32_conn and not esp32_conn.closed:
                    print(
                        "Outra conexão tentou se identificar como ESP32, ignorado."
                    )
                else:
                    esp32_conn = ws
                    setattr(ws, "is_esp32", True)
                    print(f"ESP32 conectada: {request.remote}")

            # Envio de comandos para a ESP32
            elif message in ("toggle_led", "girar", "parar",
                             "velocidade:rapida", "velocidade:lenta"):
                if esp32_conn and not esp32_conn.closed and getattr(
                        esp32_conn, "is_esp32", False):
                    await esp32_conn.send_str(message)
                    print(f"Comando '{message}' enviado para ESP32")
                else:
                    print("ESP32 não conectada ou conexão inválida")

            # Opcional: retransmitir a mensagem para os demais clientes de controle
            for client in control_clients:
                if client != ws and not client.closed:
                    await client.send_str(message)

        elif msg.type == web.WSMsgType.ERROR:
            print(f"Erro no WebSocket de controle: {ws.exception()}")

    control_clients.discard(ws)
    if ws == esp32_conn:
        esp32_conn = None
        print("ESP32 desconectada")

    print("Conexão de controle encerrada:", request.remote)
    return ws


####################################
#  Handlers de Webcam (/webcam e /webcam_view)
####################################
# Handler para a conexão que envia o stream (webcam sender)
async def webcam_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    global webcam_sender
    is_sender = False
    print("Nova conexão na rota /webcam:", request.remote)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            # Identifica o dispositivo que envia o stream
            if msg.data.strip() == "webcam_sender":
                if webcam_sender is None:
                    webcam_sender = ws
                    is_sender = True
                    print("Webcam sender conectado:", request.remote)
                else:
                    print(
                        "Já existe um sender de webcam, nova tentativa ignorada"
                    )
            # Se for texto diferente, pode ignorar ou tratar como comando extra se necessário
        elif msg.type == web.WSMsgType.BINARY:
            # Recebe frame e o retransmite para os visualizadores
            if is_sender:
                for viewer in webcam_viewers.copy():
                    if not viewer.closed:
                        await viewer.send_bytes(msg.data)
        elif msg.type == web.WSMsgType.ERROR:
            print("Erro no WebSocket da webcam:", ws.exception())

    if is_sender:
        webcam_sender = None
        print("Webcam sender desconectado:", request.remote)
    print("Conexão /webcam encerrada:", request.remote)
    return ws


# Handler para as conexões que apenas visualizam o stream
async def webcam_view_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    webcam_viewers.add(ws)
    print("Novo visualizador da webcam:", request.remote)

    async for msg in ws:
        if msg.type == web.WSMsgType.ERROR:
            print("Erro no WebSocket do visualizador:", ws.exception())

    webcam_viewers.discard(ws)
    print("Visualizador desconectado:", request.remote)
    return ws


##############################
#  Rota para servir a página HTML
##############################
async def index(request):
    return web.FileResponse('./static/index.html')


##############################
# Inicialização do servidor
##############################
async def start_servers():
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/ws', control_handler)
    app.router.add_get('/webcam',
                       webcam_handler)  # Para a conexão do sender da webcam
    app.router.add_get('/webcam_view',
                       webcam_view_handler)  # Para os visualizadores do stream

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Servidor rodando na porta {port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(start_servers())
