package com.sahayai.android.ui.caregiver.home

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
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Summarize
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.ui.components.AlertCard
import com.sahayai.android.ui.components.DashboardMetricCard
import com.sahayai.android.ui.components.FeatureActionCard
import com.sahayai.android.ui.components.FloatingNavigationBar
import com.sahayai.android.ui.components.HealthStatusCard
import com.sahayai.android.ui.components.NavItem
import com.sahayai.android.ui.theme.MetricLavender
import com.sahayai.android.ui.theme.MetricLavenderDark
import com.sahayai.android.ui.theme.MetricMint
import com.sahayai.android.ui.theme.MetricMintDark
import com.sahayai.android.ui.theme.MetricPeach
import com.sahayai.android.ui.theme.MetricPeachDark
import com.sahayai.android.ui.theme.PrimaryBlue
import com.sahayai.android.ui.theme.PrimaryBlueLight

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaregiverHomeScreen(
    onNavigateToAlerts: () -> Unit,
    onNavigateToSummary: () -> Unit,
    onNavigateToTrends: () -> Unit,
    onSwitchRole: () -> Unit,
    onAlertClick: (String) -> Unit,
    viewModel: CaregiverHomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Bottom Nav State
    var selectedNavIndex by remember { mutableStateOf(0) }
    val navItems = listOf(
        NavItem("Dashboard", Icons.Filled.Home),
        NavItem("Alerts", Icons.Filled.Notifications),
        NavItem("Trends", Icons.Filled.Assessment)
    )

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
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
                // Top Greeting
                HealthStatusCard(
                    userName = "Caregiver",
                    statusText = if (uiState.isWebSocketConnected) "Live Connection Active" else "Connecting...",
                    statusColor = if (uiState.isWebSocketConnected) MetricMintDark else MetricPeachDark
                )

                // Patient Metrics Grid
                uiState.summary?.let { summary ->
                    Column(modifier = Modifier.padding(horizontal = 24.dp)) {
                        Text(
                            text = "Patient Overview: ${summary.patientId}",
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
                                title = "CCT Score",
                                value = "${summary.aacScore.toInt()}%",
                                icon = Icons.Filled.Assessment,
                                tintColor = PrimaryBlueLight,
                                iconColor = PrimaryBlue,
                                modifier = Modifier.weight(1f)
                            )
                            DashboardMetricCard(
                                title = "Reminders",
                                value = "${summary.remindersCompleted}/${summary.remindersTotal}",
                                icon = Icons.AutoMirrored.Filled.List,
                                tintColor = MetricLavender,
                                iconColor = MetricLavenderDark,
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(32.dp))

                // Actions
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
                        title = "Daily Summary",
                        subtitle = "View comprehensive daily report",
                        icon = Icons.Filled.Summarize,
                        iconContainerColor = MetricMint,
                        iconColor = MetricMintDark,
                        onClick = onNavigateToSummary
                    )
                    FeatureActionCard(
                        title = "Cognitive Trends",
                        subtitle = "Track progression over time",
                        icon = Icons.Filled.Assessment,
                        iconContainerColor = MetricPeach,
                        iconColor = MetricPeachDark,
                        onClick = onNavigateToTrends
                    )
                    FeatureActionCard(
                        title = "Switch to Patient View",
                        subtitle = "Use the app as your patient",
                        icon = Icons.Filled.Person,
                        iconContainerColor = PrimaryBlueLight,
                        iconColor = PrimaryBlue,
                        onClick = onSwitchRole
                    )
                }

                Spacer(modifier = Modifier.height(32.dp))

                // Alerts Timeline Feed
                Column(modifier = Modifier.padding(horizontal = 24.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Recent Alerts",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        TextButton(onClick = onNavigateToAlerts) {
                            Text(text = "View All", color = PrimaryBlue)
                        }
                    }
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    if (uiState.alerts.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No active alerts",
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            uiState.alerts.take(3).forEach { alert ->
                                AlertCard(
                                    alert = alert,
                                    onClick = { onAlertClick(alert.id) }
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(120.dp)) // Space for bottom nav
            }

            // Floating Navigation Bar
            FloatingNavigationBar(
                items = navItems,
                selectedIndex = selectedNavIndex,
                onItemSelected = { index ->
                    selectedNavIndex = index
                    if (index == 1) onNavigateToAlerts()
                    if (index == 2) onNavigateToTrends()
                },
                modifier = Modifier.align(Alignment.BottomCenter)
            )
        }
    }
}
