import asyncio
import aiohttp
from aiohttp import web
import logging
import time
from hardware import send_wake_command

logger = logging.getLogger('smart_proxy')
last_wake_times = {}
COOLDOWN_SECONDS = 0  # иммунитет к повторным нажатиям кнопки

async def check_target_alive(session, target_url):
    #Пинг целевого сервера
    try:
        async with session.get(target_url, timeout=1, allow_redirects=False) as resp:
            return True
    except Exception:
        return False

async def sse_handler(request):
    #Обработчик Server-Sent Events для страницы ожидания
    config = request.app['config']
    host_header = request.host.split(':')[0].lower()
    
    if host_header not in config['hosts']:
        return web.Response(status=404, text="Host not found")
        
    target_url = config['hosts'][host_header]['target']
    session = request.app['client_session']
    
    resp = web.StreamResponse(status=200, headers={
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    })
    await resp.prepare(request)

    try:
        while True:
            is_alive = await check_target_alive(session, target_url)
            if is_alive:
                await resp.write(b'data: ready\n\n')
                break
            else:
                await resp.write(b'data: ping\n\n')
            await asyncio.sleep(3)
    except ConnectionResetError:
        pass

    return resp

async def proxy_handler(request):
    #Главный маршрутизатор трафика
    if request.path == '/events':
        return await sse_handler(request)

    config = request.app['config']
    host_header = request.host.split(':')[0].lower()

    if host_header not in config['hosts']:
        return web.Response(status=404, text="Host not configured")

    host_conf = config['hosts'][host_header]
    target_full_url = f"{host_conf['target']}{request.path_qs}"
    session = request.app['client_session']

    try:
        async with session.request(
            request.method, target_full_url,
            headers=request.headers,
            data=request.content,
            timeout=aiohttp.ClientTimeout(sock_connect=2),
            allow_redirects=False
        ) as resp:
            
            proxy_resp = web.StreamResponse(status=resp.status, headers=resp.headers)
            await proxy_resp.prepare(request)
            
            async for chunk in resp.content.iter_chunked(4096):
                await proxy_resp.write(chunk)
            
            return proxy_resp

    except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
        # Если целевой сервис не отвечает
        if host_conf.get('wake_needed'):
            current_time = time.time()
            last_wake = last_wake_times.get(host_header, 0)
            
            # кулдаун
            if current_time - last_wake > COOLDOWN_SECONDS:
                logger.info(f"Отправка WAKE. Блокировка реле на {COOLDOWN_SECONDS} сек.")
                asyncio.create_task(send_wake_command(config['mqtt']))
                last_wake_times[host_header] = current_time
            
            # Разделяем браузеры и приложения (API)
            accept_header = request.headers.get('Accept', '')
            if 'text/html' in accept_header:
                return web.FileResponse('wait.html')
            else:
                #мобильное приложение / WebDAV
                return web.Response(status=503, text="503 Service Unavailable: Server is waking up")
        else:
            return web.Response(status=502, text="Local service on VPS is offline")