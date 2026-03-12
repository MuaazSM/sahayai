package com.sahayai.android.ui.theme

import androidx.compose.ui.graphics.Color

// Modern Healthcare Vibe (Apple Health / Whisker inspired)
val PrimaryBlue = Color(0xFF5E92F3)
val PrimaryBlueLight = Color(0xFFE3EDFE)

val BackgroundCalm = Color(0xFFF7F9FC)
val SurfaceWhite = Color(0xFFFFFFFF)

// Metric Card Tints
val MetricMint = Color(0xFFE8F5E9)
val MetricMintDark = Color(0xFF4CAF50)

val MetricPeach = Color(0xFFFBE9E7)
val MetricPeachDark = Color(0xFFFF7043)

val MetricLavender = Color(0xFFF3E5F5)
val MetricLavenderDark = Color(0xFF9C27B0)

val MetricSky = Color(0xFFE1F5FE)
val MetricSkyDark = Color(0xFF03A9F4)

// Text Colors
val TextPrimary = Color(0xFF111827)
val TextSecondary = Color(0xFF6B7280)
val TextTertiary = Color(0xFF9CA3AF)

// Alerts / Risks
val AlertCritical = Color(0xFFEF4444)
val AlertCriticalLight = Color(0xFFFEE2E2)

val AlertHigh = Color(0xFFF97316)
val AlertHighLight = Color(0xFFFFEDD5)

val AlertMedium = Color(0xFFF59E0B)
val AlertMediumLight = Color(0xFFFEF3C7)

val AlertLow = Color(0xFF10B981)
val AlertLowLight = Color(0xFFD1FAE5)

// Emergency
val EmergencyRed = Color(0xFFDC2626)
val EmergencyRedLight = Color(0xFFFEF2F2)

// Legacy Aliases to prevent compilation errors in un-refactored screens
val SahayBlue500 = PrimaryBlue
val SahayBlue700 = Color(0xFF1A5276) // Keep original dark blue for contrast where used
val SahayBlue100 = PrimaryBlueLight
val SahayBlue50 = Color(0xFFEBF5FB)
val SahayGreen400 = MetricMintDark
val SahayGreen100 = MetricMint
val SahayGreen50 = Color(0xFFEAFAF1)
val SahayGray100 = BackgroundCalm
val SahayGray300 = TextTertiary
val SahayGray600 = TextSecondary
val SahayWarmWhite = SurfaceWhite
val SahayIndigo500 = Color(0xFF5D6D7E)
val SahayWarmOrange100 = MetricPeach
val SahayWarmOrange500 = MetricPeachDark
val SahayPurple100 = MetricLavender
val SahayPurple500 = MetricLavenderDark