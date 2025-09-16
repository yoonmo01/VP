# app/routers/tts.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from google.cloud import texttospeech
import io

#진단용
from pydantic import BaseModel, Field
from typing import Optional
import os

router = APIRouter(prefix="/tts", tags=["tts"])

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voiceName: Optional[str] = "ko-KR-Neural2-A"
    speakingRate: Optional[float] = 1.0
    pitch: Optional[float] = 0.0
    audioEncoding: Optional[str] = "MP3"   # MP3 / LINEAR16 / OGG_OPUS 등


@router.post("/synthesize")
async def synthesize(req: TTSRequest):
    # 0) 요청 로그(필요 시 콘솔 확인)
    # print("TTS req:", req.model_dump())

    # 1) language_code는 voiceName의 앞 2토큰에서 추출 (예: ko-KR-Neural2-A → ko-KR)
    voice_name = req.voiceName or "ko-KR-Neural2-A"
    parts = voice_name.split("-")
    language_code = "-".join(parts[:2]) if len(parts) >= 2 else "ko-KR"

    # 2) 클라이언트 생성 (자격증명 확인)
    # print("GOOGLE_APPLICATION_CREDENTIALS =", os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Init TTS client failed: {e}")

    # 3) 요청 구성
    input_text = texttospeech.SynthesisInput(text=req.text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
    )
    try:
        audio_encoding_enum = getattr(texttospeech.AudioEncoding, req.audioEncoding or "MP3")
    except AttributeError:
        raise HTTPException(status_code=400, detail=f"Invalid audioEncoding: {req.audioEncoding}")

    audio_cfg = texttospeech.AudioConfig(
        audio_encoding=audio_encoding_enum,
        speaking_rate=float(req.speakingRate or 1.0),
        pitch=float(req.pitch or 0.0),
    )

    # 4) 합성 호출
    try:
        resp = client.synthesize_speech(
            request=texttospeech.SynthesizeSpeechRequest(
                input=input_text, voice=voice, audio_config=audio_cfg
            )
        )
    except Exception as e:
        # GCP 인증/결제/API활성화/voiceName 오류 등은 여기서 잡힘
        raise HTTPException(status_code=502, detail=f"Google TTS error: {e}")

    audio_bytes = resp.audio_content or b""
    length = len(audio_bytes)

    # 5) 길이 검증: 0바이트면 명확히 실패로 돌려서 Swagger에서 바로 확인 가능
    if length == 0:
        raise HTTPException(status_code=502, detail="TTS returned 0 bytes (check credentials/project/API enablement/voiceName).")

    # 6) 명시적 Content-Length로 브라우저가 길이를 인식하도록
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Length": str(length)}
    )