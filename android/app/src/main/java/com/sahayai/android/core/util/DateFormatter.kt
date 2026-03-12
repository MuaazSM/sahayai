package com.sahayai.android.core.util

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

object DateFormatter {
    private val displayFormatter = DateTimeFormatter.ofPattern("dd MMM")
    private val fullFormatter = DateTimeFormatter.ofPattern("dd MMM yyyy, HH:mm")
    private val isoFormatter = DateTimeFormatter.ISO_DATE

    fun formatShort(isoDate: String): String {
        return try {
            val date = LocalDate.parse(isoDate.take(10))
            date.format(displayFormatter)
        } catch (e: Exception) {
            isoDate.take(10)
        }
    }

    fun formatRelative(isoTimestamp: String): String {
        return try {
            val instant = Instant.parse(isoTimestamp)
            val now = Instant.now()
            val minutesAgo = ChronoUnit.MINUTES.between(instant, now)
            when {
                minutesAgo < 1 -> "Just now"
                minutesAgo < 60 -> "$minutesAgo min ago"
                minutesAgo < 1440 -> "${minutesAgo / 60}h ago"
                else -> "${minutesAgo / 1440}d ago"
            }
        } catch (e: Exception) {
            isoTimestamp.take(16).replace("T", " ")
        }
    }

    fun today(): String = LocalDate.now().format(isoFormatter)
}
