# demo/scenario_ramesh_day.py
import time

def simulate_event(time_str, location, data_source, ai_logic, result):
    print(f"⏰ {time_str} | 📍 {location}")
    print(f"📡 DATA: {data_source}")
    print(f"🧠 AI LOGIC: {ai_logic}")
    print(f"💬 OUTPUT: {result}")
    print("-" * 50)
    time.sleep(1.5)

def run_phase_3_demo():
    print("🚀 SAHAY-AI PHASE 3: COMPREHENSIVE DEMO SCENARIO\n")

    # 1. ROUTINE & MEDICINE (The "RAG" check)
    simulate_event(
        "08:00 AM", "Kitchen", 
        "Routine check: 'Morning Donepezil 8AM'.",
        "Reasoning Agent checks 'routines' collection in ChromaDB.",
        "Assistance Agent: 'Good morning Ramesh! Time for your medicine. Let's take it with a glass of water.'"
    )

    # 2. COGNITIVE TRACKING (The "CCT" innovation)
    simulate_event(
        "02:00 PM", "Living Room",
        "Ramesh asks: 'Where is my son?' (Context: Arjun is in Bangalore).",
        "CCT Scoring detects 3s hesitation. Retrieval Agent pulls 'user_profile'.",
        "Assistance Agent: 'Arjun is in Bangalore, Ramesh. He’ll call you this Sunday!'"
    )

    # 3. EMERGENCY DETECTION (The "Classifier" you trained)
    simulate_event(
        "06:30 PM", "1.2km from Home",
        "Smartwatch Classifier: [WANDERING Detected]. GPS: [Outside safe zone].",
        "Reasoning Agent triggers 'Critical Risk' logic.",
        "System: Sending immediate Alert to Priya. Initiating guidance mode."
    )

    # 4. EMOTIONAL SUPPORT (The "EMR" memory rescue)
    simulate_event(
        "06:35 PM", "Unknown Street",
        "Ramesh voice: 'I don't know where I am... I'm scared.'",
        "EMR logic pulls 'mem_1' (Juhu Beach) from ChromaDB to lower cortisol.",
        "Assistance Agent: 'It’s okay Ramesh. Remember teaching Priya to ride a bike at Juhu? We’re going home just like that. Turn left here.'"
    )

    # 5. CAREGIVER HANDOFF (The "Caregiver Agent")
    simulate_event(
        "09:30 PM", "Priya's Phone",
        "Query: 'Dad's Daily Summary'",
        "Caregiver Agent synthesizes CCT scores and wandering event.",
        "Output: 'Ramesh had a 15% dip in memory today. Wandering event at 6:30PM resolved safely. Priya, take a break tonight—you've done great.'"
    )

if __name__ == "__main__":
    run_phase_3_demo()