from datetime import date
import re


def evidence_value(label,value):
    if re.fullmatch(r"(?:project [a-z] )?(?:duration minutes|sessions|capacity|budget dollars)",label):
        return bool(re.fullmatch(r"[0-9]{1,5}",value))
    if re.fullmatch(r"(?:project [a-z] )?deadline",label):
        try:
            return date.fromisoformat(value).isoformat()==value
        except ValueError:
            return False
    if label in ("residence","job","education"):
        return bool(re.fullmatch(r"[A-Z][a-z]{1,20}(?: [A-Z][a-z]{1,20}){0,2}",value))
    return False
