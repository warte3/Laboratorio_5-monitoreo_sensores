from machine import Pin, I2C, PWM, ADC, Timer
from time import ticks_ms, ticks_diff, sleep
from MPU6050 import MPU6050
from dht import DHT11, DHT22
import utelegram
import network
import _thread
import time
import urequests 

# CONFIGURACIÓN DEL SERVIDOR 
SERVER_URL = "http://10.229.54.29:8000/ingest"  # IP de tu computadora
API_KEY = "cambia-esta-clave"  # Misma clave del servidor

buzzer = PWM(Pin(26), freq=1, duty=0)
dht11 = DHT11(Pin(4)) #RECOMENDACION lectura cada 2 segundos y resistencia entre 4.7k-10k
mpu = MPU6050() #RECOMENDACION lectura cada 50 ms
btn = Pin(12, Pin.IN, Pin.PULL_DOWN)

DEBOUNCE_MS = 200
last_btn_ms=0

def read_buttons():
    global last_btn_ms
    now_btn= ticks_ms()
    btn_press=False
    
    if btn.value() == 1:
        if ticks_diff(now_btn, last_btn_ms) > DEBOUNCE_MS:
            last_btn_ms = now_btn
            btn_press = True
    return btn_press


#---------------------------------Telegram-WIFI---------------------------------------------
token= "8622668323:AAFsMleUXlHAAVk1OXG0-tiEqi8rJdh86zs"
miID='8516885189'
red = "A16 de Paula"
contrasena = "12345678."

"""Conexion a red Wi-fi"""
WLAN = network.WLAN(network.STA_IF) 
WLAN.active(True)
WLAN.connect(red, contrasena)

while not WLAN.isconnected():
    print("Conectando...")
    sleep(1)
print("CONECTADO A WIFI")

"""Diseño del bot"""

ultimo_mensaje = ""
MiBot = utelegram.ubot(token)
print("Estoy listo para la conexión con Telegram") 
MiBot.send(miID, "Conectado con ESP32")

def handle_message(update):
    global ultimo_mensaje
    message = update['message']['text']
    ultimo_mensaje = message
    print("Nuevo mensaje de Telegram:", message)
    MiBot.send(miID, "Mensaje recibido: " + message)

MiBot.set_default_handler(handle_message)


def enviar_al_servidor(temp, hum,gforce,boton_panico):
    """
    Envía temperatura y humedad al servidor Flask
    """
    try:
        datos = {
            "device": "esp32_sensor",
            "temp": temp,
            "hum": hum,
            "gforce": gforce,
            "B": boton_panico,
            "ts": time.time()
        }
        
        headers = {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        }
        
        response = urequests.post(SERVER_URL, json=datos, headers=headers)
        
        # Solo intentar acceder a response si no es None
        if response is not None:
            if response.status_code == 200:
                print(f"Datos enviados Servidor")
            else:
                print(f"Error Envio  servidor")
            response.close()
        else:
            print("Error")
        
    except Exception as e:
        print("Error enviando al servidor:", e)


def recibir_mensajes_telegram():
    MiBot.listen()
_thread.start_new_thread(recibir_mensajes_telegram, ()) 

#---------------------------------------------------------------------------------------------
def activar_buzzer(frecuencia):
    buzzer.freq(frecuencia)
    buzzer.duty(512)
def desactivar_buzzer():
    buzzer.duty(0)
    
last_dht = time.ticks_ms()
last_mpu = time.ticks_ms()
gforce = 0 

while True:
    now = time.ticks_ms()
    B= read_buttons()

    if ultimo_mensaje.lower() == "umbrales": 
        data ="""
           Umbrales
G-Force >=1.05: Movimineto
G-Force >=1.1: Movimineto Brusco
Temperatura <=20: Temperatura baja
Temperatura >=35: Temperatura alta
Humedad <=40: Humedad baja
Humedad >=60: Humedad alta
           """ 
        MiBot.send(miID, data)
        ultimo_mensaje = ""


    elif ultimo_mensaje.lower() == "gforce": 
        data="G-Force:",gforce
        MiBot.send(miID,data)
        ultimo_mensaje = ""
        
        
    elif ultimo_mensaje.lower() == "temperatura":
        data="Temp:",t,"°C"
        MiBot.send(miID,data)
        ultimo_mensaje = ""
        
    elif ultimo_mensaje.lower() == "humedad":
        data="Hum:",h,"%"
        MiBot.send(miID,data)
        ultimo_mensaje = ""
        
    if B:
        activar_buzzer(700)
        MiBot.send(miID, "Boton de panico activado")
        

        # MPU6050 
    if time.ticks_diff(now, last_mpu) >= 50:
        gforce = mpu.read_accel_abs(g=True)
        print(f"G-force|{gforce}")
        last_mpu = now
        if gforce >=1.05:
            if gforce >=1.1:
                MiBot.send(miID, "Se Detecto Movimiento Brusco")
                activar_buzzer(1500)
            else:
                MiBot.send(miID, "Se Detecto Movimiento")
                activar_buzzer(1200)
        #DHT11
    if time.ticks_diff(now, last_dht) >= 2000:
        dht11.measure()
        t = dht11.temperature()
        h = dht11.humidity()
        print(f"DHT -> Temp:{t:.1f}°C Hum:{h:.1f}%")
        last_dht = now
        
        enviar_al_servidor(t, h,gforce,B)
        
        
        if t<=20: # la temperatura va de 20 a 35
            activar_buzzer(523)
            MiBot.send(miID, " Alerta nivel de temperatura bajo ")
            
        if t>=35:
            activar_buzzer(582)
            MiBot.send(miID, " Alerta nivel de temperatura alto ")    
        if h>=60: # 60 - 50 
            activar_buzzer(280)
            MiBot.send(miID, " Revisa Humedad Alta >=60")
        if h<=40:
            activar_buzzer(523)
            MiBot.send(miID, "Revisa Humedad Baja <=40 ")
        else:
            if gforce<1.05:
                desactivar_buzzer()
    sleep(0.5)