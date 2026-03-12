package com.sahayai.android.ui.caregiver.summary

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.DirectionsWalk
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Medication
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.domain.model.CaregiverSummary
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.ui.components.SahayAITopBar
import com.sahayai.android.ui.components.StatusBadge
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.AlertHigh
import com.sahayai.android.ui.theme.AlertLow
import com.sahayai.android.ui.theme.AlertMedium
import com.sahayai.android.ui.theme.SahayBlue500
import com.sahayai.android.ui.theme.SahayGreen400

@Composable
fun DailySummaryScreen(
    onBack: () -> Unit,
    viewModel: DailySummaryViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
        }
    }

    Scaffold(
        topBar = {
            SahayAITopBar(title = "Daily Summary", onBack = onBack)
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { innerPadding ->
        if (uiState.isLoading && uiState.summary == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                uiState.summary?.let { summary ->
                    StatsGrid(summary = summary)
                    MoodSummaryCard(moodSummary = summary.moodSummary)
                }

                if (uiState.recentTrends.isNotEmpty()) {
                    CctMiniChart(
                        trends = uiState.recentTrends,
                        avgCctScore = uiState.summary?.avgCctScore ?: 0f
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun StatsGrid(summary: CaregiverSummary) {
    val riskColor = when (summary.riskLevel.uppercase()) {
        "CRITICAL" -> AlertCritical
        "HIGH" -> AlertHigh
        "MEDIUM" -> AlertMedium
        else -> AlertLow
    }

    Column {
        Text(
            text = "Today's Overview",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            StatCard(
                icon = Icons.AutoMirrored.Filled.DirectionsWalk,
                label = "Steps",
                value = summary.stepsToday.toString(),
                iconTint = SahayBlue500,
                modifier = Modifier.weight(1f)
            )
            StatCard(
                icon = Icons.Filled.Medication,
                label = "Reminders",
                value = "${summary.remindersCompleted}/${summary.remindersTotal}",
                iconTint = SahayGreen400,
                modifier = Modifier.weight(1f)
            )
        }
        Spacer(modifier = Modifier.height(10.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            StatCard(
                icon = Icons.Filled.Forum,
                label = "Conversations",
                value = summary.conversationsToday.toString(),
                iconTint = AlertMedium,
                modifier = Modifier.weight(1f)
            )
            RiskLevelCard(
                riskLevel = summary.riskLevel,
                riskColor = riskColor,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun StatCard(
    icon: ImageVector,
    label: String,
    value: String,
    iconTint: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalAlignment = Alignment.Start
        ) {
            androidx.compose.material3.Icon(
                imageVector = icon,
                contentDescription = label,
                tint = iconTint,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = value,
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun RiskLevelCard(
    riskLevel: String,
    riskColor: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalAlignment = Alignment.Start
        ) {
            androidx.compose.material3.Icon(
                imageVector = Icons.Filled.Security,
                contentDescription = "Risk level",
                tint = riskColor,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.height(8.dp))
            StatusBadge(
                text = riskLevel,
                backgroundColor = riskColor,
                textColor = if (riskLevel.uppercase() == "MEDIUM") Color.Black else Color.White
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Risk Level",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun MoodSummaryCard(moodSummary: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Mood & Wellness Summary",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSecondaryContainer
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = moodSummary.ifBlank { "No mood data available for today." },
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
                lineHeight = 24.sp
            )
        }
    }
}

@Composable
private fun CctMiniChart(
    trends: List<CognitiveTrendPoint>,
    avgCctScore: Float
) {
    val scoreColor = when {
        avgCctScore >= 70f -> SahayGreen400
        avgCctScore >= 40f -> AlertMedium
        else -> AlertCritical
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "CCT Score — Last 7 Days",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold
                )
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "Avg: ${avgCctScore.toInt()}",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        color = scoreColor
                    )
                    Text(
                        text = "out of 100",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Score pill row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                trends.forEach { point ->
                    ScorePill(
                        score = point.cctScore,
                        date = point.date.takeLast(5),
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}

@Composable
private fun ScorePill(
    score: Float,
    date: String,
    modifier: Modifier = Modifier
) {
    val pillColor = when {
        score >= 70f -> SahayGreen400
        score >= 40f -> AlertMedium
        else -> AlertCritical
    }

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(pillColor.copy(alpha = 0.15f), RoundedCornerShape(6.dp))
                .padding(vertical = 6.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = score.toInt().toString(),
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = pillColor
            )
        }
        Text(
            text = date,
            fontSize = 9.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
