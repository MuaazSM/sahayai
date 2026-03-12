package com.sahayai.android.ui.caregiver.alerts

import android.content.Intent
import android.net.Uri
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
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.domain.model.Alert
import com.sahayai.android.ui.components.PriorityBadge
import com.sahayai.android.ui.components.SahayAITopBar
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.AlertHigh
import com.sahayai.android.ui.theme.AlertLow
import com.sahayai.android.ui.theme.AlertMedium
import com.sahayai.android.ui.theme.SahayGreen400

@Composable
fun AlertDetailScreen(
    onBack: () -> Unit,
    viewModel: AlertDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
            viewModel.dismissError()
        }
    }

    Scaffold(
        topBar = {
            SahayAITopBar(
                title = uiState.alert?.title ?: "Alert Detail",
                onBack = onBack
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { innerPadding ->
        when {
            uiState.isLoading && uiState.alert == null -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }

            uiState.alert != null -> {
                AlertDetailContent(
                    alert = uiState.alert!!,
                    isAcknowledged = uiState.isAcknowledged,
                    isLoading = uiState.isLoading,
                    onAcknowledge = viewModel::acknowledgeAlert,
                    onCallPatient = {
                        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:"))
                        context.startActivity(intent)
                    },
                    onDismiss = onBack,
                    modifier = Modifier.padding(innerPadding)
                )
            }

            else -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Alert not found.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun AlertDetailContent(
    alert: Alert,
    isAcknowledged: Boolean,
    isLoading: Boolean,
    onAcknowledge: () -> Unit,
    onCallPatient: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    val priorityColor = when (alert.priority.uppercase()) {
        "CRITICAL" -> AlertCritical
        "HIGH" -> AlertHigh
        "MEDIUM" -> AlertMedium
        else -> AlertLow
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Priority banner at top
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    color = priorityColor.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(12.dp)
                )
                .padding(16.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.NotificationsActive,
                    contentDescription = null,
                    tint = priorityColor,
                    modifier = Modifier.size(36.dp)
                )
                Column {
                    PriorityBadge(priority = alert.priority)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = alert.title,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }

        // Acknowledged banner
        if (isAcknowledged) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        color = SahayGreen400.copy(alpha = 0.12f),
                        shape = RoundedCornerShape(10.dp)
                    )
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.CheckCircle,
                    contentDescription = null,
                    tint = SahayGreen400,
                    modifier = Modifier.size(24.dp)
                )
                Text(
                    text = "This alert has been acknowledged",
                    color = SahayGreen400,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 16.sp
                )
            }
        }

        // Alert details card
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                AlertDetailRow(label = "Alert Type", value = alert.alertType.replace("_", " "))
                HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                AlertDetailRow(label = "Priority", value = alert.priority)
                HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                AlertDetailRow(
                    label = "Created",
                    value = alert.createdAt.take(16).replace("T", "  ")
                )
                if (alert.acknowledgedAt != null) {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                    AlertDetailRow(
                        label = "Acknowledged at",
                        value = alert.acknowledgedAt.take(16).replace("T", "  ")
                    )
                }
                if (!alert.acknowledgedBy.isNullOrBlank()) {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))
                    AlertDetailRow(label = "Acknowledged by", value = alert.acknowledgedBy)
                }
            }
        }

        // Description card
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "Description",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = alert.description,
                    style = MaterialTheme.typography.bodyLarge,
                    lineHeight = 24.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Action buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Button(
                onClick = onAcknowledge,
                enabled = !isAcknowledged && !isLoading,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = SahayGreen400
                )
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        color = Color.White,
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(
                        imageVector = Icons.Filled.CheckCircle,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                }
                Text(
                    text = if (isAcknowledged) "Acknowledged" else "Acknowledge",
                    modifier = Modifier.padding(start = 4.dp),
                    fontWeight = FontWeight.SemiBold
                )
            }

            FilledTonalButton(
                onClick = onCallPatient,
                modifier = Modifier.weight(1f)
            ) {
                Icon(
                    imageVector = Icons.Filled.Call,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Text(
                    text = "Call Patient",
                    modifier = Modifier.padding(start = 4.dp)
                )
            }
        }

        OutlinedButton(
            onClick = onDismiss,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(
                imageVector = Icons.Filled.Close,
                contentDescription = null,
                modifier = Modifier.size(18.dp)
            )
            Text(
                text = "Dismiss",
                modifier = Modifier.padding(start = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun AlertDetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(0.4f)
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.weight(0.6f)
        )
    }
}
