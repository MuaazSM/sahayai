package com.sahayai.android.ui.patient.conversation

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Spa
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.core.content.ContextCompat
import com.sahayai.android.ui.components.LargeMicButton
import com.sahayai.android.ui.components.SahayAITopBar
import com.sahayai.android.ui.theme.AlertHigh
import com.sahayai.android.ui.theme.SahayBlue100
import com.sahayai.android.ui.theme.SahayBlue50
import com.sahayai.android.ui.theme.SahayBlue500
import com.sahayai.android.ui.theme.SahayBlue700
import com.sahayai.android.ui.theme.SahayGray600
import com.sahayai.android.ui.theme.SahayWarmOrange100
import com.sahayai.android.ui.theme.SahayWarmOrange500
import kotlinx.coroutines.launch
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner

@Composable
fun ConversationScreen(
    onBack: () -> Unit,
    viewModel: ConversationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted ->
            if (granted) {
                viewModel.startListening()
            } else {
                coroutineScope.launch {
                    snackbarHostState.showSnackbar("Microphone permission is required to talk to SahayAI.")
                }
            }
        }
    )

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                viewModel.stopAudio()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.stopAudio()
        }
    }

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
            viewModel.clearError()
        }
    }

    Scaffold(
        topBar = {
            SahayAITopBar(
                title = "Conversation",
                onBack = onBack
            )
        },
        snackbarHost = {
            SnackbarHost(hostState = snackbarHostState) { data ->
                Snackbar(
                    snackbarData = data,
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(24.dp)
            ) {
                Spacer(modifier = Modifier.height(8.dp))

                // Transcription card (User Message Bubble)
                if (uiState.isListening || uiState.transcribedText.isNotBlank()) {
                    UserMessageBubble(
                        text = uiState.transcribedText,
                        isListening = uiState.isListening,
                        modifier = Modifier.align(Alignment.End)
                    )
                }

                // AI Response (AI Message Bubble)
                AnimatedVisibility(
                    visible = uiState.responseText.isNotBlank() || uiState.isAwaitingResponse,
                    enter = fadeIn() + slideInVertically(initialOffsetY = { it / 2 })
                ) {
                    AiMessageBubble(
                        text = uiState.responseText,
                        isAwaiting = uiState.isAwaitingResponse,
                        aacScore = uiState.aacScore,
                        modifier = Modifier.align(Alignment.Start)
                    )
                }

                // EMR memory card
                val emrMemory = uiState.emrMemory
                if (!emrMemory.isNullOrBlank()) {
                    EmrMemoryCard(
                        memoryText = emrMemory,
                        modifier = Modifier.fillMaxWidth()
                    )
                }

                Spacer(modifier = Modifier.height(140.dp))
            }

            // Mic button pinned to the bottom centre
            LargeMicButton(
                isListening = uiState.isListening,
                onClick = {
                    if (uiState.isListening) {
                        viewModel.stopListening()
                    } else {
                        val granted = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED
                        if (granted) {
                            viewModel.startListening()
                        } else {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    }
                },
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 32.dp)
            )
        }
    }
}

@Composable
private fun UserMessageBubble(
    text: String,
    isListening: Boolean,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(0.85f),
        horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.Bottom
    ) {
        Card(
            shape = RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp),
            colors = CardDefaults.cardColors(containerColor = SahayBlue500),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Text(
                text = if (text.isBlank() && isListening) "Listening…" else text,
                style = MaterialTheme.typography.bodyLarge.copy(
                    color = Color.White,
                    fontStyle = if (text.isBlank()) FontStyle.Italic else FontStyle.Normal
                ),
                modifier = Modifier.padding(16.dp)
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .size(32.dp)
                .background(SahayBlue100, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Filled.Person,
                contentDescription = null,
                tint = SahayBlue500,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

@Composable
private fun AiMessageBubble(
    text: String,
    isAwaiting: Boolean,
    aacScore: Float,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(0.9f),
        horizontalArrangement = Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .background(SahayBlue50, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Filled.AutoAwesome,
                contentDescription = null,
                tint = SahayBlue500,
                modifier = Modifier.size(22.dp)
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Column(horizontalAlignment = Alignment.Start) {
            Card(
                shape = RoundedCornerShape(4.dp, 20.dp, 20.dp, 20.dp),
                colors = CardDefaults.cardColors(containerColor = SahayBlue100),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    if (isAwaiting && text.isBlank()) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = SahayBlue500,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = text,
                            style = MaterialTheme.typography.bodyLarge.copy(
                                fontSize = 20.sp,
                                lineHeight = 28.sp,
                                color = SahayBlue700
                            )
                        )
                    }
                }
            }
            if (aacScore > 0f) {
                Spacer(modifier = Modifier.height(8.dp))
                AacScoreBadge(score = aacScore)
            }
        }
    }
}

@Composable
private fun AacScoreBadge(score: Float) {
    val displayScore = score.toInt().coerceIn(0, 100)
    val (badgeColor, label) = when {
        displayScore >= 70 -> Color(0xFF27AE60) to "Independent"
        displayScore >= 40 -> Color(0xFFF39C12) to "Assisted"
        else -> Color(0xFFE74C3C) to "Needs Help"
    }

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = badgeColor.copy(alpha = 0.12f),
        border = androidx.compose.foundation.BorderStroke(1.dp, badgeColor.copy(alpha = 0.5f))
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(badgeColor, CircleShape)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "AAC $displayScore • $label",
                style = MaterialTheme.typography.labelSmall.copy(
                    color = badgeColor,
                    fontWeight = FontWeight.Bold
                )
            )
        }
    }
}

@Composable
private fun EmrMemoryCard(
    memoryText: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = SahayWarmOrange100),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, SahayWarmOrange500.copy(alpha = 0.2f))
    ) {
        Column(modifier = Modifier.padding(24.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Filled.Spa,
                    contentDescription = null,
                    tint = SahayWarmOrange500,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = "A Warm Memory",
                    style = MaterialTheme.typography.titleMedium.copy(
                        color = SahayWarmOrange500,
                        fontWeight = FontWeight.Bold
                    )
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = memoryText,
                style = MaterialTheme.typography.bodyLarge.copy(
                    color = SahayBlue700,
                    lineHeight = 30.sp,
                    fontStyle = FontStyle.Italic
                )
            )
        }
    }
}
