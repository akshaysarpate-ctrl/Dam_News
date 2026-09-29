"""Optional second-pass check with the Claude API (set ANTHROPIC_API_KEY in .env).

Works on the headline and snippet in any language. It confirms whether the item reports
an actual failure of a dam/reservoir/barrage/tank, rejects noise (inaugurations, water-level
updates, river flood embankments), and fills in state, district and dam name.
"""
import json
import logging

import config

log = logging.getLogger("classify")

SYSTEM = """You screen news items for a dam-safety monitoring desk in India.
The item may be in any Indian language. Reply with ONE JSON object and nothing else:
{"relevant": bool, "in_india": bool,
 "structure": "dam|barrage|tank_bund|reservoir|river_embankment|canal|other",
 "event_type": "breach|collapse|overtopping|gate_failure|leakage_seepage|cracks|inundation_from_release|other",
 "state": "English state name or empty", "district": "English district name or empty",
 "dam_name": "English name of the dam/structure or empty"}

relevant = true only if the item reports an actual failure, breach, collapse, gate failure,
overtopping, serious leakage or cracks of a dam, barrage, reservoir or tank bund, OR
inundation of land/villages caused by such a failure or an uncontrolled release.
relevant = false for: inaugurations, plans, tenders, mock drills, routine water-level or
release notices, tourism, opinion pieces without an incident, and failures of river
flood embankments (use structure "river_embankment")."""


def parse_reply(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def decide(data: dict) -> str:
    """Map the model's answer to a status."""
    relevant = bool(data.get("relevant")) and bool(data.get("in_india", True))
    if str(data.get("structure", "")).lower() == "river_embankment" and not config.INCLUDE_RIVER_EMBANKMENTS:
        relevant = False
    return "relevant" if relevant else "rejected"


def classify_pending(conn, limit: int = 150) -> int:
    try:
        import anthropic
    except ImportError:
        log.warning("The 'anthropic' package is not installed - skipping the AI check.")
        return 0
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    rows = conn.execute(
        """SELECT id, title, snippet, source, language, kind FROM articles
           WHERE llm_checked = 0 AND status IN ('relevant','maybe') AND collector != 'demo'
           ORDER BY published_at DESC LIMIT ?""", (limit,)).fetchall()
    done, failures = 0, 0
    for row in rows:
        prompt = (f"Language code: {row['language']}\nType: {row['kind']}\n"
                  f"Source: {row['source']}\nTitle: {row['title']}\n"
                  f"Snippet: {(row['snippet'] or '')[:500]}")
        try:
            msg = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=300,
                                         system=SYSTEM,
                                         messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        except Exception as exc:  # network, auth, rate limit...
            failures += 1
            log.warning("AI check failed: %s", str(exc)[:160])
            if failures >= 3:
                log.warning("Stopping the AI check after 3 failures.")
                break
            continue
        data = parse_reply(text)
        if not data:
            continue
        status = decide(data)
        conn.execute(
            """UPDATE articles SET status=?, llm_checked=1, structure=?, event_type=?,
                 state=COALESCE(NULLIF(?, ''), state), district=?, dam_name=? WHERE id=?""",
            (status, str(data.get("structure", ""))[:40], str(data.get("event_type", ""))[:40],
             str(data.get("state", ""))[:60], str(data.get("district", ""))[:80],
             str(data.get("dam_name", ""))[:120], row["id"]))
        conn.commit()
        done += 1
    log.info("AI check finished: %d of %d items classified.", done, len(rows))
    return done
