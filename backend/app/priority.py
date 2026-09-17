import re

URGENT = re.compile(r"\b(urgent|asap|blocker|production|deadline|today|immediately)\b", re.I)


def score(sender: str, subject: str, body: str) -> tuple[float, str]:
    text = f"{subject} {body}"
    points = len(URGENT.findall(text)) * 20
    if any(x in sender.lower() for x in ("manager", "customer", "client", "ceo")):
        points += 25
    if "p1" in text.lower() or "critical" in text.lower():
        points += 30
    points = min(float(points), 100)
    return points, "critical" if points >= 70 else "high" if points >= 40 else "normal"
