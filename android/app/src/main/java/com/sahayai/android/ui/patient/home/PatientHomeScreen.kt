package com.sahayai.android.ui.patient.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.automirrored.filled.DirectionsWalk
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.MicNone
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.ui.components.DashboardMetricCard
import com.sahayai.android.ui.components.FeatureActionCard
import com.sahayai.android.ui.components.FloatingNavigationBar
import com.sahayai.android.ui.components.HealthStatusCard
import com.sahayai.android.ui.components.LoadingOverlay
import com.sahayai.android.ui.components.NavItem
import com.sahayai.android.ui.theme.AlertHigh
import com.sahayai.android.ui.theme.AlertHighLight
import com.sahayai.android.ui.theme.EmergencyRed
import com.sahayai.android.ui.theme.EmergencyRedLight
import com.sahayai.android.ui.theme.MetricLavender
import com.sahayai.android.ui.theme.MetricLavenderDark
import com.sahayai.android.ui.theme.MetricMint
import com.sahayai.android.ui.theme.MetricMintDark
import com.sahayai.android.ui.theme.PrimaryBlue
import com.sahayai.android.ui.theme.PrimaryBlueLight

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PatientHomeScreen(
    onNavigateToConversation: () -> Unit,
    onNavigateToScene: () -> Unit,
    onNavigateToReminders: () -> Unit,
    onNavigateToEmergency: () -> Unit,
    onSwitchRole: () -> Unit,
    viewModel: PatientHomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    
    // Bottom Nav State
    var selectedNavIndex by remember { mutableStateOf(0) }
    val navItems = listOf(
        NavItem("Home", Icons.Filled.Home),
        NavItem("Tasks", Icons.AutoMirrored.Filled.ListAlt),
        NavItem("Profile", Icons.Filled.Person)
    )

    LaunchedEffect(uiState.error) {
        uiState.error?.let { errorMessage ->
            snackbarHostState.showSnackbar(message = errorMessage)
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = {
            SnackbarHost(hostState = snackbarHostState) { data ->
                Snackbar(
                    snackbarData = data,
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = Color.White
                )
            }
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState()),
            ) {
                // Top Greeting (HealthStatusCard)
                HealthStatusCard(
                    userName = uiState.userName.ifBlank { "Ramesh" },
                    statusText = "Monitoring active",
                    statusColor = MetricMintDark
                )

                // Health Metrics Grid
                Column(modifier = Modifier.padding(horizontal = 24.dp)) {
                    Text(
                        text = "Today's Overview",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        DashboardMetricCard(
                            title = "Steps",
                            value = "2,430",
                            icon = Icons.AutoMirrored.Filled.DirectionsWalk,
                            tintColor = PrimaryBlueLight,
                            iconColor = PrimaryBlue,
                            modifier = Modifier.weight(1f)
                        )
                        DashboardMetricCard(
                            title = "Cognitive",
                            value = "85%",
                            icon = Icons.Filled.Favorite,
                            tintColor = MetricLavender,
                            iconColor = MetricLavenderDark,
                            modifier = Modifier.weight(1f)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(32.dp))

                // Action Cards List
                Column(
                    modifier = Modifier.padding(horizontal = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Text(
                        text = "Quick Actions",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    
                    FeatureActionCard(
                        title = "Talk to SahayAI",
                        subtitle = "Speak to your intelligent companion",
                        icon = Icons.Filled.MicNone,
                        iconContainerColor = PrimaryBlueLight,
                        iconColor = PrimaryBlue,
                        onClick = onNavigateToConversation
                    )

                    FeatureActionCard(
                        title = "Check Surroundings",
                        subtitle = "Use the camera to understand your space",
                        icon = Icons.Filled.CameraAlt,
                        iconContainerColor = MetricMint,
                        iconColor = MetricMintDark,
                        onClick = onNavigateToScene
                    )

                    FeatureActionCard(
                        title = "My Reminders",
                        subtitle = if (uiState.pendingReminderCount > 0) "${uiState.pendingReminderCount} pending tasks" else "All clear",
                        icon = Icons.Filled.Notifications,
                        iconContainerColor = AlertHighLight,
                        iconColor = AlertHigh,
                        onClick = onNavigateToReminders,
                        badgeCount = uiState.pendingReminderCount
                    )

                    FeatureActionCard(
                        title = "Emergency Help",
                        subtitle = "Notify your caregiver immediately",
                        icon = Icons.Filled.Warning,
                        iconContainerColor = EmergencyRedLight,
                        iconColor = EmergencyRed,
                        onClick = onNavigateToEmergency
                    )
                }

                Spacer(modifier = Modifier.height(120.dp)) // Space for bottom nav
            }

            // Floating Navigation Bar
            FloatingNavigationBar(
                items = navItems,
                selectedIndex = selectedNavIndex,
                onItemSelected = { index -> 
                    selectedNavIndex = index
                    if (index == 2) onSwitchRole() // Use Profile tab to switch role for demo purposes
                    if (index == 1) onNavigateToReminders()
                },
                modifier = Modifier.align(Alignment.BottomCenter)
            )

            if (uiState.isLoading) {
                LoadingOverlay()
            }
        }
    }
}
