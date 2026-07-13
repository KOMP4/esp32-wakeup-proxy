import json
import aiohttp
from aiohttp import web
import logging
import ssl
from router import proxy_handler

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('proxy.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('smart_proxy')

def load_config():
    """Загрузка настроек из JSON файла"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

async def init_session(app):
    #auto_decompress=False критически важен, чтобы прокси не ломал сжатые (gzip) ответы от Nextcloud и отдавал их браузеру как есть.
    app['client_session'] = aiohttp.ClientSession(auto_decompress=False)

async def close_session(app):
    await app['client_session'].close()

def main():
    config = load_config()
    app = web.Application(client_max_size=1024**3 * 20)
    
    app['config'] = config
    
    app.on_startup.append(init_session)
    app.on_cleanup.append(close_session)
    
    # Направляем все запросы в маршрутизатор
    app.router.add_route('*', '/{path_info:.*}', proxy_handler)
    
    # HTTPS из config.json
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(
        certfile=config['ssl_cert'], 
        keyfile=config['ssl_key']
    )
    
    logger.info(f"Запуск защищенного прокси на порту {config['port']}")
    
    web.run_app(app, port=config['port'], access_log=logger, ssl_context=ssl_context)

if __name__ == '__main__':
    main()