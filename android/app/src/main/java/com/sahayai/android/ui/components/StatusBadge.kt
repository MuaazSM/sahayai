package com.sahayai.android.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.AlertHigh
import com.sahayai.android.ui.theme.AlertLow
import com.sahayai.android.ui.theme.AlertMedium

@Composable
fun StatusBadge(
    text: String,
    backgroundColor: Color,
    textColor: Color = Color.White,
    modifier: Modifier = Modifier
) {
    Text(
        text = text,
        modifier = modifier
            .background(backgroundColor, RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        color = textColor,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
fun PriorityBadge(priority: String, modifier: Modifier = Modifier) {
    val (bg, text) = when (priority.uppercase()) {
        "CRITICAL" -> AlertCritical to "CRITICAL"
        "HIGH" -> AlertHigh to "HIGH"
        "MEDIUM" -> AlertMedium to "MEDIUM"
        else -> AlertLow to "LOW"
    }
    StatusBadge(
        text = text,
        backgroundColor = bg,
        textColor = if (priority.uppercase() == "MEDIUM") Color.Black else Color.White,
        modifier = modifier
    )
}
