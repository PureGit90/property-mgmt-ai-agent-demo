"""Property-management agent (demo): lead qualification and maintenance triage.

Runs on plain rules with mock property data so it works with no keys. In
production the same two functions sit behind a webhook (Tenant Cloud, Zapier or
Make) and the classification step is handed to an LLM, with these rules kept
as the guardrails.
"""
import re
from datetime import date

PROPERTIES = [
    {"id": "P1", "name": "Lakeview Studio", "type": "mid-term", "rent": 1650, "max_guests": 2, "pets": False, "min_stay_days": 30, "available": "2026-10-15"},
    {"id": "P2", "name": "Maple 2BR", "type": "mid-term", "rent": 2400, "max_guests": 4, "pets": True, "min_stay_days": 30, "available": "2026-10-01"},
    {"id": "P3", "name": "Beach Bungalow", "type": "short-term", "rent": 190, "max_guests": 5, "pets": False, "min_stay_days": 3, "available": "2026-10-05"},
]

VENDORS = {"plumbing": "Sam's Plumbing", "electrical": "Bright Electric", "hvac": "CoolAir HVAC",
           "appliance": "Fixit Appliance", "gas": "Owner + gas utility emergency line", "pest": "Green Pest Control", "lockout": "Handyman (on call)", "other": "Handyman (on call)"}

EXAMPLE_INQUIRIES = {
    "Hot lead (Furnished Finder)": "Hi! Travel nurse here, need a place from Oct 20 for 3 months. Just me, budget up to $1800/month. No pets. Is the studio still available?",
    "Warm lead (Zillow)": "Looking for something for me and my partner plus our dog, about 2 months starting mid November. Budget around $2000.",
    "Cold lead (Airbnb)": "Hey do you have anything this weekend for 6 people? Budget $100 a night",
    "Vague question": "Is this still available?",
}
EXAMPLE_REQUESTS = {
    "Emergency: water leak": "There is water pouring from under the kitchen sink and it is flooding the floor!!",
    "Urgent: no AC": "The AC stopped working and it is 90 degrees in the apartment.",
    "Routine: dripping tap": "The bathroom faucet has a slow drip, no rush.",
    "Emergency: gas smell": "I smell gas near the stove, not sure what to do",
    "Lockout": "I locked myself out and my keys are inside",
}


def _months(text):
    m = re.search(r"(\d+)\s*(month|week|night|day)s?", text, re.I)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * {"month": 30, "week": 7, "night": 1, "day": 1}[unit]


def parse_inquiry(text):
    t = text.lower()
    guests = 1
    if re.search(r"\b(me and my|my partner|couple|two of us)\b", t):
        guests = 2
    g = re.search(r"(\d+)\s*(people|guests|adults|of us)", t)
    if g:
        guests = int(g.group(1))
    if re.search(r"\bplus our|and (my|our) (family|kids)\b", t) and guests < 3 and "partner" not in t:
        guests += 1
    budget = re.search(r"\$\s?(\d[\d,]*)", text)
    return {
        "stay_days": _months(text),
        "guests": guests,
        "budget": int(budget.group(1).replace(",", "")) if budget else None,
        "pets": bool(re.search(r"\b(dog|cat|pet)s?\b", t)) and not re.search(r"no pets", t),
        "has_dates": bool(re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|weekend|mid|next week|starting", t)),
    }


def qualify(text):
    f = parse_inquiry(text)
    reasons, score = [], 0
    over_budget = None
    stay = f["stay_days"]
    kind = "short-term" if (stay is not None and stay < 30) or "weekend" in text.lower() else "mid-term"
    pool = [p for p in PROPERTIES if p["type"] == kind and f["guests"] <= p["max_guests"] and (p["pets"] or not f["pets"])]
    best = None
    if f["has_dates"]:
        score += 1; reasons.append("gave move-in timing")
    else:
        reasons.append("no dates given")
    if stay is not None:
        score += 1; reasons.append(f"stay length stated ({stay} days)")
    else:
        reasons.append("no stay length given")
    if f["budget"] is not None:
        fits = [p for p in pool if f["budget"] >= p["rent"]]
        if fits:
            best = min(fits, key=lambda p: p["rent"])
            score += 2; reasons.append(f"budget ${f['budget']} covers {best['name']} (${best['rent']})")
        else:
            reasons.append(f"budget ${f['budget']} is below every matching property")
            best = min(pool, key=lambda p: p["rent"]) if pool else None
            over_budget = best
    else:
        reasons.append("no budget given")
        best = pool[0] if (pool and (f["has_dates"] or stay is not None)) else None
    if not pool:
        reasons.append("no property fits the guests, pets or stay type")
        score = min(score, 1)
    label = "hot" if score >= 4 else "warm" if score >= 2 else "cold"
    return {"label": label, "score": score, "reasons": reasons, "match": best, "facts": f, "flag_team": label == "hot", "over_budget": over_budget is not None}


def draft_reply(text):
    q = qualify(text)
    p = q["match"]
    if q["label"] == "cold" and p is None:
        body = ("Thanks for reaching out. I want to make sure I point you to the right place, so could you tell me your move-in date, "
                "how long you plan to stay, and how many people?")
    elif p is None:
        body = "Thanks for your message. None of our current places fit that exact combination, but a couple of details would help me check for you: your dates and group size?"
    else:
        unit = "per night" if p["type"] == "short-term" else "per month"
        body = (f"Thanks for reaching out! {p['name']} is available from {p['available']} at ${p['rent']} {unit}. "
                f"Would you like to see it? I can offer a showing tomorrow at 10am or 4pm.")
        if q.get("over_budget"):
            body = (f"Thanks for reaching out! The closest fit is {p['name']}, available from {p['available']} at ${p['rent']} {unit}, "
                    f"which is a bit above the ${q['facts']['budget']} you mentioned. Is there any flexibility on budget, or would you like me to keep an eye out for something closer?")
        elif q["facts"]["budget"] is None:
            body = f"Thanks for reaching out! {p['name']} is available from {p['available']} at ${p['rent']} {unit}. Does that fit your budget, and what move-in date are you aiming for?"
    return q, body


def triage_request(text, tenant="the tenant"):
    t = text.lower()
    category = "gas" if re.search(r"\bgas\b|carbon monoxide", t) else "other"
    for cat, words in {} if category == "gas" else {"plumbing": ["leak", "water", "sink", "faucet", "drip", "toilet", "pipe", "flood"],
                       "electrical": ["spark", "outlet", "power", "breaker", "light", "electric"],
                       "hvac": ["ac ", "a/c", "air condition", "heat", "furnace", "thermostat", "hvac"],
                       "appliance": ["fridge", "refrigerator", "dishwasher", "oven", "washer", "dryer", "stove"],
                       "pest": ["roach", "ants", "mice", "rat", "bug", "bed bug"],
                       "lockout": ["locked", "lockout", "keys", "lock"]}.items():
        if any(w in t + " " for w in words):
            category = cat
            break
    if re.search(r"\bgas\b|fire|smoke|spark|flood|pouring|burst|no heat|carbon monoxide", t):
        urgency = "emergency"
    elif re.search(r"not working|stopped|no hot water|out|broken|locked|hot|locked out", t) or category == "lockout":
        urgency = "urgent"
    else:
        urgency = "routine"
    vendor = VENDORS[category]
    eta = {"emergency": "within the hour", "urgent": "today", "routine": "within 3 business days"}[urgency]
    reply = f"Thanks for letting us know. We've logged this as {urgency} ({category}) and {vendor} has been notified. Expect contact {eta}."
    if "gas" in t:
        reply = "If you smell gas, leave the unit now and call your gas utility's emergency line from outside. We've alerted the emergency vendor and will call you right away."
    notify = f"[{urgency.upper()}] {category} request: \"{text.strip()}\" Please respond {eta}. Reported {date.today():%Y-%m-%d}."
    return {"category": category, "urgency": urgency, "vendor": vendor, "reply": reply, "vendor_message": notify,
            "escalate_to_owner": urgency == "emergency"}
