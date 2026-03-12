package com.sahayai.android.ui.caregiver.trends

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.patrykandpatrick.vico.compose.cartesian.CartesianChartHost
import com.patrykandpatrick.vico.compose.cartesian.axis.rememberBottomAxis
import com.patrykandpatrick.vico.compose.cartesian.axis.rememberStartAxis
import com.patrykandpatrick.vico.compose.cartesian.layer.rememberLineCartesianLayer
import com.patrykandpatrick.vico.compose.cartesian.rememberCartesianChart
import com.patrykandpatrick.vico.compose.common.ProvideVicoTheme
import com.patrykandpatrick.vico.compose.m3.common.rememberM3VicoTheme
import com.patrykandpatrick.vico.core.cartesian.axis.VerticalAxis
import com.patrykandpatrick.vico.core.cartesian.data.CartesianChartModelProducer
import com.patrykandpatrick.vico.core.cartesian.data.lineSeries
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.ui.components.SahayAITopBar
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.AlertMedium
import com.sahayai.android.ui.theme.SahayGreen400

@Composable
fun CognitiveTrendScreen(
    onBack: () -> Unit,
    viewModel: CognitiveTrendViewModel = hiltViewModel()
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
            SahayAITopBar(title = "Cognitive Trends", onBack = onBack)
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { innerPadding ->
        if (uiState.isLoading && uiState.trendPoints.isEmpty()) {
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
                // Dimension filter chips
                DimensionFilterRow(
                    selectedDimension = uiState.selectedDimension,
                    onSelect = viewModel::selectDimension
                )

                // Line chart
                if (uiState.trendPoints.isNotEmpty()) {
                    TrendLineChart(
                        trendPoints = uiState.trendPoints,
                        selectedDimension = uiState.selectedDimension
                    )
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "No trend data available.",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                // Stats row
                if (uiState.trendPoints.isNotEmpty()) {
                    TrendStatsRow(uiState = uiState)
                }

                // Trend note card
                TrendNoteCard(
                    selectedDimension = uiState.selectedDimension,
                    avgScore = uiState.avgScore
                )

                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun DimensionFilterRow(
    selectedDimension: TrendDimension,
    onSelect: (TrendDimension) -> Unit
) {
    LazyRow(
        contentPadding = PaddingValues(vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(TrendDimension.values()) { dimension ->
            FilterChip(
                selected = selectedDimension == dimension,
                onClick = { onSelect(dimension) },
                label = {
                    Text(
                        text = when (dimension) {
                            TrendDimension.CCT_SCORE -> "CCT Score"
                            TrendDimension.AAC_SCORE -> "AAC Score"
                        },
                        fontWeight = if (selectedDimension == dimension)
                            FontWeight.SemiBold else FontWeight.Normal
                    )
                }
            )
        }
    }
}

@Composable
private fun TrendLineChart(
    trendPoints: List<CognitiveTrendPoint>,
    selectedDimension: TrendDimension
) {
    val scores = trendPoints.map { point ->
        when (selectedDimension) {
            TrendDimension.CCT_SCORE -> point.cctScore.toDouble()
            TrendDimension.AAC_SCORE -> (point.aacScore ?: 0f).toDouble()
        }
    }

    val modelProducer = remember { CartesianChartModelProducer() }

    LaunchedEffect(trendPoints, selectedDimension) {
        modelProducer.runTransaction {
            lineSeries {
                series(scores)
            }
        }
    }

    val dateLabels = trendPoints.map { it.date.takeLast(5) }

    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = when (selectedDimension) {
                    TrendDimension.CCT_SCORE -> "CCT Score — Last 14 Days"
                    TrendDimension.AAC_SCORE -> "AAC Score — Last 14 Days"
                },
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Score range: 0–100",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(12.dp))

            ProvideVicoTheme(rememberM3VicoTheme()) {
                CartesianChartHost(
                    chart = rememberCartesianChart(
                        rememberLineCartesianLayer(),
                        startAxis = rememberStartAxis(
                            itemPlacer = VerticalAxis.ItemPlacer.step({ 20.0 })
                        ),
                        bottomAxis = rememberBottomAxis(
                            valueFormatter = { value, _, _ ->
                                dateLabels.getOrElse(value.toInt()) { "" }
                            }
                        )
                    ),
                    modelProducer = modelProducer,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(220.dp)
                )
            }
        }
    }
}

@Composable
private fun TrendStatsRow(uiState: CognitiveTrendUiState) {
    val avgColor = when {
        uiState.avgScore >= 70f -> SahayGreen400
        uiState.avgScore >= 40f -> AlertMedium
        else -> AlertCritical
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        TrendStatCard(
            label = "Min",
            value = uiState.minScore.toInt().toString(),
            valueColor = AlertCritical,
            modifier = Modifier.weight(1f)
        )
        TrendStatCard(
            label = "Avg",
            value = uiState.avgScore.toInt().toString(),
            valueColor = avgColor,
            modifier = Modifier.weight(1f)
        )
        TrendStatCard(
            label = "Max",
            value = uiState.maxScore.toInt().toString(),
            valueColor = SahayGreen400,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun TrendStatCard(
    label: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = value,
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
                color = valueColor
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
private fun TrendNoteCard(
    selectedDimension: TrendDimension,
    avgScore: Float
) {
    val noteText = when (selectedDimension) {
        TrendDimension.CCT_SCORE -> when {
            avgScore >= 70f ->
                "CCT scores are in a healthy range. The patient is demonstrating strong conversational cognition — recall, coherence, and temporal orientation remain consistent."
            avgScore >= 40f ->
                "CCT scores show moderate cognitive engagement. Monitor for further changes; consider scheduling additional caregiver check-ins."
            else ->
                "CCT scores indicate low cognitive performance. Immediate caregiver review recommended. Consider escalating to healthcare provider."
        }
        TrendDimension.AAC_SCORE -> when {
            avgScore >= 70f ->
                "AAC (Adaptive Autonomy Calibration) score is high. The system is providing minimal assistance, respecting the patient's independence."
            avgScore >= 40f ->
                "AAC score is in a moderate range. The system is actively calibrating assistance levels. Observe patterns over the coming days."
            else ->
                "AAC score is low, indicating the system is providing high assistance. Patient may benefit from additional support resources."
        }
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = when (selectedDimension) {
                    TrendDimension.CCT_SCORE -> "About CCT Score"
                    TrendDimension.AAC_SCORE -> "About AAC Score"
                },
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSecondaryContainer
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = noteText,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
                lineHeight = 22.sp
            )
        }
    }
}
