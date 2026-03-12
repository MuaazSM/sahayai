package com.sahayai.android.core.util

import android.content.Context
import android.widget.Toast

fun Context.showToast(message: String) {
    Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}

fun String.toSentenceCase(): String {
    return if (isEmpty()) this
    else this[0].uppercaseChar() + substring(1).lowercase()
}

fun Float.toPercent(): String = "${(this).toInt()}%"

fun Long.toReadableDate(): String {
    val date = java.util.Date(this)
    val format = java.text.SimpleDateFormat("dd MMM yyyy", java.util.Locale.getDefault())
    return format.format(date)
}
