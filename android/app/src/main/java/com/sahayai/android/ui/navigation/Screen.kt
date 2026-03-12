package com.sahayai.android.ui.navigation

sealed class Screen(val route: String) {
    object Onboarding : Screen("onboarding")
    object PatientHome : Screen("patient/home")
    object Conversation : Screen("patient/conversation")
    object SceneUnderstanding : Screen("patient/scene")
    object Reminders : Screen("patient/reminders")
    object Emergency : Screen("patient/emergency")
    object CaregiverHome : Screen("caregiver/home")
    object AlertsFeed : Screen("caregiver/alerts")
    object AlertDetail : Screen("caregiver/alerts/{alertId}") {
        fun withId(id: String) = "caregiver/alerts/$id"
    }
    object DailySummary : Screen("caregiver/summary")
    object CognitiveTrend : Screen("caregiver/trends")
}
