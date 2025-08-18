# orchestrator/rules.py
from typing import List, Tuple, Dict, Any

def rule_tag_kor(transcript: str) -> List[Tuple[str, float]]:
    t = (transcript or "").lower()
    rules = [
        ("impersonation.acquaintance", ["지인", "친구", "자녀", "카톡", "메신저", "폰 고장", "급히", "입금"]),
        ("impersonation.prosecutor",   ["검사", "영장", "수사", "금감원", "계좌 연루", "안전계좌"]),
        ("account.safekeeping",        ["안전계좌", "보관", "현금 인출", "무통장", "가상계좌"]),
        ("loan.bait",                  ["대출", "한도", "선입금", "보증금"]),
        ("card.installment",           ["카드", "해외결제", "일시불", "ars", "승인"]),
    ]
    tagged = []
    for code, kws in rules:
        hit = sum(1 for k in kws if k in t)
        score = round(hit / max(1, len(kws)), 3)
        if score >= 0.2:
            tagged.append((code, score))
    return sorted(tagged, key=lambda x: x[1], reverse=True) or [("generic", 0.0)]

def join_transcript_from_logs(logs: List[Dict[str,Any]]) -> str:
    return "\n".join([f"[{l.get('role','?')}] {l.get('content','')}" for l in (logs or [])])

def judge_phishing_from_json(payload: Dict[str, Any]) -> bool:
    """
    아주 단순한 휴리스틱:
    - 공격자 발화에 '입금','송금','가상계좌','무통장','현금' 같은 단어가 있고
    - 피해자가 명확히 거부/신고/중단을 선언하지 않으면 → True
    - 반대로 피해자가 '신고/확인/거부/중단'을 반복하면 → False
    """
    logs = payload.get("logs", []) or []
    txt = join_transcript_from_logs(logs)

    atk_flags = any(k in txt for k in ["입금", "송금", "가상계좌", "무통장", "현금 인출", "상품권"])
    vic_block = any(k in txt for k in ["신고", "경찰", "못 도와", "중단", "거절", "끊"])
    vic_strong_no = any(k in txt for k in ["절대", "못 보내", "안 보내", "안 돼", "속지"])

    if atk_flags and not (vic_block or vic_strong_no):
        return True
    return False
rule_tag = rule_tag_kor