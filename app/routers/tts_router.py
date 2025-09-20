# app/routers/tts_router.py
from __future__ import annotations
import os, io, base64, re, wave
from typing import List, Optional, Literal, Union, Tuple, Set
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 환경 설정
load_dotenv()
cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "../service-account-key.json")
if cred_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

# Google TTS 클라이언트
from google.cloud import texttospeech
tts_client = texttospeech.TextToSpeechClient()

router = APIRouter(prefix="/tts", tags=["TTS"])

# 더미 대화 데이터
DUMMY_DIALOGUE = [
    {"speaker": "offender", "text": "고객님, 보안 위험이 감지되어 즉시 본인 인증이 필요합니다."},
    {"speaker": "victim",   "text": "네? 어떤 문제인가요? 인증을 어떻게 하면 되나요?"},
    {"speaker": "offender", "text": "앱 스토어에서 보안 인증 앱을 설치하시고, 안내에 따라 로그인을 진행해 주세요."},
    {"speaker": "victim",   "text": "해결이 됐나요?"},
    {"speaker": "offender", "text": "안되면 깔끔히 다른 방법을 모색해야지요."},
]

VOICE_BY_SPEAKER = {
    "offender": {"languageCode": "ko-KR", "voiceName": "ko-KR-Standard-B"},
    "victim":   {"languageCode": "ko-KR", "voiceName": "ko-KR-Standard-A"},
}

# 연령·성별 기반 음성 매핑
VOICE_BY_AGE_GENDER = {
    ("20s", "female"): "ko-KR-Standard-A",
    ("30s", "female"): "ko-KR-Standard-A",
    ("20s", "male")  : "ko-KR-Standard-C",
    ("30s", "male")  : "ko-KR-Standard-C",
    ("40s", "female"): "ko-KR-Standard-B",
    ("50s", "female"): "ko-KR-Standard-B",
    ("60s", "female"): "ko-KR-Standard-B",
    ("40s", "male")  : "ko-KR-Standard-D",
    ("50s", "male")  : "ko-KR-Standard-D",
    ("60s", "male")  : "ko-KR-Standard-D",
}

# 가해자용 대체 음성 리스트 (충돌 방지용)
OFFENDER_ALTERNATES = [
    "ko-KR-Standard-A",
    "ko-KR-Standard-B",
    "ko-KR-Standard-C",
    "ko-KR-Standard-D",
]

# Pydantic 모델들
class WordTiming(BaseModel):
    token: str
    charCount: int
    startSec: float
    durationSec: float

class TtsResponse(BaseModel):
    audioContent: str
    contentType: str
    totalDurationSec: float
    charTimeSec: float
    words: List[WordTiming]

class DialogueTurn(BaseModel):
    speaker: str
    text: str
    voiceName: Optional[str] = None
    languageCode: Optional[str] = None
    age_group: Optional[str] = None   # e.g. "20s","30s","40s","50s","60s"
    gender: Optional[str] = None      # "male" or "female"

class TtsRequest(BaseModel):
    mode: Literal["single", "dialogue"] = "single"
    text: Optional[str] = Field(None)
    languageCode: str = "ko-KR"
    voiceName: str = "ko-KR-Standard-A"
    speakingRate: float = 1.0
    pitch: float = 0.0
    audioEncoding: str = "LINEAR16"
    dialogue: Optional[List[DialogueTurn]] = None

class DialogueItem(BaseModel):
    speaker: str
    text: str
    voiceName: str
    languageCode: str
    audioContent: str
    contentType: str
    totalDurationSec: float
    charTimeSec: float
    words: List[WordTiming]

class DialogueResponse(BaseModel):
    items: List[DialogueItem]
    note: str = "Word timings are heuristic (char-proportional)."

# 유틸리티 함수들
CHAR_PATTERN = re.compile(r"[가-힣A-Za-z0-9]")

def count_chars(token: str) -> int:
    return len(CHAR_PATTERN.findall(token))

def wav_duration_sec(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return w.getnframes() / float(w.getframerate())

def wrap_pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """raw PCM (linear16) bytes → WAV 파일 bytes"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)
    return buf.getvalue()

def synthesize_wav_and_timings(
    text: str,
    languageCode: str,
    voiceName: str,
    speakingRate: float = 1.0,
    pitch: float = 0.0,
    sample_rate_hz: int = 24000,
) -> Tuple[bytes, float, float, List[WordTiming]]:
    """
    Google TTS 호출 → WAV bytes 확보(이미 WAV면 그대로, RAW면 래핑)
    → 길이 및 글자 비례 타이밍 반환.
    """
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=languageCode, name=voiceName)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=speakingRate,
        pitch=pitch,
        sample_rate_hertz=sample_rate_hz,
    )

    resp = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    audio_bytes = resp.audio_content or b""

    # 감지: 이미 WAV 컨테이너인지 확인 (RIFF header)
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        wav_bytes = audio_bytes
    else:
        # raw PCM → WAV로 래핑
        wav_bytes = wrap_pcm_to_wav(audio_bytes, sample_rate=sample_rate_hz, channels=1, sampwidth=2)

    total_sec = wav_duration_sec(wav_bytes)

    # 토큰화: 공백으로 분리하고 빈 토큰 제거
    tokens = [tk for tk in re.split(r"\s+", text.strip()) if tk != ""]
    counts = [count_chars(tk) for tk in tokens]
    total_chars = sum(counts)
    words: List[WordTiming] = []

    # 글자 수가 0인 경우(숫자/기호만 있는 경우 등) — 균등 분배
    if total_chars <= 0 or not tokens:
        per = total_sec / max(len(tokens), 1) if tokens else 0.0
        acc = 0.0
        for tk in tokens:
            words.append(WordTiming(token=tk, charCount=0, startSec=round(acc, 6), durationSec=round(per, 6)))
            acc += per
        return wav_bytes, total_sec, 0.0, words

    # 글자 비례 계산
    char_time = total_sec / total_chars
    acc = 0.0
    for tk, cc in zip(tokens, counts):
        dur = cc * char_time
        words.append(WordTiming(token=tk, charCount=cc, startSec=acc, durationSec=dur))
        acc += dur

    # 보정: 누적 오차로 인한 잔여 시간을 마지막 단어에 더함
    if len(words) > 0:
        last = words[-1]
        last_end = last.startSec + last.durationSec
        epsilon = 1e-6
        if total_sec - last_end > epsilon:
            extra = total_sec - last_end
            last.durationSec += extra

    # 응답용 반올림
    for w in words:
        w.startSec = round(w.startSec, 6)
        w.durationSec = round(w.durationSec, 6)

    char_time = round(char_time, 9)
    return wav_bytes, total_sec, char_time, words

def choose_voice_name(turn: DialogueTurn, default: str = "ko-KR-Standard-A", taken_voices: Optional[Set[str]] = None, role: Optional[str] = None) -> str:
    """
    우선순위: explicit turn.voiceName -> age+gender 매핑 -> VOICE_BY_SPEAKER(role) -> default
    taken_voices가 주어지고 role == 'offender'인 경우 충돌 시 OFFENDER_ALTERNATES에서 대체 선택.
    """
    # 1) explicit override
    if turn.voiceName:
        candidate = turn.voiceName
    else:
        # 2) age+gender 매핑 우선
        age = (turn.age_group or "").strip()
        gender = (turn.gender or "").strip().lower()
        if age and gender:
            candidate = VOICE_BY_AGE_GENDER.get((age, gender), None)
        else:
            candidate = None

        # 3) VOICE_BY_SPEAKER 기반 (role 매핑)
        if not candidate and role:
            base = VOICE_BY_SPEAKER.get(role)
            if base:
                candidate = base.get("voiceName")
        # 4) 기본값
        if not candidate:
            candidate = default

    # 가해자 충돌 방지: taken_voices와 동일하면 대체 선택
    if role == "offender" and taken_voices:
        if candidate in taken_voices:
            # 후보에서 첫 사용 가능한 음성을 선택
            for alt in OFFENDER_ALTERNATES:
                if alt not in taken_voices and alt != candidate:
                    return alt
            # 모든 후보가 충돌하면 그냥 candidate 반환
            return candidate

    return candidate

# API 엔드포인트
@router.post("/synthesize", response_model=Union[TtsResponse, DialogueResponse])
def synthesize(req: TtsRequest):
    """TTS 합성 엔드포인트 - 단일 텍스트 또는 대화 모드 지원"""
    
    if req.mode == "dialogue":
        turns = req.dialogue if (req.dialogue and len(req.dialogue) > 0) else [DialogueTurn(**t) for t in DUMMY_DIALOGUE]
        items: List[DialogueItem] = []

        # 피해자(들)의 음성 집합을 미리 계산해 가해자 충돌을 예방
        victim_voices: Set[str] = set()
        for t in turns:
            try:
                if t.speaker == "victim":
                    v = choose_voice_name(t, default="ko-KR-Standard-A", role="victim")
                    if v:
                        victim_voices.add(v)
            except Exception:
                pass

        for turn in turns:
            spk = turn.speaker
            txt = turn.text
            base = VOICE_BY_SPEAKER.get(spk, {"languageCode":"ko-KR","voiceName":"ko-KR-Standard-A"})
            lang = turn.languageCode or base["languageCode"]

            # 가해자(offender)는 피해자와 음성이 겹치지 않도록 taken_voices로 피해자 음성 전달
            if spk == "offender":
                vname = choose_voice_name(turn, default=base["voiceName"], taken_voices=victim_voices, role="offender")
            else:
                # 피해자 또는 일반 화자
                vname = choose_voice_name(turn, default=base["voiceName"], role=spk)

            try:
                wav_bytes, total_sec, char_time, words = synthesize_wav_and_timings(
                    text=txt, languageCode=lang, voiceName=vname,
                    speakingRate=req.speakingRate, pitch=req.pitch, sample_rate_hz=24000
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"대화 TTS 실패: {e}")

            items.append(DialogueItem(
                speaker=spk,
                text=txt,
                voiceName=vname,
                languageCode=lang,
                audioContent=base64.b64encode(wav_bytes).decode("utf-8"),
                contentType="audio/wav",
                totalDurationSec=round(total_sec, 3),
                charTimeSec=round(char_time, 6),
                words=words
            ))
        return DialogueResponse(items=items)

    # 단건 모드
    text = (req.text or "안녕하세요. 제 이름은 구글입니다. 오늘은 텍스트 음성 변환을 테스트합니다.").strip()
    try:
        wav_bytes, total_sec, char_time, words = synthesize_wav_and_timings(
            text=text, languageCode=req.languageCode, voiceName=req.voiceName,
            speakingRate=req.speakingRate, pitch=req.pitch, sample_rate_hz=24000
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS 요청 실패: {e}")

    return TtsResponse(
        audioContent=base64.b64encode(wav_bytes).decode("utf-8"),
        contentType="audio/wav",
        totalDurationSec=round(total_sec, 3),
        charTimeSec=round(char_time, 6),
        words=words
    )

@router.get("/voices")
def list_voices():
    """사용 가능한 TTS 음성 목록 반환"""
    try:
        voices = tts_client.list_voices()
        korean_voices = [
            {
                "name": voice.name,
                "language_code": voice.language_codes[0],
                "ssml_gender": voice.ssml_gender.name,
                "natural_sample_rate": voice.natural_sample_rate_hertz
            }
            for voice in voices.voices
            if "ko-KR" in voice.language_codes[0]
        ]
        return {"voices": korean_voices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"음성 목록 조회 실패: {e}")

@router.get("/health")
def tts_health():
    """TTS 서비스 헬스체크"""
    try:
        # 간단한 테스트 합성
        synthesis_input = texttospeech.SynthesisInput(text="테스트")
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name="ko-KR-Standard-A"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        return {"status": "healthy", "service": "google-tts"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}