-- ============================================================
-- Demo seed data: Ramesh (patient) + Priya (caregiver daughter)
-- Run after tables are created. IDs are hardcoded so all our
-- demo scripts and Flutter mock data reference the same UUIDs.
-- ============================================================

-- Ramesh — 72 year old with early-stage dementia, lives in Andheri
INSERT INTO users (id, name, role, disability_type, medical_conditions, home_lat, home_lng, home_address, aac_baseline, cbd_score, created_at)
VALUES (
    'ramesh-001',
    'Ramesh Sharma',
    'patient',
    'cognitive',
    'early-stage dementia, hypertension, mild hearing loss',
    19.1136, 72.8697,
    '14 Lokhandwala Complex, Andheri West, Mumbai 400053',
    70, 0.0, NOW()
);

-- Priya — Ramesh's daughter and primary caregiver
INSERT INTO users (id, name, role, disability_type, medical_conditions, home_lat, home_lng, home_address, aac_baseline, cbd_score, created_at)
VALUES (
    'priya-001',
    'Priya Sharma',
    'caregiver',
    NULL, NULL,
    19.1180, 72.8540,
    '7 Versova, Andheri West, Mumbai 400061',
    70, 15.0, NOW()
);

-- Link Priya as Ramesh's primary caregiver
INSERT INTO caregiver_links (id, caregiver_id, patient_id, is_primary, relationship_label, created_at)
VALUES (
    'link-001',
    'priya-001',
    'ramesh-001',
    TRUE,
    'daughter',
    NOW()
);

-- Ramesh's daily routines
INSERT INTO routines (id, user_id, routine_type, scheduled_time, description, is_active, days_of_week, adherence_rate, created_at, updated_at) VALUES
    ('routine-001', 'ramesh-001', 'medication', '08:00', 'Take blood pressure medication (Amlodipine 5mg) with a glass of water', TRUE, 'mon,tue,wed,thu,fri,sat,sun', 0.85, NOW(), NOW()),
    ('routine-002', 'ramesh-001', 'medication', '20:00', 'Take evening medication (Donepezil 10mg) after dinner', TRUE, 'mon,tue,wed,thu,fri,sat,sun', 0.78, NOW(), NOW()),
    ('routine-003', 'ramesh-001', 'walk',       '07:00', 'Morning walk around Lokhandwala garden — usually 30 minutes, stays within 500m', TRUE, 'mon,tue,wed,thu,fri,sat,sun', 0.90, NOW(), NOW()),
    ('routine-004', 'ramesh-001', 'meal',       '12:30', 'Lunch — usually eats at home, Priya prepares before leaving for work', TRUE, 'mon,tue,wed,thu,fri,sat,sun', 0.95, NOW(), NOW()),
    ('routine-005', 'ramesh-001', 'sleep',      '22:00', 'Bedtime — gets restless if not in bed by 10:30 PM', TRUE, 'mon,tue,wed,thu,fri,sat,sun', 0.70, NOW(), NOW());

-- A few historical events so the demo summary has something to show
INSERT INTO events (id, user_id, event_type, severity, description, lat, lng, agent_action, timestamp) VALUES
    ('event-001', 'ramesh-001', 'medication_taken', 'info', 'Confirmed morning medication (Amlodipine) via voice', NULL, NULL, 'Logged confirmation, updated adherence rate', NOW() - INTERVAL '2 hours'),
    ('event-002', 'ramesh-001', 'conversation', 'info', 'Had a 5-minute conversation about breakfast plans. CCT scored 0.78 — normal range.', NULL, NULL, 'CCT scored, no alert needed', NOW() - INTERVAL '1 hour'),
    ('event-003', 'ramesh-001', 'camera_use', 'info', 'Used camera to identify items on kitchen counter. Scene: medicine bottles, water glass, newspaper.', 19.1136, 72.8697, 'Described scene, no obstacles detected', NOW() - INTERVAL '30 minutes');