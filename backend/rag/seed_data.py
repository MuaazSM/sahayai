"""
Seed ChromaDB with the Ramesh demo persona.

Run this once before demo / tests:
    python -m rag.seed_data

Ramesh Sharma, 72 — retired school principal, early-stage dementia,
lives with daughter Priya in Bangalore.
"""

import logging
import sys

logger = logging.getLogger("sahayai.rag.seed")


# =====================================================
# Seed documents — keyed by collection name
# Each entry: (doc_id, text, metadata)
# =====================================================

USER_PROFILE = [
    (
        "ramesh-profile-001",
        (
            "Ramesh Sharma is a 72-year-old retired school principal living in Bangalore. "
            "He has early-stage dementia and uses SahayAI for daily assistance. "
            "His daughter Priya (caregiver ID: priya-001) is his primary caregiver. "
            "He was diagnosed with Alzheimer's disease in 2024. "
            "He is a warm, gentle man who loves cricket, classical music, and gardening. "
            "He responds best to calm, respectful language in Hindi or simple English. "
            "He gets anxious in the evenings (sundowning) and benefits from familiar routines."
        ),
        {"user_id": "ramesh-001", "type": "profile", "language": "en"},
    ),
    (
        "ramesh-family-001",
        (
            "Ramesh's family: Daughter Priya Sharma (caregiver, 42, software engineer, "
            "contact: priya-001). Wife Savitri passed away in 2019. "
            "Son Rahul lives in Mumbai, visits monthly. "
            "Grandchildren: Arjun (16) and Meera (13). "
            "Ramesh lights up when family is mentioned, especially Priya and the grandchildren."
        ),
        {"user_id": "ramesh-001", "type": "family"},
    ),
    (
        "ramesh-medical-001",
        (
            "Medical conditions: Early-stage Alzheimer's dementia (diagnosed 2024), "
            "Type 2 diabetes (managed with Metformin 500mg twice daily), "
            "Hypertension (managed with Amlodipine 5mg once daily). "
            "No history of falls yet. Gait is steady. "
            "Blood pressure target: 130/80. "
            "Allergic to penicillin."
        ),
        {"user_id": "ramesh-001", "type": "medical"},
    ),
]

ROUTINES = [
    (
        "ramesh-routine-morning-meds",
        "Take Metformin 500mg with breakfast at 8:00 AM every morning. "
        "Reminder: 'Ramesh ji, time for your morning tablet with your chai.'",
        {"user_id": "ramesh-001", "time": "08:00", "type": "medication", "days": "daily"},
    ),
    (
        "ramesh-routine-morning-walk",
        "Morning walk in the garden from 8:30 AM to 9:00 AM. "
        "Ramesh enjoys watering his plants and watching the birds. "
        "If he hasn't left the house by 9:15, check in with him.",
        {"user_id": "ramesh-001", "time": "08:30", "type": "routine", "days": "daily"},
    ),
    (
        "ramesh-routine-breakfast",
        "Breakfast at 8:00 AM. Ramesh usually has idli or dosa with sambar, "
        "and a cup of strong chai. He is diabetic so no extra sugar.",
        {"user_id": "ramesh-001", "time": "08:00", "type": "meal", "days": "daily"},
    ),
    (
        "ramesh-routine-lunch",
        "Lunch at 12:30 PM. Rice, dal, sabzi, and yogurt. "
        "Take Metformin 500mg evening dose at 7:00 PM with dinner.",
        {"user_id": "ramesh-001", "time": "12:30", "type": "meal", "days": "daily"},
    ),
    (
        "ramesh-routine-nap",
        "Afternoon rest/nap from 2:00 PM to 3:30 PM. "
        "If he skips the nap, evenings tend to be more confusing (sundowning risk).",
        {"user_id": "ramesh-001", "time": "14:00", "type": "rest", "days": "daily"},
    ),
    (
        "ramesh-routine-evening-meds",
        "Evening medication: Amlodipine 5mg at 7:00 PM with dinner. "
        "Also Metformin 500mg evening dose at this time.",
        {"user_id": "ramesh-001", "time": "19:00", "type": "medication", "days": "daily"},
    ),
    (
        "ramesh-routine-cricket",
        "Ramesh watches cricket on TV every evening from 5:30 PM when there is a match. "
        "He loves the Indian national team and gets excited about big matches. "
        "This is a good calming activity during sundowning hours.",
        {"user_id": "ramesh-001", "time": "17:30", "type": "leisure", "days": "when_match"},
    ),
    (
        "ramesh-routine-bedtime",
        "Bedtime at 9:30 PM. Ramesh reads or listens to classical music (Carnatic or Hindustani) "
        "before sleeping. Priya checks in by phone at 9:00 PM each night.",
        {"user_id": "ramesh-001", "time": "21:30", "type": "sleep", "days": "daily"},
    ),
]

CAREGIVER_PREFS = [
    (
        "priya-prefs-001",
        (
            "Priya Sharma (caregiver for Ramesh). Alert preferences: "
            "Send URGENT alerts immediately via push notification and phone call. "
            "ATTENTION alerts via push notification. "
            "ROUTINE alerts only as daily summary. "
            "Quiet hours: 11:00 PM to 7:00 AM (only emergency alerts during this time). "
            "Priya works from home on Tuesdays and Thursdays — more responsive those days. "
            "She prefers concise, factual alert messages. She gets anxious if alerts are too alarming."
        ),
        {"caregiver_id": "priya-001", "patient_id": "ramesh-001"},
    ),
    (
        "priya-prefs-002",
        (
            "Priya's escalation preferences: "
            "For confusion/disorientation: first remind Ramesh calmly, then alert Priya if confusion persists >5 min. "
            "For falls: alert immediately. "
            "For medication missed: remind Ramesh twice, then alert Priya if still missed after 30 min. "
            "For wandering outside geofence: alert immediately with GPS location."
        ),
        {"caregiver_id": "priya-001", "patient_id": "ramesh-001"},
    ),
]

COMMUNICATION = [
    (
        "ramesh-comm-001",
        (
            "How to speak with Ramesh: Use simple, short sentences. "
            "Address him as 'Ramesh ji' — he appreciates the respectful title. "
            "Speak slowly and clearly. "
            "If he seems confused, don't correct him harshly — redirect gently. "
            "Use familiar Indian references (cricket, festivals, family) to orient him. "
            "Avoid complex medical language. "
            "If he asks where Savitri (wife) is, gently redirect rather than reminding him she passed away."
        ),
        {"user_id": "ramesh-001", "type": "communication_style"},
    ),
    (
        "ramesh-comm-002",
        (
            "Ramesh's emotional triggers and soothers: "
            "Triggers: Being told he is confused or wrong; unfamiliar people; evenings (sundowning). "
            "Soothers: Mentions of Priya, grandchildren Arjun and Meera; cricket scores; "
            "memories of his teaching career; classical music (Ravi Shankar, MS Subbulakshmi); "
            "the garden and his rose plants. "
            "If distressed, ask about his garden or a happy memory."
        ),
        {"user_id": "ramesh-001", "type": "emotional_profile"},
    ),
]

EMR_MEMORIES = [
    (
        "ramesh-emr-garden",
        (
            "Ramesh's rose garden — he has grown roses for 30 years. "
            "His favourite is the Rajnigandha (tuberose) that Savitri planted on their anniversary. "
            "He still tends it every morning. The garden gives him a sense of purpose and continuity."
        ),
        {"user_id": "ramesh-001", "emotion": "calm", "effectiveness_count": 5, "tags": "garden,nature,purpose"},
    ),
    (
        "ramesh-emr-priya-bicycle",
        (
            "When Priya was 8 years old, Ramesh taught her to ride a bicycle in their Mysore home. "
            "She fell twice and cried, but he held the seat and ran alongside until she got it. "
            "She still calls it her proudest childhood memory. Ramesh beams every time he tells this story."
        ),
        {"user_id": "ramesh-001", "emotion": "joy", "effectiveness_count": 8, "tags": "family,priya,childhood,joy"},
    ),
    (
        "ramesh-emr-school",
        (
            "Ramesh was principal of St. Joseph's School, Mysore for 18 years. "
            "He was known as 'the principal who remembered every student's name.' "
            "His students still visit him. In 2018, they organized a surprise reunion with 200 former students. "
            "He cried when they walked in."
        ),
        {"user_id": "ramesh-001", "emotion": "pride", "effectiveness_count": 6, "tags": "career,respect,achievement"},
    ),
    (
        "ramesh-emr-cricket-1983",
        (
            "India won the 1983 Cricket World Cup. Ramesh was 29 years old, watching on a small black-and-white TV "
            "with his college friends in a tiny room in Mysore. When Kapil Dev lifted the trophy, "
            "the whole street burst into celebration. He says it was the happiest moment of his youth."
        ),
        {"user_id": "ramesh-001", "emotion": "joy", "effectiveness_count": 7, "tags": "cricket,india,celebration,youth"},
    ),
    (
        "ramesh-emr-savitri-wedding",
        (
            "Ramesh and Savitri were married in 1976 in a beautiful ceremony in Bangalore. "
            "She wore a green Kanjivaram silk saree. He was so nervous he forgot his lines twice. "
            "They were married for 43 years. He says she was the wisest person he ever knew."
        ),
        {"user_id": "ramesh-001", "emotion": "love", "effectiveness_count": 4, "tags": "marriage,savitri,love,memories"},
    ),
    (
        "ramesh-emr-arjun-chess",
        (
            "Ramesh taught his grandson Arjun to play chess when he was 7. "
            "Arjun beat him for the first time two years ago and Ramesh laughed so hard he cried. "
            "They still play when Arjun visits. It's their special ritual."
        ),
        {"user_id": "ramesh-001", "emotion": "joy", "effectiveness_count": 9, "tags": "arjun,grandchild,chess,family,joy"},
    ),
    (
        "ramesh-emr-music",
        (
            "Ramesh listens to Carnatic classical music to relax — especially MS Subbulakshmi's Suprabhatam "
            "in the morning and Ravi Shankar's sitar in the evenings. "
            "Music was a constant in his childhood home. His mother sang every morning."
        ),
        {"user_id": "ramesh-001", "emotion": "calm", "effectiveness_count": 6, "tags": "music,carnatic,peace,home"},
    ),
    (
        "ramesh-emr-meera-painting",
        (
            "Granddaughter Meera (13) painted a portrait of Ramesh for his 70th birthday. "
            "It hangs in his bedroom. He touches the frame every morning. "
            "She has his talent for detail — he was an artist in his college days."
        ),
        {"user_id": "ramesh-001", "emotion": "love", "effectiveness_count": 5, "tags": "meera,grandchild,art,love,birthday"},
    ),
]

PAST_EVENTS = [
    (
        "ramesh-event-confusion-dec",
        (
            "December 2025: Ramesh became confused at 6 PM and thought he was late for school. "
            "He was heading toward the front door with his briefcase. "
            "Priya calmly reminded him he was retired and they had chai together. "
            "He settled down within 10 minutes after the gentle reminder and chai."
        ),
        {"user_id": "ramesh-001", "type": "confusion", "severity": "medium", "month": "dec_2025"},
    ),
    (
        "ramesh-event-medication-missed",
        (
            "January 2026: Ramesh missed his evening Amlodipine dose twice in one week "
            "because he forgot he had already taken it and didn't take it again to be safe. "
            "Learning: single pill organizer introduced, situation improved."
        ),
        {"user_id": "ramesh-001", "type": "medication_missed", "severity": "low", "month": "jan_2026"},
    ),
    (
        "ramesh-event-garden-fall-near-miss",
        (
            "February 2026: Ramesh slipped slightly on wet garden path but caught himself on the wall. "
            "No injury. Grip-sole sandals ordered. Garden path now has non-slip mat. "
            "Priya aware, no alert needed at the time as Ramesh was fine."
        ),
        {"user_id": "ramesh-001", "type": "near_fall", "severity": "low", "month": "feb_2026"},
    ),
]


def seed_all(force: bool = False):
    """
    Seed all collections. If force=True, clears existing docs first.
    Safe to run multiple times with force=False — won't duplicate.
    """
    from rag.chromadb_setup import init_chromadb, get_collection
    from rag.embeddings import embed_texts

    init_chromadb()
    logger.info("Starting seed...")

    collections_data = [
        ("user_profile", USER_PROFILE),
        ("routines", ROUTINES),
        ("caregiver_prefs", CAREGIVER_PREFS),
        ("communication", COMMUNICATION),
        ("emr_memories", EMR_MEMORIES),
        ("past_events", PAST_EVENTS),
    ]

    for collection_name, docs in collections_data:
        collection = get_collection(collection_name)
        existing_ids = set(collection.get(include=[])["ids"])

        new_docs = [(doc_id, text, meta) for doc_id, text, meta in docs if doc_id not in existing_ids]
        if not new_docs and not force:
            logger.info(f"  {collection_name}: already seeded ({len(existing_ids)} docs), skipping")
            continue

        if force and existing_ids:
            collection.delete(ids=list(existing_ids))
            new_docs = docs

        ids = [d[0] for d in new_docs]
        texts = [d[1] for d in new_docs]
        metadatas = [d[2] for d in new_docs]
        embeddings = embed_texts(texts)

        collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        logger.info(f"  {collection_name}: added {len(ids)} documents")

    logger.info("Seed complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    force = "--force" in sys.argv
    seed_all(force=force)
