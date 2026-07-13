import asyncio
import ssl
import aiomqtt
import logging

logger = logging.getLogger('smart_proxy')
is_waking_up = False

async def send_wake_command(mqtt_conf):
    global is_waking_up
    if is_waking_up:
        return
    
    is_waking_up = True
    logger.info("Отправка сигнала WAKE на ESP32...")
    
    try:
        ssl_context = ssl.create_default_context(cafile=mqtt_conf['cert_ca'])
        ssl_context.load_cert_chain(certfile=mqtt_conf['cert_crt'], keyfile=mqtt_conf['cert_key'])
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with aiomqtt.Client(mqtt_conf['broker'], port=mqtt_conf['port'], tls_context=ssl_context) as client:
            await client.publish(mqtt_conf['topic'], mqtt_conf['payload'])
        logger.info("Сигнал WAKE успешно отправлен!")
    except Exception as e:
        logger.error(f"Ошибка MQTT: {e}")
    finally:
        # Защита от спама
        await asyncio.sleep(15)
        is_waking_up = False