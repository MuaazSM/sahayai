package com.sahayai.android.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = PrimaryBlue,
    onPrimary = SurfaceWhite,
    primaryContainer = PrimaryBlueLight,
    onPrimaryContainer = PrimaryBlue,
    secondary = MetricMintDark,
    onSecondary = SurfaceWhite,
    secondaryContainer = MetricMint,
    background = BackgroundCalm,
    onBackground = TextPrimary,
    surface = SurfaceWhite,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceWhite,
    onSurfaceVariant = TextSecondary,
    error = AlertCritical,
    errorContainer = AlertCriticalLight,
    outline = TextTertiary.copy(alpha = 0.3f)
)

@Composable
fun SahayAITheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = SahayTypography,
        shapes = SahayShapes,
        content = content
    )
}