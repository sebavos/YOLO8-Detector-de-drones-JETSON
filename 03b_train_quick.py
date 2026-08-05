"""
Entrenamiento RAPIDO para tener un modelo de drones funcionando HOY,
usando solo el dataset base descargado (sin tus fotos propias todavia).

Correr desde la carpeta scripts/:
    python 03b_train_quick.py

Requisitos: haber corrido antes 01_download_dataset.py

pip install ultralytics --break-system-packages
"""

from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # pesos pre-entrenados en COCO, transfer learning

results = model.train(
    data="../configs/data_base_only.yaml",
    epochs=50,          # menos que el entrenamiento final (100), para tenerlo listo antes
    imgsz=640,
    batch=16,            # bajar a 8 si te quedas sin memoria de GPU
    patience=15,
    device=0,             # 0 = GPU, "cpu" si no tenes GPU disponible
    project="../runs",
    name="drone_quick",

    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=15.0,
    scale=0.5,
    fliplr=0.5,
    mosaic=1.0,
)

metrics = model.val()
print("mAP50:", metrics.box.map50)
print("mAP50-95:", metrics.box.map)

print("\nModelo listo en ../runs/drone_quick/weights/best.pt")
print("Usalo ahora en 05_ground_station.py (DRONE_MODEL_PATH).")
print("Cuando tengas tus fotos propias close-range, corre 02_merge_own_photos.py")
print("y despues 03_train.py (el entrenamiento completo con data.yaml combinado)")
print("para mejorar la precision a corta distancia.")
