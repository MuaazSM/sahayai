package com.sahayai.android.ui.caregiver.trends

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.CognitiveTrendPoint
import com.sahayai.android.domain.repository.CaregiverRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class TrendDimension { CCT_SCORE, AAC_SCORE }

data class CognitiveTrendUiState(
    val trendPoints: List<CognitiveTrendPoint> = emptyList(),
    val selectedDimension: TrendDimension = TrendDimension.CCT_SCORE,
    val isLoading: Boolean = false,
    val error: String? = null
) {
    val minScore: Float
        get() = if (trendPoints.isEmpty()) 0f else
            trendPoints.minOf { scoreFor(it, selectedDimension) }

    val maxScore: Float
        get() = if (trendPoints.isEmpty()) 0f else
            trendPoints.maxOf { scoreFor(it, selectedDimension) }

    val avgScore: Float
        get() = if (trendPoints.isEmpty()) 0f else
            trendPoints.map { scoreFor(it, selectedDimension) }.average().toFloat()

    private fun scoreFor(point: CognitiveTrendPoint, dimension: TrendDimension): Float =
        when (dimension) {
            TrendDimension.CCT_SCORE -> point.cctScore
            TrendDimension.AAC_SCORE -> point.aacScore ?: 0f
        }
}

@HiltViewModel
class CognitiveTrendViewModel @Inject constructor(
    private val caregiverRepository: CaregiverRepository,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(CognitiveTrendUiState())
    val uiState: StateFlow<CognitiveTrendUiState> = _uiState

    init {
        loadTrends()
    }

    fun loadTrends() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            val prefs = runCatching { prefsRepository.userPreferences.first() }.getOrNull()
            val patientId = prefs?.patientId?.takeIf { it.isNotBlank() } ?: run {
                _uiState.update { it.copy(isLoading = false, error = "Patient ID not configured.") }
                return@launch
            }

            // Trigger network refresh first
            caregiverRepository.refreshTrends(patientId)

            // Then collect from local cache
            caregiverRepository.getCognitiveTrends(patientId).first { result ->
                when (result) {
                    is NetworkResult.Success -> {
                        _uiState.update { state ->
                            state.copy(
                                trendPoints = result.data.takeLast(14),
                                isLoading = false,
                                error = null
                            )
                        }
                        true
                    }
                    is NetworkResult.Error -> {
                        _uiState.update { it.copy(isLoading = false, error = result.message) }
                        true
                    }
                    NetworkResult.Loading -> false
                }
            }
        }
    }

    fun selectDimension(dimension: TrendDimension) {
        _uiState.update { it.copy(selectedDimension = dimension) }
    }
}
