import subprocess
import time
import smbus2
import math
import socket
import json
from bmp280 import BMP280

# ==========================================
# CONFIGURACIÓN DE RED
# ==========================================
PC_IP = "192.168.14.3"
UDP_PORT = 5005

# ==========================================
# INICIALIZACIÓN DE SENSORES (IMU Y BARÓMETRO)
# ==========================================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

bus_imu = smbus2.SMBus(1)
IMU_ADDR = 0x68    
MAG_ADDR = 0x0C    

bus_baro = smbus2.SMBus(0)
BMP_ADDR = 0x76    

try:
    bmp280 = BMP280(i2c_dev=bus_baro, i2c_addr=BMP_ADDR)
    PRESION_BASE = 1013.25 
    print("[INFO] GY-BMP280 inicializado correctamente en el Bus 0.")
except Exception as e:
    print(f"[ADVERTENCIA] Barómetro no detectado ({e}). La altitud será 0.")
    bmp280 = None

def init_imu():
    try:
        bus_imu.write_byte_data(IMU_ADDR, 0x06, 0x01)
        time.sleep(0.1)
        bus_imu.write_byte_data(IMU_ADDR, 0x0F, 0x02)
        time.sleep(0.1)
        bus_imu.write_byte_data(MAG_ADDR, 0x31, 0x08)
        time.sleep(0.1)
        print("[INFO] IMU y Brújula inicializados correctamente en el Bus 1.")
    except Exception as e:
        print(f"[ERROR] Error crítico en IMU: {e}")
        exit()

def read_word_2c(reg):
    high = bus_imu.read_byte_data(IMU_ADDR, reg)
    low = bus_imu.read_byte_data(IMU_ADDR, reg+1)
    val = (high << 8) + low
    if val >= 0x8000:
        return -((65535 - val) + 1)
    return val

def read_mag():
    try:
        data = bus_imu.read_i2c_block_data(MAG_ADDR, 0x11, 8)
        hx = (data[1] << 8) | data[0]
        hy = (data[3] << 8) | data[2]
        hz = (data[5] << 8) | data[4]
        if hx >= 32768: hx -= 65536
        if hy >= 32768: hy -= 65536
        if hz >= 32768: hz -= 65536
        return hx * 0.15, hy * 0.15, hz * 0.15
    except Exception:
        return 0.0, 0.0, 0.0

init_imu()

def main():
    processes = []
    try:
        # 1. INICIAR MEDIAMTX EN SEGUNDO PLANO (Ruta absoluta y cwd corregidos)
        print("[INFO] Lanzando servidor MediaMTX...")
        mediamtx_proc = subprocess.Popen(["/home/uboglasses/mediamtx"], cwd="/home/uboglasses")
        processes.append(mediamtx_proc)
        time.sleep(2)  # Dar tiempo a que el servidor levante

        # 2. INICIAR CÁMARA 0 (Sensor ID 0 -> Puerto 8004)
        print("[INFO] Activando flujo de video de la Cámara 0 (Sensor ID 0)...")
        gst_cmd_0 = (
            "gst-launch-1.0 nvarguscamerasrc sensor-id=0 ! "
            "'video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1' ! "
            "nvvidconv ! "
            "'video/x-raw(memory:NVMM),format=I420' ! "
            "nvv4l2h264enc bitrate=2000000 insert-sps-pps=true ! "
            "h264parse ! mpegtsmux ! "
            "udpsink host=127.0.0.1 port=8004"
        )
        gst_proc_0 = subprocess.Popen(gst_cmd_0, shell=True)
        processes.append(gst_proc_0)

        # 3. INICIAR CÁMARA 1 (Sensor ID 1 -> Puerto 8005)
        print("[INFO] Activando flujo de video de la Cámara 1 (Sensor ID 1)...")
        gst_cmd_1 = (
            "gst-launch-1.0 nvarguscamerasrc sensor-id=1 ! "
            "'video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1' ! "
            "nvvidconv ! "
            "'video/x-raw(memory:NVMM),format=I420' ! "
            "nvv4l2h264enc bitrate=2000000 insert-sps-pps=true ! "
            "h264parse ! mpegtsmux ! "
            "udpsink host=127.0.0.1 port=8005"
        )
        gst_proc_1 = subprocess.Popen(gst_cmd_1, shell=True)
        processes.append(gst_proc_1)

        print("[INFO] Servidor y flujos de ambas cámaras activos con éxito.")

        # 4. BUCLE PRINCIPAL DE TELEMETRÍA (IMU + BARÓMETRO + VELOCIDAD)
        print("[INFO] Iniciando transmisión de telemetría UDP hacia el PC...")
        
        smoothed_yaw = 0.0
        smoothed_pitch = 0.0
        smoothed_roll = 0.0
        is_first_read = True

        velocidad_x = 0.0
        velocidad_y = 0.0
        last_time = time.time()

        while True:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            accel_x = read_word_2c(0x2D) / 16384.0
            accel_y = read_word_2c(0x2F) / 16384.0
            accel_z = read_word_2c(0x31) / 16384.0
            mag_x, mag_y, mag_z = read_mag()

            ax = accel_z     
            ay = accel_x     
            az = -accel_y    

            mx = -mag_z      
            my = mag_x       
            mz = mag_y       

            if ax == 0 and ay == 0 and az == 0:
                raw_pitch, raw_roll, raw_yaw = 0.0, 0.0, 0.0
            else:
                raw_pitch = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
                raw_roll = math.degrees(math.atan2(ay, az))
                raw_yaw = math.degrees(math.atan2(-my, mx))
                if raw_yaw < 0: raw_yaw += 360.0 

            # Filtrado y suavizado de datos
            if is_first_read:
                smoothed_yaw = raw_yaw
                smoothed_pitch = raw_pitch
                smoothed_roll = raw_roll
                is_first_read = False
            else:
                diff_yaw = raw_yaw - smoothed_yaw
                if diff_yaw > 180: raw_yaw -= 360
                elif diff_yaw < -180: raw_yaw += 360
                
                alpha_yaw = 0.15
                smoothed_yaw = smoothed_yaw + alpha_yaw * (raw_yaw - smoothed_yaw)
                if smoothed_yaw < 0: smoothed_yaw += 360
                elif smoothed_yaw >= 360: smoothed_yaw -= 360
                    
                alpha_pr = 0.12 
                smoothed_pitch = smoothed_pitch + alpha_pr * (raw_pitch - smoothed_pitch)
                smoothed_roll = smoothed_roll + alpha_pr * (raw_roll - smoothed_roll)

            # Cálculo de velocidad cinemática
            grav_x = math.sin(math.radians(smoothed_pitch))
            grav_y = -math.sin(math.radians(smoothed_roll)) * math.cos(math.radians(smoothed_pitch))

            accel_dinamica_x = (ax - grav_x) * 9.81
            accel_dinamica_y = (ay - grav_y) * 9.81

            if abs(accel_dinamica_x) < 0.3: accel_dinamica_x = 0
            if abs(accel_dinamica_y) < 0.3: accel_dinamica_y = 0

            friccion = 0.95
            velocidad_x = (velocidad_x + accel_dinamica_x * dt) * friccion
            velocidad_y = (velocidad_y + accel_dinamica_y * dt) * friccion
            velocidad_total = math.sqrt(velocidad_x**2 + velocidad_y**2)

            # Barómetro
            altitud_m = 0.0
            if bmp280:
                presion_actual = bmp280.get_pressure()
                altitud_m = 44330.0 * (1.0 - math.pow(presion_actual / PRESION_BASE, 0.1903))

            telemetry_data = {
                "pitch": round(smoothed_pitch, 2),
                "roll": round(smoothed_roll, 2),
                "yaw": round(smoothed_yaw, 2),
                "altitud": round(altitud_m, 2),
                "velocidad": round(velocidad_total, 2)
            }
            
            mensaje = json.dumps(telemetry_data).encode('utf-8')
            sock.sendto(mensaje, (PC_IP, UDP_PORT))
            
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[INFO] Apagando sistema dual en la Jetson de forma segura...")
        for p in processes:
            p.terminate()
            p.wait()
        bus_imu.close()
        bus_baro.close()
        sock.close()
        print("[INFO] Todo cerrado correctamente.")

if __name__ == "__main__":
    main()