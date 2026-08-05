import cv2
import socket
import json
import threading
import time
import math
import os
import tempfile
import numpy as np
from ultralytics import YOLO
from gtts import gTTS
import playsound

# ==========================================
# CONFIGURACIÓN DE VOZ (gTTS)
# ==========================================
def speak_alert_spanish(mensaje_texto):
    def run_speech():
        temp_filename = None
        try:
            tts = gTTS(text=mensaje_texto, lang='es', slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tf:
                temp_filename = tf.name
            tts.save(temp_filename)
            playsound.playsound(temp_filename)
        except Exception:
            pass
        finally:
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass

    threading.Thread(target=run_speech, daemon=True).start()

# ==========================================
# CONFIGURACIÓN DEL SISTEMA Y IA
# ==========================================
RTSP_URL = "rtsp://192.168.14.6:8554/cam0"
# RTSP_URL = 0  # Activar para webcam local

CONFIDENCE_THRESHOLD = 0.55 
TARGET_CLASS_ID = 0  # ID del dron en el modelo entrenado

print("Cargando modelo custom mejorado (drone_finetuned-3)...")
NUEVO_MODELO_PATH = r"C:\drone\scripts\runs\detect\runs\drone_finetuned-3\weights\best.pt"
model_drone = YOLO(NUEVO_MODELO_PATH)

# Diccionario base con todas las variables incluyendo velocidad
telemetry_data = {"pitch": 0.0, "roll": 0.0, "yaw": 0.0, "altitud": 0.0, "velocidad": 0.0}
current_frame = None
latest_boxes = []
frame_lock = threading.Lock()

last_alert_time = 0
ALERT_COOLDOWN = 4.0 


def udp_telemetry_worker():
    global telemetry_data
    UDP_IP = "0.0.0.0"
    UDP_PORT = 5005
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            telemetry_data = json.loads(data.decode("utf-8"))
        except Exception:
            pass


def ai_inference_worker():
    global current_frame, latest_boxes, last_alert_time

    while True:
        with frame_lock:
            if current_frame is None:
                time.sleep(0.01)
                continue
            frame_to_process = current_frame.copy()

        boxes_detected = []
        dron_visto_este_frame = False

        results_drone = model_drone.track(
            frame_to_process,
            conf=CONFIDENCE_THRESHOLD,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )
        
        for r in results_drone:
            for box in r.boxes:
                clase_id = int(box.cls[0])
                
                # FILTRO ESTRICTO POR ID: Solo ID 0 (Drones)
                if clase_id == TARGET_CLASS_ID:
                    x1, y1, x2, y2 = box.xyxy[0].int().tolist()
                    conf = math.ceil((box.conf[0] * 100)) / 100
                    
                    boxes_detected.append((x1, y1, x2, y2, "DRON", conf))
                    dron_visto_este_frame = True

        with frame_lock:
            latest_boxes = boxes_detected

        if dron_visto_este_frame and (time.time() - last_alert_time) > ALERT_COOLDOWN:
            speak_alert_spanish("Dron detectado")
            last_alert_time = time.time()

        time.sleep(0.02)


def draw_dji_bracket(frame, x1, y1, x2, y2, label=""):
    color = (0, 255, 120)
    thickness = 2
    length = 25
    cv2.line(frame, (x1, y1), (x1 + length, y1), color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + length), color, thickness)
    cv2.line(frame, (x2, y1), (x2 - length, y1), color, thickness)
    cv2.line(frame, (x2, y1), (x2, y2 - length), color, thickness)
    cv2.line(frame, (x1, y2), (x1 + length, y2), color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - length), color, thickness)
    cv2.line(frame, (x2, y2), (x2 - length, y2), color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - length), color, thickness)

    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
    cv2.circle(frame, (cx, cy), 4, color, -1)
    if label:
        cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def draw_glass_panel(frame, x1, y1, x2, y2, alpha=0.3, color=(0, 0, 0)):
    """Crea un panel traslúcido para mejorar la legibilidad sin perder inmersión."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def draw_pro_hud(frame):
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    c_white = (255, 255, 255)
    c_cyan = (255, 200, 0)
    c_green = (0, 255, 120)
    c_red = (0, 0, 255)
    
    # Extraer telemetría
    yaw = telemetry_data.get("yaw", 0)
    pitch = telemetry_data.get("pitch", 0)
    alt_m = telemetry_data.get("altitud", 0.0)
    alt_ft = alt_m * 3.28084
    velocidad = telemetry_data.get("velocidad", 0.0)

    # ==========================================
    # 1. TOP BAR (Minimalista)
    # ==========================================
    draw_glass_panel(frame, 0, 0, w, 40, alpha=0.4)
    cv2.putText(frame, "SYS: MANUAL", (20, 25), font, 0.45, c_cyan, 1, cv2.LINE_AA)
    cv2.putText(frame, "GPS: 3D LOCK", (150, 25), font, 0.45, c_green, 1, cv2.LINE_AA)
    
    n_drones = len(latest_boxes)
    estado_color = c_red if n_drones > 0 else c_green
    estado_txt = f"ALERTA: {n_drones} DRON(ES)" if n_drones > 0 else "ZONA DESPEJADA"
    cv2.putText(frame, estado_txt, (w // 2 - 80, 25), font, 0.5, estado_color, 2, cv2.LINE_AA)
    
    cv2.putText(frame, "BAT: 84% [11.4V]", (w - 150, 25), font, 0.45, c_white, 1, cv2.LINE_AA)

    # ==========================================
    # 2. CINTA DE VELOCIDAD (Izquierda - Rolling Tape)
    # ==========================================
    tape_h = 300
    tape_y_start = h // 2 - tape_h // 2
    px_per_ms = 15  
    
    draw_glass_panel(frame, 10, tape_y_start, 70, tape_y_start + tape_h, alpha=0.3)
    cv2.putText(frame, "SPD", (25, tape_y_start - 10), font, 0.4, c_cyan, 1, cv2.LINE_AA)
    
    for i in range(-5, 6):
        tick_val = int(velocidad) + i
        if tick_val < 0: continue
        
        diff = velocidad - tick_val
        y_pos = int(h // 2 + diff * px_per_ms)
        
        if tape_y_start < y_pos < tape_y_start + tape_h:
            length = 10 if tick_val % 5 == 0 else 5
            cv2.line(frame, (60, y_pos), (60 + length, y_pos), c_white, 1)
            if tick_val % 5 == 0:
                cv2.putText(frame, str(tick_val), (25, y_pos + 4), font, 0.4, c_white, 1, cv2.LINE_AA)
                
    # Indicador central fijo de velocidad
    cv2.rectangle(frame, (70, h // 2 - 15), (130, h // 2 + 15), (0, 0, 0), -1)
    cv2.rectangle(frame, (70, h // 2 - 15), (130, h // 2 + 15), c_cyan, 1)
    cv2.putText(frame, f"{velocidad:.1f}", (75, h // 2 + 5), font, 0.6, c_white, 2, cv2.LINE_AA)
    pts_spd = np.array([[70, h//2], [76, h//2 - 6], [76, h//2 + 6]], np.int32)
    cv2.fillPoly(frame, [pts_spd], c_cyan)

    # ==========================================
    # 3. CINTA DE ALTITUD (Derecha - Rolling Tape)
    # ==========================================
    px_per_ft = 2
    
    draw_glass_panel(frame, w - 70, tape_y_start, w - 10, tape_y_start + tape_h, alpha=0.3)
    cv2.putText(frame, "ALT", (w - 45, tape_y_start - 10), font, 0.4, c_cyan, 1, cv2.LINE_AA)
    
    for i in range(-8, 9):
        tick_val = int(alt_ft / 10) * 10 + (i * 10)
        diff = alt_ft - tick_val
        y_pos = int(h // 2 + diff * px_per_ft)
        
        if tape_y_start < y_pos < tape_y_start + tape_h:
            length = 10 if tick_val % 50 == 0 else 5
            cv2.line(frame, (w - 70, y_pos), (w - 70 - length, y_pos), c_white, 1)
            if tick_val % 50 == 0:
                cv2.putText(frame, str(tick_val), (w - 55, y_pos + 4), font, 0.4, c_white, 1, cv2.LINE_AA)

    # Indicador central fijo de altitud
    cv2.rectangle(frame, (w - 140, h // 2 - 15), (w - 70, h // 2 + 15), (0, 0, 0), -1)
    cv2.rectangle(frame, (w - 140, h // 2 - 15), (w - 70, h // 2 + 15), c_cyan, 1)
    cv2.putText(frame, f"{alt_ft:.1f}", (w - 135, h // 2 + 5), font, 0.55, c_white, 2, cv2.LINE_AA)
    pts_alt = np.array([[w - 70, h//2], [w - 76, h//2 - 6], [w - 76, h//2 + 6]], np.int32)
    cv2.fillPoly(frame, [pts_alt], c_cyan)

    # ==========================================
    # 4. CROSSHAIR CENTRAL Y PITCH LADDER
    # ==========================================
    cx, cy = w // 2, h // 2
    
    # Retículo de la aeronave (Fijo en el centro)
    cv2.line(frame, (cx - 40, cy), (cx - 15, cy), c_cyan, 2)
    cv2.line(frame, (cx + 15, cy), (cx + 40, cy), c_cyan, 2)
    cv2.line(frame, (cx - 15, cy), (cx - 15, cy + 15), c_cyan, 2)
    cv2.line(frame, (cx + 15, cy), (cx + 15, cy + 15), c_cyan, 2)
    cv2.circle(frame, (cx, cy), 2, c_red, -1)

    # Escalera de cabeceo (Se mueve con el Pitch)
    px_per_degree = 6
    pitch_offset = int(pitch * px_per_degree)
    
    for deg in [-20, -10, 10, 20]:
        line_y = cy + pitch_offset - (deg * px_per_degree)
        
        if cy - 150 < line_y < cy + 150:
            color_linea = c_green if deg > 0 else (0, 150, 255) 
            estilo = cv2.LINE_AA
            
            if deg > 0:
                cv2.line(frame, (cx - 60, line_y), (cx - 25, line_y), color_linea, 1, estilo)
                cv2.line(frame, (cx + 25, line_y), (cx + 60, line_y), color_linea, 1, estilo)
            else:
                for x_seg in range(cx - 60, cx - 20, 10):
                    cv2.line(frame, (x_seg, line_y), (x_seg + 5, line_y), color_linea, 1, estilo)
                for x_seg in range(cx + 25, cx + 60, 10):
                    cv2.line(frame, (x_seg, line_y), (x_seg + 5, line_y), color_linea, 1, estilo)
            
            cv2.putText(frame, str(abs(deg)), (cx + 65, line_y + 4), font, 0.35, color_linea, 1, cv2.LINE_AA)
            cv2.putText(frame, str(abs(deg)), (cx - 85, line_y + 4), font, 0.35, color_linea, 1, cv2.LINE_AA)

    # ==========================================
    # 5. BRÚJULA HORIZONTAL (Rumbo abajo al centro)
    # ==========================================
    compass_y = h - 30
    draw_glass_panel(frame, cx - 150, compass_y - 20, cx + 150, compass_y + 20, alpha=0.4)
    
    cv2.putText(frame, f"{int(yaw):03d}°", (cx - 15, compass_y - 25), font, 0.5, c_white, 1, cv2.LINE_AA)
    
    cardinals = {0: "N", 90: "E", 180: "S", 270: "W", 360: "N"}
    for deg in range(0, 361, 15):
        diff = deg - yaw
        while diff < -180: diff += 360
        while diff > 180: diff -= 360
        
        pos_x = cx + int(diff * (300 / 90.0))
        if cx - 140 < pos_x < cx + 140:
            if deg in cardinals:
                cv2.putText(frame, cardinals[deg], (pos_x - 5, compass_y + 5), font, 0.4, c_cyan, 1, cv2.LINE_AA)
            else:
                cv2.line(frame, (pos_x, compass_y), (pos_x, compass_y + 5), c_white, 1)
                
    pts_comp = np.array([[cx, compass_y - 15], [cx - 6, compass_y - 22], [cx + 6, compass_y - 22]], np.int32)
    cv2.fillPoly(frame, [pts_comp], c_cyan)


def main():
    global current_frame, latest_boxes

    threading.Thread(target=udp_telemetry_worker, daemon=True).start()
    threading.Thread(target=ai_inference_worker, daemon=True).start()

    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        return

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        frame = cv2.flip(frame, -1)

        with frame_lock:
            current_frame = frame.copy()
            boxes_to_draw = list(latest_boxes)

        for (x1, y1, x2, y2, name, conf) in boxes_to_draw:
            draw_dji_bracket(frame, x1, y1, x2, y2, label=f"{name} {conf}")

        draw_pro_hud(frame)

        cv2.imshow("Ground Control Station - HUD Pro", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()