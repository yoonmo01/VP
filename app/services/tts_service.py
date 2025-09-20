from google.cloud import texttospeech

def synthesize(text: str,
               voice_name: str = "ko-KR-Neural2-A",
               speaking_rate: float = 1.0,
               pitch: float = 0.0,
               audio_encoding: str = "MP3") -> bytes:
    if not text or not text.strip():
        raise ValueError("text is empty")

    client = texttospeech.TextToSpeechClient()  # ADC 사용(서비스 계정)
    input_text = texttospeech.SynthesisInput(text=text)
    language_code = "-".join(voice_name.split("-")[:2]) if "-" in voice_name else "ko-KR"

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
    )
    audio_cfg = texttospeech.AudioConfig(
        audio_encoding=getattr(texttospeech.AudioEncoding, audio_encoding),
        speaking_rate=speaking_rate,
        pitch=pitch,
    )

    resp = client.synthesize_speech(
        request=texttospeech.SynthesizeSpeechRequest(
            input=input_text, voice=voice, audio_config=audio_cfg
        )
    )
    return resp.audio_content
