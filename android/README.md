# SahayAI Android App

AI-powered care companion for elderly patients and their caregivers.

## Prerequisites

- JDK 17+
- Android Studio Hedgehog or newer (AGP 8.4)
- Android device / emulator running API 26+ (Android 8.0)
- Gradle 8.7

## Build Instructions

```bash
# Debug APK with mock data (default)
./gradlew assembleDebug

# Install on connected device
./gradlew installDebug

# Run unit tests
./gradlew test
```

Or open the `android/` folder directly in Android Studio and click **Run**.

## Mock Mode (Default for Demo)

Debug builds have `USE_MOCK_DATA=true` baked in — no backend needed.

The app ships with the **"Ramesh" demo persona**:
- Patient ID: `ramesh_demo_001`
- Caregiver ID: `caregiver_priya_001`

All API calls return realistic mock data with 300–600ms simulated latency.

## Real API Mode

In `app/build.gradle.kts`, set for the release build type:
```kotlin
buildConfigField("Boolean", "USE_MOCK_DATA", "false")
buildConfigField("String", "BASE_URL", "\"https://your-backend-url/\"")
```

Then run `./gradlew assembleRelease`.

## Demo Walkthrough

1. Launch app → **Onboarding** screen appears
2. Select **Patient** role → enter `ramesh_demo_001` → tap **Get Started**
3. **Patient Home** → tap **Talk to SahayAI** → mic button → speak → response + TTS
4. Tap **Check Surroundings** → camera → **Capture** → scene description read aloud
5. Tap **My Reminders** → tap a reminder to confirm it
6. Tap **Emergency Help** → big SOS button → caregiver notified
7. Back to onboarding (switch role) → select **Caregiver** → enter `caregiver_priya_001` + patient `ramesh_demo_001`
8. **Caregiver Home** → alerts count badge visible
9. Tap **All Alerts** → alert feed → tap alert → detail + Acknowledge
10. Tap **Daily Summary** → stats + mood summary
11. Tap **Cognitive Trends** → 14-day CCT line chart + dimension filter

## Architecture

```
core/
  config/      App configuration
  di/          Hilt DI modules (NetworkModule has single mock/real switch)
  network/     Retrofit service + WebSocket client
  db/          Room database (offline-first cache)
  datastore/   User preferences (onboarding state, role, userId)
  mock/        MockApiService + MockData (Ramesh persona)
  util/        Extensions, DateFormatter

domain/
  model/       All data classes (@Serializable)
  repository/  Repository interfaces + implementations

ui/
  theme/       Colors, Typography (min 18sp body), Shapes
  navigation/  Screen sealed class + NavHost
  components/  Shared composables (LargeActionCard, LargeMicButton, etc.)
  patient/     Onboarding, Home, Conversation, Scene, Reminders, Emergency
  caregiver/   Home, AlertsFeed, AlertDetail, DailySummary, CognitiveTrend
```

## Key Design Decisions

- **Single APK, two roles** — role chosen at onboarding, stored in DataStore
- **Mock/real switch** — single `if (BuildConfig.USE_MOCK_DATA)` in `NetworkModule`, zero mock leakage
- **Offline-first** — Room cache populated on first fetch, served immediately on next launch
- **Elderly UX** — min 18sp body text, large touch targets (48dp+), calm blue/white palette
- **Accessibility** — all interactive elements have `contentDescription`
