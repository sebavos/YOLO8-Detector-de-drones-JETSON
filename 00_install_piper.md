# Instalación de Piper TTS (voz en español, local, rápida)

Piper corre 100% local (sin internet, a diferencia de gTTS) y es liviano —
ideal para latencia baja en un HUD en tiempo real.

## 1. Instalar el paquete

En la PC ground-station (donde corre tu script principal, la RTX 4070):

```bash
pip install piper-tts --break-system-packages
```

Esto instala el comando `piper` y la librería Python `piper.voice`.

## 2. Descargar un modelo de voz en español

Los modelos están en Hugging Face: https://huggingface.co/rhasspy/piper-voices

Recomendado para tu caso (buena calidad, no muy pesado): **es_ES-davefx-medium**

```bash
mkdir -p piper_voices
cd piper_voices

# el modelo de voz (~60MB)
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx

# el config del modelo (obligatorio, va junto al .onnx)
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json
```

Alternativas si querés otra voz (todas en el mismo repo, cambiando la ruta):
- `es_ES-carlfm-x_low` -> más liviano, algo más robótico
- `es_MX-claude-high` -> español latino, más pesado pero mejor calidad
- `es_AR-daniela-high` -> acento argentino

## 3. Probar que funciona

```bash
echo "Dron detectado a las tres en punto" | piper \
  --model piper_voices/es_ES-davefx-medium.onnx \
  --output_file test.wav

# reproducir (Linux)
aplay test.wav
# o si no tenés aplay:
python3 -c "import playsound; playsound.playsound('test.wav')"
```

Si escuchás la frase en español, estás listo. Actualizá `PIPER_MODEL_PATH`
en `05_ground_station.py` con la ruta real de tu `.onnx`.

## Notas
- La primera síntesis después de cargar el modelo tarda un poco más
  (carga en memoria); las siguientes son casi instantáneas.
- Si en el futuro corrés esto en la Jetson en vez de la PC, existen
  builds ARM64 de Piper — avisame y te dejo esa variante.
