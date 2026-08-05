"""

Descarga el dataset base "Drones YOLO11 A" desde Roboflow Universe.

1. Andá a https://universe.roboflow.com/drone-a7lpy/drones-yolo11-a

2. Click en "Download Dataset" -> formato "YOLOv8" (sirve igual para v11/v8)

3. Elegí "show download code" en vez de descargar el zip -> te va a dar tu API_KEY

   (o creá una cuenta gratis en roboflow.com si no tenés)

4. Pegá tu ROBOFLOW_API_KEY abajo y corré este script

pip install roboflow --break-system-packages

"""

from roboflow import Roboflow

ROBOFLOW_API_KEY = ""  # <-- reemplazar

rf = Roboflow(api_key=ROBOFLOW_API_KEY)

project = rf.workspace("drone-a7lpy").project("drones-yolo11-a")

version = project.version(1)  # revisá en la web cuál es la versión más nueva

dataset = version.download("yolov8", location="../data/base_dataset")

print("Dataset descargado en ../data/base_dataset")

print("Estructura esperada: train/, valid/, test/ cada uno con images/ y labels/")