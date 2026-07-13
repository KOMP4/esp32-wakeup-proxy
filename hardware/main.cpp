#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>

// --- НАСТРОЙКИ СЕТИ И MQTT ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "YOUR_VPS_IP";
const int mqtt_port = 8883;
const int RELAY_PIN = 4;

// --- СЕРТИФИКАТЫ ---
const char* ca_cert = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR CA CERT
-----END CERTIFICATE-----
)EOF";

const char* client_cert = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR CLIENT CERT
-----END CERTIFICATE-----
)EOF";

const char* client_key = R"EOF(
-----BEGIN PRIVATE KEY-----
YOUR CLIENT KEY
-----END PRIVATE KEY-----
)EOF";

// --- ГЛОБАЛЬНЫЕ ОБЪЕКТЫ ---
WiFiClientSecure espClient;
PubSubClient client(espClient);


unsigned long relay_timer = 0;
bool is_relay_active = false;
const unsigned long RELAY_HOLD_TIME = 800; // Держим кнопку 0.8 сек


// --- ФУНКЦИИ ---

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  // Отключаем спящий режим модема, чтобы не терять пакеты TLS
  WiFi.setSleep(false); 
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == "home/server/power" && message == "WAKE") {
    Serial.println(">>> КОМАНДА ПОЛУЧЕНА: Включаем сервер! <<<");
    digitalWrite(RELAY_PIN, HIGH);

    is_relay_active = true;
    relay_timer = millis();
  }
}

void reconnect() {
  if (!client.connected()) {
    espClient.stop();
    delay(500); // Даем ядру время на сборку мусора в памяти после stop

    Serial.print("Attempting MQTT connection...");
    
    // Генерируем случайный ClientID
    String clientId = "ESP32C3-Client-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected!");
      client.subscribe("home/server/power");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" (Повтор в следующем цикле)");
    }
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  setup_wifi();

  espClient.setCACert(ca_cert);
  espClient.setCertificate(client_cert);
  espClient.setPrivateKey(client_key);
  
  espClient.setTimeout(15);
  espClient.setHandshakeTimeout(5);

  client.setBufferSize(1024);   // Расширяем буфер для TLS пакетов
  client.setSocketTimeout(15);
  
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

unsigned long lastReconnectAttempt = 0;

void loop() {
  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      reconnect();
    }
  } else {
    client.loop();
  }

  if (is_relay_active && (millis() - relay_timer >= RELAY_HOLD_TIME)) {
    digitalWrite(RELAY_PIN, LOW);
    is_relay_active = false;
    Serial.println(">>> Кнопка отпущена <<<");
  }
  
  delay(1); 
}
