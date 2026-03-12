package com.sahayai.android.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.navigation.navigation
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.domain.model.UserRole
import com.sahayai.android.ui.caregiver.alerts.AlertDetailScreen
import com.sahayai.android.ui.caregiver.alerts.AlertsFeedScreen
import com.sahayai.android.ui.caregiver.home.CaregiverHomeScreen
import com.sahayai.android.ui.caregiver.summary.DailySummaryScreen
import com.sahayai.android.ui.caregiver.trends.CognitiveTrendScreen
import com.sahayai.android.ui.patient.conversation.ConversationScreen
import com.sahayai.android.ui.patient.emergency.EmergencyScreen
import com.sahayai.android.ui.patient.home.PatientHomeScreen
import com.sahayai.android.ui.patient.onboarding.OnboardingScreen
import com.sahayai.android.ui.patient.reminders.RemindersScreen
import com.sahayai.android.ui.patient.scene.SceneScreen
import javax.inject.Inject

@Composable
fun AppNavigation(
    prefsRepository: UserPreferencesRepository = hiltViewModel<NavViewModel>().prefsRepository
) {
    val navController = rememberNavController()
    val prefs by prefsRepository.userPreferences.collectAsState(initial = null)

    prefs?.let { userPrefs ->
        val startDest = if (!userPrefs.onboardingDone) {
            Screen.Onboarding.route
        } else if (userPrefs.userRole == UserRole.CAREGIVER) {
            "caregiver"
        } else {
            "patient"
        }

        NavHost(navController = navController, startDestination = startDest) {
            composable(Screen.Onboarding.route) {
                OnboardingScreen(
                    onPatientOnboarded = { navController.navigate(Screen.PatientHome.route) { popUpTo(0) } },
                    onCaregiverOnboarded = { navController.navigate(Screen.CaregiverHome.route) { popUpTo(0) } }
                )
            }

            // Patient graph
            navigation(startDestination = Screen.PatientHome.route, route = "patient") {
                composable(Screen.PatientHome.route) {
                    PatientHomeScreen(
                        onNavigateToConversation = { navController.navigate(Screen.Conversation.route) },
                        onNavigateToScene = { navController.navigate(Screen.SceneUnderstanding.route) },
                        onNavigateToReminders = { navController.navigate(Screen.Reminders.route) },
                        onNavigateToEmergency = { navController.navigate(Screen.Emergency.route) },
                        onSwitchRole = { navController.navigate(Screen.Onboarding.route) { popUpTo(0) } }
                    )
                }
                composable(Screen.Conversation.route) {
                    ConversationScreen(onBack = { navController.popBackStack() })
                }
                composable(Screen.SceneUnderstanding.route) {
                    SceneScreen(onBack = { navController.popBackStack() })
                }
                composable(Screen.Reminders.route) {
                    RemindersScreen(onBack = { navController.popBackStack() })
                }
                composable(Screen.Emergency.route) {
                    EmergencyScreen(onBack = { navController.popBackStack() })
                }
            }

            // Caregiver graph
            navigation(startDestination = Screen.CaregiverHome.route, route = "caregiver") {
                composable(Screen.CaregiverHome.route) {
                    CaregiverHomeScreen(
                        onNavigateToAlerts = { navController.navigate(Screen.AlertsFeed.route) },
                        onNavigateToSummary = { navController.navigate(Screen.DailySummary.route) },
                        onNavigateToTrends = { navController.navigate(Screen.CognitiveTrend.route) },
                        onSwitchRole = { navController.navigate(Screen.Onboarding.route) { popUpTo(0) } },
                        onAlertClick = { alertId -> navController.navigate(Screen.AlertDetail.withId(alertId)) }
                    )
                }
                composable(Screen.AlertsFeed.route) {
                    AlertsFeedScreen(
                        onBack = { navController.popBackStack() },
                        onAlertClick = { alertId -> navController.navigate(Screen.AlertDetail.withId(alertId)) }
                    )
                }
                composable(
                    route = Screen.AlertDetail.route,
                    arguments = listOf(navArgument("alertId") { type = NavType.StringType })
                ) { backStackEntry ->
                    AlertDetailScreen(onBack = { navController.popBackStack() })
                }
                composable(Screen.DailySummary.route) {
                    DailySummaryScreen(onBack = { navController.popBackStack() })
                }
                composable(Screen.CognitiveTrend.route) {
                    CognitiveTrendScreen(onBack = { navController.popBackStack() })
                }
            }
        }
    }
}
