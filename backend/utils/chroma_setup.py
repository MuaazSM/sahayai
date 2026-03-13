# utils/chroma_setup.py

import os
import chromadb
from chromadb.utils import embedding_functions

# ------------------------------------------------------------------------
# 1. INITIALIZE DATABASE AND EMBEDDING MODEL
# ------------------------------------------------------------------------

# Define the path where our database will live on your computer.
# We go up one folder from 'utils' to the main backend folder, then into 'data/chroma_db'
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")

# Create a PersistentClient. This means the data saves to your hard drive, 
# so you don't lose Ramesh's data every time you restart the server!
client = chromadb.PersistentClient(path=DB_PATH)

# Setup our free, local embedding model (HuggingFace all-MiniLM-L6-v2). 
# This turns our text into numbers (vectors) so the AI can search through them by meaning.
# COST: $0.00 (Runs entirely on your machine)
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

print("✅ Database client and Embedding model loaded successfully!")

# ------------------------------------------------------------------------
# 2. CREATE COLLECTIONS
# ------------------------------------------------------------------------

# A 'collection' in ChromaDB is like a specific table or folder for our data.
# We use get_or_create_collection so it doesn't crash if we run this script twice.
collections = {
    "user_profile": client.get_or_create_collection(name="user_profile", embedding_function=sentence_transformer_ef),
    "routines": client.get_or_create_collection(name="routines", embedding_function=sentence_transformer_ef),
    "past_events": client.get_or_create_collection(name="past_events", embedding_function=sentence_transformer_ef),
    "caregiver_prefs": client.get_or_create_collection(name="caregiver_prefs", embedding_function=sentence_transformer_ef),
    "communication": client.get_or_create_collection(name="communication", embedding_function=sentence_transformer_ef),
    "emr_memories": client.get_or_create_collection(name="emr_memories", embedding_function=sentence_transformer_ef)
}

print("✅ All 6 RAG collections created!")

# ------------------------------------------------------------------------
# 3. SEED DATA (Filling the AI's Memory)
# ------------------------------------------------------------------------

# We structure our data as dictionaries. Keys are IDs, values are the actual text.
seed_data = {
    "user_profile": {
        "profile_1": "Ramesh: age 72, early-stage Alzheimer's, lives at 14 Maple Street, wife Sita at home, daughter Priya 20 min away visits daily 4PM, son Arjun in Bangalore calls Sundays, allergic to penicillin, uses walking cane."
    },
    "routines": {
        "routine_1": "wakes 6:30-7AM, morning Donepezil 8AM, lunch 12:30PM, afternoon rest 1-3PM, park walk 5-5:30PM within 500m, evening Memantine 8PM, bed 9:30PM, days_of_week: all"
    },
    "past_events": {
        "event_1": "March 3 6:45PM: wandering 1.1km, resolved by Priya calling, returned 7:20PM.",
        "event_2": "March 8 5:10PM: walked to park known location, self-returned 5:30PM.",
        "event_3": "March 10 8:45PM: missed evening medication, reminded at 8:45, took at 8:50"
    },
    "caregiver_prefs": {
        "pref_1": "Priya: immediate alerts for wandering, fall alerts highest priority, don't alert for missed meds unless 2+ hours late, prefers detailed context in alerts, quiet hours 11PM-6AM except emergencies"
    },
    "communication": {
        "comm_1": "responds well to yes/no questions, confused by multi-step instructions, prefers first name not 'sir', morning: more detailed ok, evening: gentler shorter sentences, needs reorientation: 'This is SahayAI your helper'"
    },
    "emr_memories": {
        "mem_1": "Priya learning to ride bicycle at Juhu beach, Ramesh ran alongside her the whole road",
        "mem_2": "Arjun's graduation ceremony, Ramesh gave a speech and everyone clapped",
        "mem_3": "Wedding anniversary dinner at Taj hotel, Sita wore the red saree Ramesh bought",
        "mem_4": "Sunday cricket matches with neighbours, Ramesh was always the bowler",
        "mem_5": "Priya's first painting exhibition, Ramesh bought three paintings"
    }
}

# Emotion tags specific to our EMR (Emotional Memory Reinforcement) memories
emr_metadata = {
    "mem_1": {"tags": "family, joy, priya, outdoor"},
    "mem_2": {"tags": "family, pride, arjun, achievement"},
    "mem_3": {"tags": "love, sita, celebration"},
    "mem_4": {"tags": "fun, friends, outdoor, sport"},
    "mem_5": {"tags": "family, pride, priya, art"}
}

# ------------------------------------------------------------------------
# 4. INSERT DATA INTO CHROMADB
# ------------------------------------------------------------------------

# Loop through each category and insert it into the correct collection
for collection_name, data in seed_data.items():
    collection = collections[collection_name]
    
    ids = list(data.keys())
    documents = list(data.values())
    
    # If we are inserting memories, we attach the emotion metadata tags to them
    if collection_name == "emr_memories":
        metadatas = [emr_metadata[mem_id] for mem_id in ids]
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
    else:
        # Standard insert without specific metadata
        collection.upsert(documents=documents, ids=ids)
        
    print(f"✅ Inserted {len(documents)} records into '{collection_name}'")

print("\n🎉 SUCCESS: All seed data loaded. SahayAI now has a memory!")