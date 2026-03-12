package com.sahayai.android.ui.components

import androidx.compose.animation.animateColor
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.SahayBlue500

@Composable
fun LargeMicButton(
    isListening: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "mic_pulse")
    val pulseColor by infiniteTransition.animateColor(
        initialValue = AlertCritical,
        targetValue = AlertCritical.copy(alpha = 0.6f),
        animationSpec = infiniteRepeatable(
            animation = tween(700),
            repeatMode = RepeatMode.Reverse
        ),
        label = "mic_pulse_color"
    )

    FloatingActionButton(
        onClick = onClick,
        modifier = modifier.size(96.dp),
        shape = CircleShape,
        containerColor = if (isListening) pulseColor else SahayBlue500,
        elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 8.dp)
    ) {
        Icon(
            imageVector = if (isListening) Icons.Filled.MicOff else Icons.Filled.Mic,
            contentDescription = if (isListening) "Stop listening" else "Start listening",
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.onPrimary
        )
    }
}
