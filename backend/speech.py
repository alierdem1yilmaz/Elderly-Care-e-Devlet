# Sahiplik: Kişi 1 (ali-erdem)
#
# Mikrofon girdisini (sesli yazma / STT) YEREL bir Whisper modeliyle yazıya çevirir.
# Neden bu şekilde: Electron'un kullandığı Chromium'da tarayıcının yerleşik
# webkitSpeechRecognition'ı Google'ın kendi (lisanslı) API anahtarını gerektiriyor —
# bu anahtar Electron'da bulunmadığı için o özellik hep "network" hatasıyla
# başarısız oluyordu. Bu modül API anahtarı/hesap/internet gerektirmez; ses tamamen
# bu makinede işlenir.
#
# İlk çalıştırmada model indirilir (~150MB, "base" boyutu) ve ~/.cache içinde
# saklanır — sonraki çalıştırmalar hızlıdır. Model, backend başlarken bir kere
# yüklenir (bkz. main.py::lifespan -> warm_up()) ki ilk gerçek istek beklemesin.

import os
import tempfile

from faster_whisper import WhisperModel

_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def warm_up() -> None:
    """Backend başlarken modeli önceden yükler — demo sırasında ilk mikrofon
    denemesinde sürpriz bir indirme/yükleme beklemesi olmasın diye."""
    _get_model()


def transcribe_audio(audio_bytes: bytes, filename_hint: str = "recording.webm") -> str:
    """Ham ses baytlarını (tarayıcının MediaRecorder'ından gelen webm/opus vb.)
    Türkçe metne çevirir. av/ctranslate2 çözme işini kendi içinde yapar, ayrıca
    sistemde ffmpeg kurulu olmasına gerek yoktur."""
    suffix = os.path.splitext(filename_hint)[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        segments, _info = _get_model().transcribe(tmp.name, language="tr")
        return " ".join(segment.text.strip() for segment in segments).strip()
