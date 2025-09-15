import re
END_TRIGGERS = [r"마무리하겠습니다"]
VICTIM_END_LINE = "시뮬레이션을 종료합니다."

def attacker_declared_end(text: str) -> bool:
    norm = text.strip()
    return any(re.search(pat, norm) for pat in END_TRIGGERS)
