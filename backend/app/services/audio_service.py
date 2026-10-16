import logging
import threading
import queue
import json
import time
import re
import numpy as np
import wave
from collections import deque
try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    Model = None
    KaldiRecognizer = None

class AudioService:
    def __init__(self):
        self.logger = logging.getLogger("app.audio")
        self.running = False
        self.audio_thread = None
        self.sample_rate = 16000
        self.q = queue.Queue()
        
        self.model = None
        self.recognizer = None
        
        self.threat_words = [
            "help", "kill", "gun", "bomb", "shoot", "blood", "fire",
            "die", "dead", "knife", "weapon", "attack", "terror"
        ]
        
        # Audio anomaly tracking
        self.last_anomaly_score = 0.0
        self.last_audio_level = 0.0
        self.last_transcription = ""
        self.recent_threat_words = []
        
        # Buffer for saving audio clips (e.g. 60 seconds at 16000Hz)
        # We store raw bytes in chunks. We'll limit the deque size based on expected chunks.
        # sounddevice default chunk size might be variable, but maxlen=1000 should hold enough
        self.audio_buffer = deque(maxlen=2000)
        
        self.init_vosk()

    def init_vosk(self):
        if Model is None:
            self.logger.error("Vosk is not installed. NLP transcription disabled.")
            return
        try:
            # Assumes the model is downloaded to 'model' directory in backend root
            # You can download a tiny english model: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
            self.model = Model("vosk-model-small-en-us")
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.logger.info("Vosk model loaded successfully.")
        except Exception as e:
            self.logger.warning(f"Failed to load Vosk model: {e}")
            self.model = None

    def start(self):
        if self.running:
            return
        if sd is None:
            self.logger.warning("sounddevice not installed — audio analysis disabled (this is OK)")
            return
        try:
            # Quick check: is there any input device at all?
            devices = sd.query_devices()
            has_input = any(
                getattr(d, "max_input_channels", d.get("max_input_channels", 0) if isinstance(d, dict) else 0) > 0
                for d in (devices if isinstance(devices, list) else [devices])
            )
            if not has_input:
                self.logger.warning("No audio input device found — audio analysis disabled (this is OK)")
                return
        except Exception as exc:
            self.logger.warning(f"Cannot query audio devices: {exc} — audio analysis disabled (this is OK)")
            return

        self.running = True
        self.audio_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.audio_thread.start()
        
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()

    def stop(self):
        self.running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)
        if hasattr(self, 'process_thread') and self.process_thread:
            self.process_thread.join(timeout=2.0)

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.logger.warning(f"Sounddevice status: {status}")
        self.q.put(indata.copy())

    def _record_loop(self):
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self._audio_callback, dtype='int16'):
                while self.running:
                    time.sleep(0.1)
        except Exception as e:
            self.logger.warning(f"Audio stream stopped: {e} — continuing without audio (this is OK)")
            self.running = False

    def _process_loop(self):
        while self.running:
            try:
                data = self.q.get(timeout=1.0)
            except queue.Empty:
                continue

            # Store in buffer for clip saving
            self.audio_buffer.append(data.tobytes())

            # 1. NLP Transcription
            if self.recognizer:
                if self.recognizer.AcceptWaveform(data.tobytes()):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        self.last_transcription = text
                        self._detect_threat_words(text)
                else:
                    partial = json.loads(self.recognizer.PartialResult())
                    # can process partial result if needed

            # 2. Audio Anomaly Heuristics (High frequency / energy - e.g. glass break/gunshot)
            # Simple heuristic: calculate RMS energy and Spectral Centroid
            data_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            if len(data_np) == 0:
                continue
                
            rms_energy = np.sqrt(np.mean(data_np**2))
            
            # Simple spectral centroid (proxy for high frequency content)
            spectrum = np.abs(np.fft.rfft(data_np))
            freqs = np.fft.rfftfreq(len(data_np), 1.0 / self.sample_rate)
            
            if np.sum(spectrum) > 0:
                centroid = np.sum(freqs * spectrum) / np.sum(spectrum)
            else:
                centroid = 0
                
            # Heuristic thresholds (needs tuning)
            # Gunshot/Glass break typically have high sudden energy and high spectral centroid
            is_loud = rms_energy > 5000  # arbitrary threshold for int16 max 32768
            is_high_freq = centroid > 3000 # Hz
            
            anomaly_score = 0.0
            if is_loud and is_high_freq:
                anomaly_score = 0.8  # High chance of glass break or gunshot
            elif is_loud:
                anomaly_score = 0.5
                
            self.last_anomaly_score = anomaly_score
            self.last_audio_level = float(rms_energy)

    def _detect_threat_words(self, text: str):
        words = text.lower().split()
        detected = [w for w in words if w in self.threat_words]
        if detected:
            self.recent_threat_words.extend(detected)
            # Keep only recent
            self.recent_threat_words = list(set(self.recent_threat_words[-10:]))
            self.logger.warning(f"Threatening words detected: {detected}")

    def get_current_audio_context(self) -> dict:
        score = self.last_anomaly_score
        # Add to score if recent threat words exist
        if self.recent_threat_words:
            score = max(score, 0.6)
            
        context = {
            "audio_anomaly_score": score,
            "audio_level": self.last_audio_level,
            "transcription": self.last_transcription,
            "threat_words_detected": self.recent_threat_words.copy()
        }
        
        # Reset for next check
        self.last_anomaly_score = 0.0
        self.recent_threat_words.clear()
        return context

    def save_audio_clip(self, filepath: str):
        if not self.audio_buffer:
            return
            
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit (2 bytes)
            wf.setframerate(self.sample_rate)
            # Write all accumulated chunks
            for chunk in list(self.audio_buffer):
                wf.writeframes(chunk)
