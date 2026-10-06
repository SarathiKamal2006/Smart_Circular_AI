"""NLP core: cleaning, sentence segmentation, tokenisation, entity & fact extraction, summarisation.

Pure-Python / regex based so it works with zero model downloads.  If spaCy is installed
(``python -m spacy download en_core_web_sm``) it is used as an *additional* NER source for
organisations / persons.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

STOPWORDS = set(
    """a an the and or but if then else of to in on at by for with from as is are was were be been being am do does did
    will would shall should can could may might must this that these those it its they them their there here i we you he
    she his her our your my me us not no yes so such than too very also into about over under again further once all any
    both each few more most other some only own same just what which who whom when where why how please kindly""".split()
)

# ------------------------------------------------------------------ cleaning
_ABBR = ["Dr.", "Prof.", "Mr.", "Mrs.", "Ms.", "No.", "St.", "Rs.", "etc.", "e.g.", "i.e.", "Sri.", "Smt.", "Dept."]
_BULLET = re.compile(r"^\s*(?:[-•*·▪●○]|\d{1,2}[.)])\s+")


def normalize_ocr_text(t: str) -> str:
    """Fix common OCR spacing and designation glitches in academic circulars."""
    # Fix honorific spacing: Ms.K -> Ms. K., Dr.S -> Dr. S.
    t = re.sub(r"\b(Dr|Prof|Mr|Mrs|Ms|Sri|Smt)\.([A-Za-z])", r"\1. \2", t)
    # Fix initials: "K .Amsaveni" -> "K. Amsaveni", "RNavedha" -> "R. Navedha"
    t = re.sub(r"\b([A-Z])\s*\.([A-Za-z])", r"\1. \2", t)
    t = re.sub(r"\b([A-Z]{1})([A-Z][a-z]{3,})\b", r"\1. \2", t)
    # Fix designations: AP(SGYCSE -> AP(SG)/CSE, APICSE -> AP/CSE
    t = re.sub(r"\bAP\s*[\(\[]?\s*SG\s*[Y/]?\s*CSE\b", "AP(SG)/CSE", t, flags=re.I)
    t = re.sub(r"\bAP\s*[\(\[]?\s*SG\s*[\)\]Y]?\s*", "AP(SG)/CSE", t, flags=re.I)
    t = re.sub(r"\bAP\s*[I/]\s*CSE\b", "AP/CSE", t, flags=re.I)
    t = re.sub(r"\bAPICSE\b", "AP/CSE", t, flags=re.I)
    # Spacing around commas and colons
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r"\s*:\s*", ": ", t)
    return t


def structure_tabular_data(text: str) -> str:
    """Structure reviewer lists or domain tables if found in text."""
    domain_names = [
        "Cyber Security", "Fullstack Development", "Full Stack Development",
        "Blockchain Technology", "Blockchain", "Artificial Intelligence",
        "Machine Learning", "AI & DS", "Data Science", "Cloud Computing",
        "Internet of Things", "IoT", "Web Development", "Mobile App Development",
        "Deep Learning", "Computer Networks", "Image Processing"
    ]
    if not any(re.search(rf"\b{re.escape(d)}\b", text, re.I) for d in domain_names):
        return text

    present = [d for d in domain_names if re.search(rf"\b{re.escape(d)}\b", text, re.I)]
    if not present:
        return text

    pattern = rf"({'|'.join(re.escape(d) for d in present)})"
    parts = re.split(pattern, text, flags=re.I)
    if len(parts) <= 1:
        return text

    rows = []
    for i in range(1, len(parts), 2):
        dname = parts[i].strip()
        rev = parts[i + 1].strip() if i + 1 < len(parts) else ""
        rev = re.sub(r"^[\s:|\-–]+", "", rev)
        rev = re.sub(r"[\s:|\-–]+$", "", rev)
        if rev:
            rows.append(f"• **{dname}**: {rev}")
        else:
            rows.append(f"• **{dname}**")

    if rows:
        header = parts[0].strip()
        header = re.sub(r"^(problem domain\s*(and|&)?\s*name of the reviewers?|name of the reviewers?)", "", header, flags=re.I).strip()
        res = ""
        if header:
            res += header + "\n\n"
        res += "**Problem Domains & Reviewers:**\n" + "\n".join(rows)
        return res
    return text


def clean_text(t: str) -> str:
    t = t.replace("\r", "\n").replace("\u00a0", " ").replace("\t", " ")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)  # de-hyphenate line breaks
    t = re.sub(r"\b([AaPp])\.[Mm]\.?", lambda m: m.group(1).upper() + "M", t)  # a.m. -> AM
    t = normalize_ocr_text(t)
    t = structure_tabular_data(t)
    t = re.sub(r"[ ]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def split_sentences(text: str) -> list[str]:
    """Sentence segmentation tuned for notices (label lines, bullets, abbreviations)."""
    t = text
    for a in _ABBR:
        t = t.replace(a, a.replace(".", "§"))
    t = re.sub(r"\b([A-Z])\.(?=\s?[A-Z])", r"\1§", t)  # initials: "R. Meenakshi"
    lines = [ln.strip() for ln in t.split("\n")]
    merged: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln:
            i += 1
            continue
        # "Eligible students:" + next line(s)  ->  one unit
        if ln.endswith(":") and i + 1 < len(lines) and lines[i + 1]:
            j, parts, first = i + 1, [], True
            while j < len(lines) and lines[j]:
                is_b = bool(_BULLET.match(lines[j]))
                if not first and not is_b:
                    break
                parts.append(_BULLET.sub("", lines[j]).strip())
                first = False
                j += 1
                if not is_b:
                    break
            merged.append(ln + " " + "; ".join(parts))
            i = j
            continue
        merged.append(_BULLET.sub("", ln))
        i += 1

    out: list[str] = []
    for ln in merged:
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", ln):
            s = s.replace("§", ".").strip()
            if len(s) >= 3:
                out.append(s)
    return out


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def content_tokens(text: str) -> list[str]:
    return [w for w in tokenize(text) if w not in STOPWORDS]


def preprocess(text: str) -> dict:
    """Return the intermediate NLP view shown in the UI ("how the AI read it")."""
    sents = split_sentences(text)
    toks = tokenize(text)
    ct = content_tokens(text)
    return {
        "sentences": len(sents),
        "tokens": len(toks),
        "content_tokens": len(ct),
        "top_keywords": [w for w, _ in Counter(ct).most_common(10)],
    }


def chunk_text(text: str, max_chars: int = 480, overlap: int = 1) -> list[str]:
    sents = split_sentences(text)
    chunks, cur = [], []
    size = 0
    for s in sents:
        if cur and size + len(s) > max_chars:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
            size = sum(len(x) for x in cur)
        cur.append(s)
        size += len(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks or ([text.strip()] if text.strip() else [])


# ----------------------------------------------------------------- entities
_MON = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

_DATE_RANGE2 = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}\.?\s*(?:to|till|until|-|–)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}\.?,?(?:\s+(\d{{4}}))?\b", re.I)
_DATE_RANGE = re.compile(rf"\b(\d{{1,2}})\s*(?:-|–|to)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}\.?,?(?:\s+(\d{{4}}))?\b", re.I)
_DATE_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s\-]+(?:of\s+)?{_MON}\.?,?(?:\s+(\d{{4}}))?\b", re.I)
_DATE_MDY = re.compile(rf"\b{_MON}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", re.I)
_DATE_NUM = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")

_TIME = re.compile(
    r"\b(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?m\b\.?|\b([01]?\d|2[0-3]):([0-5]\d)\s*(?:hrs|hours)\b", re.I
)
_VENUE_LABEL = re.compile(r"(?im)^\s*(?:venue|location|place)\s*[:\-–]\s*(.+?)\s*$")
_VENUE_INLINE = re.compile(
    r"(?i:\b(?:in|at)\s+(?:the\s+)?)((?:[A-Z][\w&'\-]*\s+){0,4}"
    r"(?:Hall|Auditorium|Lab|Laboratory|Block|Room|Centre|Center|Theatre|Theater|Ground|Library|Studio|Campus|Seminar Hall)"
    r"(?:\s*[-#]?\s*(?:\d+[A-Z]?|[A-D]\b))?)"
)
_DEPT = re.compile(r"\bDepartment of ([A-Z][A-Za-z&]+(?:\s(?:and|&|of)\s[A-Z][A-Za-z&]+|\s[A-Z][A-Za-z&]+){0,4})")
_DEPT_ABBR = re.compile(r"\b(CSE|ECE|EEE|IT|AIDS|AI&DS|AIML|MECH|CIVIL|MBA|MCA|BCA|BBA|CYBER ?SECURITY)\b")
_YEAR = re.compile(r"\b(first|second|third|final|fourth|1st|2nd|3rd|4th)[\s\-]*year\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_MONEY = re.compile(r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?(?:/-)?", re.I)
_URL = re.compile(r"https?://[^\s)]+|www\.[^\s)]+")


def _mk_date(d, mon, y, today: date | None = None):
    try:
        month = _MONTHS[mon[:3].lower()]
        day = int(d)
        inferred = False
        today = today or date.today()
        if y:
            year = int(y)
        else:
            year, inferred = today.year, True
            if date(year, month, day) < today:
                year += 1
        return date(year, month, day).isoformat(), inferred
    except Exception:
        return None, False


def find_dates(text: str) -> list[dict]:
    found: list[dict] = []
    taken: list[tuple[int, int]] = []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    def add(m, iso, inferred=False):
        taken.append((m.start(), m.end()))
        found.append({"text": m.group(0).strip(" ,"), "iso": iso, "inferred_year": inferred, "pos": m.start()})

    for m in _DATE_RANGE2.finditer(text):
        if free(*m.span()):
            iso, inf = _mk_date(m.group(1), m.group(2), m.group(5))
            add(m, iso, inf)
    for m in _DATE_RANGE.finditer(text):
        if free(*m.span()):
            iso, inf = _mk_date(m.group(1), m.group(3), m.group(4))
            add(m, iso, inf)
    for m in _DATE_DMY.finditer(text):
        if free(*m.span()):
            iso, inf = _mk_date(m.group(1), m.group(2), m.group(3))
            add(m, iso, inf)
    for m in _DATE_MDY.finditer(text):
        if free(*m.span()):
            iso, inf = _mk_date(m.group(2), m.group(1), m.group(3))
            add(m, iso, inf)
    for m in _DATE_NUM.finditer(text):
        if free(*m.span()):
            try:
                iso = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except ValueError:
                iso = None
            add(m, iso)
    return sorted(found, key=lambda d: d["pos"])


def find_times(text: str) -> list[str]:
    out = []
    for m in _TIME.finditer(text):
        if m.group(3):
            h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).upper() + "M"
            if 1 <= h <= 12:
                out.append(f"{h}:{mi:02d} {ap}")
        else:
            out.append(f"{int(m.group(4)):02d}:{m.group(5)} hrs")
    return out


def find_venues(text: str) -> list[str]:
    out = [m.group(1).strip(" .,") for m in _VENUE_LABEL.finditer(text)]
    out += [m.group(1).strip(" .,") for m in _VENUE_INLINE.finditer(text)]
    seen, uniq = set(), []
    for v in out:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append(v)
    return uniq


def _spacy_entities(text: str) -> dict:
    try:
        import spacy  # type: ignore

        global _NLP
        if "_NLP" not in globals():
            _NLP = spacy.load("en_core_web_sm")
        doc = _NLP(text[:20000])
        res = {"organizations": [], "persons": []}
        for e in doc.ents:
            if e.label_ == "ORG":
                res["organizations"].append(e.text)
            elif e.label_ == "PERSON":
                res["persons"].append(e.text)
        return {k: list(dict.fromkeys(v))[:8] for k, v in res.items()}
    except Exception:
        return {}


def extract_entities(text: str) -> dict:
    dates = find_dates(text)
    ents = {
        "dates": list(dict.fromkeys(d["text"] for d in dates)),
        "times": list(dict.fromkeys(find_times(text))),
        "venues": find_venues(text),
        "departments": list(
            dict.fromkeys([m.group(1) for m in _DEPT.finditer(text)] + [m.group(1) for m in _DEPT_ABBR.finditer(text)])
        ),
        "years": list(dict.fromkeys(m.group(0).title() for m in _YEAR.finditer(text))),
        "emails": list(dict.fromkeys(_EMAIL.findall(text))),
        "phones": list(dict.fromkeys(p.strip() for p in _PHONE.findall(text))),
        "money": list(dict.fromkeys(_MONEY.findall(text))),
        "links": list(dict.fromkeys(_URL.findall(text))),
    }
    ents.update(_spacy_entities(text))
    return {k: v for k, v in ents.items() if v}


# ------------------------------------------------------------------- facts
_CAT_RX = {
    "deadline": re.compile(r"\b(deadline|last date|last day|due date|due by|on or before|no later than|not later than|before|till|until|cut-?off|closes?|by)\b", re.I),
    "eligibility": re.compile(r"\b(eligible|eligibility|open to|applicable (?:to|for)|criteria|all (?:the )?\w+(?:-\w+)? ?(?:year)? students|final[- ]year|students of|who can|intended for|meant for|only for)\b", re.I),
    "registration": re.compile(r"\b(regist\w*|enrol\w*|apply|application|sign[- ]?up|google form|link)\b", re.I),
    "contact": re.compile(r"\b(contact|e-?mail|phone|call|coordinator|reach|queries|helpline|incharge|in-charge)\b", re.I),
    "instructions": re.compile(r"\b(bring|carry|must|mandatory|required|dress code|id card|instructions?|compulsory|laptop|resume|prohibited)\b", re.I),
    "fee": re.compile(r"\b(fee|fees|payable|amount|charges?|fine|penalty)\b|₹|\bRs\.?\b", re.I),
}
_ISSUE_RX = re.compile(r"\b(issued|circulated|dated|posted on|ref(?:erence)?\.? ?no|circular (?:no|date))\b", re.I)
_EVENT_DATE_RX = re.compile(r"\b(date|scheduled|conducted|organi[sz]ed|held|will be|commence|start|begin|programme|workshop|seminar|exam|examination|drive|event|on)\b", re.I)


_LABEL_SKIP = re.compile(r"(?i)^\s*(subject|sub|re|ref(?:erence)?(?: no)?)\s*[:\-–]")


def categorize_sentence(s: str) -> list[str]:
    cats = []
    has_date = bool(find_dates(s))
    has_time = bool(find_times(s))
    if _CAT_RX["deadline"].search(s) and (has_date or re.search(r"deadline|last date|last day", s, re.I)):
        if not (_ISSUE_RX.search(s) and not re.search(r"deadline|last date|before", s, re.I)):
            cats.append("deadline")
    if has_date and "deadline" not in cats and not _ISSUE_RX.search(s):
        cats.append("event_date")
    if has_time:
        cats.append("event_time")
    if find_venues(s) or re.search(r"\b(venue|location|held at|report to|reporting)\b", s, re.I):
        cats.append("location")
    for k in ("eligibility", "registration", "contact", "instructions", "fee"):
        if _CAT_RX[k].search(s):
            cats.append(k)
    return cats


def extract_title(text: str, filename: str = "") -> str:
    m = re.search(r"(?im)^\s*(?:subject|sub|re)\s*[:\-–]\s*(.+?)\s*$", text)
    if m:
        return _tidy(m.group(1))
    skip = re.compile(r"(?i)^(circular|notice|notification|announcement|ref\b|date\b|no\b|to\b|from\b|dear|office of)")
    org = re.compile(r"(?i)\b(college|university|institute of|autonomous|affiliated|approved by)\b")
    for line in text.split("\n"):
        s = line.strip()
        if 6 <= len(s) <= 120 and re.search(r"[A-Za-z]{3}", s) and not skip.match(s) and not org.search(s) and not find_dates(s):
            return _tidy(s)
    stem = re.sub(r"[_\-]+", " ", filename.rsplit(".", 1)[0]).strip()
    return stem.title() or "Untitled circular"


def _tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" .:-–")
    return s[:140]


def event_phrase(title: str) -> str:
    t = re.sub(r"(?i)^(circular|notice|notification)\s*(on|regarding|for|about)?\s*[:\-]?\s*", "", title).strip()
    t = re.sub(r"(?i)\s*[-–]?\s*(circular|notice)$", "", t).strip() or title
    words = [w if (w.isupper() and len(w) > 1) else w.lower() for w in t.split()]
    return "the " + " ".join(words)


def build_facts(text: str, filename: str = "") -> dict:
    title = extract_title(text, filename)
    sents = split_sentences(text)
    cats: dict[str, list[str]] = {}
    sent_dates: list[tuple[str, list[dict], list[str]]] = []
    for s in sents:
        cs = [] if _LABEL_SKIP.match(s) else categorize_sentence(s)
        for c in cs:
            cats.setdefault(c, []).append(s)
        sent_dates.append((s, find_dates(s), cs))

    # primary event date: best scoring sentence containing a date that isn't a deadline / issue date
    best, best_score = None, -99
    for s, ds, cs in sent_dates:
        if not ds or "deadline" in cs:
            continue
        score = 0
        if _EVENT_DATE_RX.search(s):
            score += 2
        if _ISSUE_RX.search(s) or re.match(r"(?i)^\s*ref", s):
            score -= 3
        if "event_time" in cs or "location" in cs:
            score += 1
        if score > best_score:
            best, best_score = (s, ds[0]), score
    event_date = None
    if best:
        event_date = {"text": best[1]["text"], "iso": best[1]["iso"], "sentence": best[0]}

    deadline = None
    for s, ds, cs in sent_dates:
        if "deadline" in cs and ds:
            low = s.lower()
            label = (
                "registration" if "regist" in low else "fee payment" if re.search(r"fee|pay", low)
                else "application" if "appl" in low else "submission" if "submit" in low else ""
            )
            deadline = {"text": ds[-1]["text"] if "before" in low or "by" in low else ds[0]["text"], "iso": ds[-1]["iso"] if "before" in low or "by" in low else ds[0]["iso"], "sentence": s, "label": label}
            break

    # time: start / end taken from event-ish sentences (never from contact / deadline lines)
    cand = ([event_date["sentence"]] if event_date else []) + [
        s for s, _, cs in sent_dates if find_times(s) and "deadline" not in cs and "contact" not in cs
    ]
    t_start = t_end = None
    for i, s in enumerate(cand):
        ts = find_times(s)
        if not ts:
            continue
        if t_start is None:
            t_start = ts[0]
            if len(ts) >= 2 and ts[1] != t_start:
                t_end = ts[1]
                break
        elif t_end is None and re.search(r"\b(to|till|until|end|ends|conclude|run)\b", s, re.I):
            other = [t for t in ts if t != t_start]
            if other:
                t_end = other[0]
                break
    time_text = f"{t_start} to {t_end}" if t_start and t_end else t_start

    venues = find_venues(text)
    ents = extract_entities(text)
    facts = {
        "title": title,
        "phrase": event_phrase(title),
        "department": (ents.get("departments") or [None])[0],
        "event_date": event_date,
        "time": time_text,
        "time_start": t_start,
        "time_end": t_end,
        "venue": venues[0] if venues else None,
        "deadline": deadline,
        "cats": {k: v[:6] for k, v in cats.items()},
        "emails": ents.get("emails", []),
        "phones": ents.get("phones", []),
        "entities": ents,
        "stats": preprocess(text),
    }
    return facts


# ------------------------------------------------------------ summarisation
def summarize(text: str, n: int = 3) -> str:
    sents = [
        s if s.endswith((".", "!", "?")) else s + "."
        for s in split_sentences(text)
        if len(s) > 25 and not re.match(r"(?i)^(ref|date|subject|sub|issued)\b", s) and not re.match(r"^[A-Z][\w\s/&-]{2,30}:\s", s)
    ]
    if len(sents) <= n:
        return " ".join(sents)
    freq = Counter(content_tokens(text))
    top = max(freq.values()) if freq else 1
    scored = []
    for i, s in enumerate(sents):
        toks = content_tokens(s)
        if not toks:
            continue
        sc = sum(freq[t] / top for t in toks) / (len(toks) ** 0.6)
        if find_dates(s) or find_times(s):
            sc *= 1.25
        if _CAT_RX["contact"].search(s):
            sc *= 0.5
        if i < 2:
            sc *= 1.15
        scored.append((sc, i, s))
    best = sorted(scored, reverse=True)[:n]
    return " ".join(s for _, _, s in sorted(best, key=lambda x: x[1]))


def suggest_questions(facts: dict) -> list[str]:
    cats = facts.get("cats", {})
    q = []
    if facts.get("event_date"):
        q.append("When is it?")
    if facts.get("venue"):
        q.append("Where will it be held?")
    if facts.get("time") and not facts.get("event_date"):
        q.append("What time does it start?")
    if "eligibility" in cats:
        q.append("Who can attend?")
    if facts.get("deadline"):
        q.append("What is the last date to register?")
    elif "registration" in cats:
        q.append("How do I register?")
    if "instructions" in cats:
        q.append("What should I bring?")
    if "fee" in cats:
        q.append("How much is the fee?")
    if "contact" in cats:
        q.append("Who should I contact?")
    q.append("Summarize this circular")
    return q[:6]
