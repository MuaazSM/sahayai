package com.sahayai.android.ui.patient.emergency

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.ui.theme.EmergencyRed
import com.sahayai.android.ui.theme.EmergencyRedLight
import kotlinx.coroutines.launch

@Composable
fun EmergencyScreen(
    onBack: () -> Unit,
    viewModel: EmergencyViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current

    val locationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions(),
        onResult = { result ->
            val granted = result.values.any { it }
            if (granted) {
                viewModel.onSosPressed()
            } else {
                coroutineScope.launch {
                    snackbarHostState.showSnackbar("Location permission is required to share your safety status.")
                }
            }
        }
    )

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
            viewModel.dismissError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Color.Transparent
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    brush = Brush.verticalGradient(
                        colors = listOf(
                            EmergencyRed,
                            Color(0xFF8B0000)
                        )
                    )
                )
                .padding(innerPadding)
        ) {
            // Back button top-left
            IconButton(
                onClick = onBack,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(8.dp)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "Back",
                    tint = Color.White,
                    modifier = Modifier.size(32.dp)
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 24.dp, vertical = 80.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Header section
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "EMERGENCY HELP",
                        fontSize = 34.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = Color.White,
                        textAlign = TextAlign.Center,
                        letterSpacing = 2.sp
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "SahayAI will alert your caregiver immediately",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color.White.copy(alpha = 0.9f),
                        textAlign = TextAlign.Center,
                        lineHeight = 30.sp
                    )
                }

                // SOS Button
                SosPulseButton(
                    isSending = uiState.isSending,
                    alertSent = uiState.alertSent,
                    onClick = {
                        val hasLocationPermission = listOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION
                        ).any { permission ->
                            ContextCompat.checkSelfPermission(
                                context,
                                permission
                            ) == PackageManager.PERMISSION_GRANTED
                        }
                        if (hasLocationPermission) {
                            viewModel.onSosPressed()
                        } else {
                            locationPermissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                    Manifest.permission.ACCESS_COARSE_LOCATION
                                )
                            )
                        }
                    }
                )

                // Status/Confirmation section
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 24.dp)
                ) {
                    AnimatedVisibility(
                        visible = uiState.alertSent,
                        enter = fadeIn() + scaleIn(),
                        exit = fadeOut()
                    ) {
                        AlertSentConfirmation(
                            caregiverNotified = uiState.caregiverNotified,
                            statusMessage = uiState.statusMessage
                        )
                    }

                    AnimatedVisibility(
                        visible = uiState.isSending,
                        enter = fadeIn(),
                        exit = fadeOut()
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(
                                color = Color.White,
                                modifier = Modifier.size(40.dp),
                                strokeWidth = 4.dp
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = uiState.statusMessage,
                                fontSize = 20.sp,
                                color = Color.White,
                                textAlign = TextAlign.Center,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }

                    if (!uiState.alertSent && !uiState.isSending) {
                        Text(
                            text = "Press the button above to send an emergency alert to your caregiver.",
                            fontSize = 18.sp,
                            color = Color.White.copy(alpha = 0.8f),
                            textAlign = TextAlign.Center,
                            lineHeight = 26.sp
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SosPulseButton(
    isSending: Boolean,
    alertSent: Boolean,
    onClick: () -> Unit
) {
    val infiniteTransition = rememberInfiniteTransition(label = "sos_pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.12f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 700),
            repeatMode = RepeatMode.Reverse
        ),
        label = "sos_pulse_scale"
    )

    val buttonScale = if (!isSending && !alertSent) pulseScale else 1f

    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier.size(160.dp)
    ) {
        // Outer glow ring
        Box(
            modifier = Modifier
                .size(160.dp)
                .scale(buttonScale)
                .border(
                    width = 4.dp,
                    color = Color.White.copy(alpha = 0.4f),
                    shape = CircleShape
                )
        )

        // SOS circular button
        Button(
            onClick = onClick,
            enabled = !isSending && !alertSent,
            modifier = Modifier
                .size(120.dp)
                .scale(buttonScale),
            shape = CircleShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = if (alertSent) Color(0xFF4CAF50) else Color.White,
                disabledContainerColor = if (alertSent) Color(0xFF4CAF50) else Color.White.copy(alpha = 0.7f)
            ),
            elevation = ButtonDefaults.buttonElevation(
                defaultElevation = 12.dp,
                pressedElevation = 4.dp
            )
        ) {
            Icon(
                imageVector = if (alertSent) Icons.Filled.CheckCircle else Icons.Filled.Warning,
                contentDescription = if (alertSent) "Alert Sent" else "SOS",
                tint = if (alertSent) Color(0xFF4CAF50) else EmergencyRed,
                modifier = Modifier.size(56.dp)
            )
        }
    }
}

@Composable
private fun AlertSentConfirmation(
    caregiverNotified: Boolean,
    statusMessage: String
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .fillMaxWidth()
            .background(
                color = Color.White.copy(alpha = 0.15f),
                shape = MaterialTheme.shapes.large
            )
            .padding(20.dp)
    ) {
        Icon(
            imageVector = Icons.Filled.CheckCircle,
            contentDescription = "Alert sent",
            tint = Color.White,
            modifier = Modifier.size(48.dp)
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            text = "Alert Sent!",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = statusMessage,
            fontSize = 20.sp,
            color = Color.White.copy(alpha = 0.9f),
            textAlign = TextAlign.Center,
            lineHeight = 28.sp
        )
        if (caregiverNotified) {
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .background(Color(0xFF4CAF50), CircleShape)
                )
                Text(
                    text = "Caregiver notified",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = EmergencyRedLight
                )
            }
        }
    }
}
