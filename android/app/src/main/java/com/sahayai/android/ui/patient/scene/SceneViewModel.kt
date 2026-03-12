package com.sahayai.android.ui.patient.scene

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.repository.SceneRepository
import com.sahayai.android.ui.patient.conversation.TtsManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SceneUiState(
    val description: String = "",
    val objectsDetected: List<String> = emptyList(),
    val isAnalyzing: Boolean = false,
    val hasResult: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class SceneViewModel @Inject constructor(
    private val sceneRepository: SceneRepository,
    private val ttsManager: TtsManager,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private var userId: String? = null

    private val _uiState = MutableStateFlow(SceneUiState())
    val uiState: StateFlow<SceneUiState> = _uiState

    init {
        observeUser()
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    fun onImageCaptured(bytes: ByteArray) {
        val targetUserId = userId ?: run {
            _uiState.update {
                it.copy(
                    isAnalyzing = false,
                    hasResult = false,
                    error = "User ID missing. Please redo onboarding."
                )
            }
            return
        }

        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    isAnalyzing = true,
                    hasResult = false,
                    error = null,
                    description = "",
                    objectsDetected = emptyList()
                )
            }

            when (val result = sceneRepository.analyzeScene(targetUserId, bytes)) {
                is NetworkResult.Success -> {
                    val scene = result.data
                    _uiState.update {
                        it.copy(
                            description = scene.description,
                            objectsDetected = scene.objectsDetected,
                            isAnalyzing = false,
                            hasResult = true,
                            error = null
                        )
                    }
                    ttsManager.speak(scene.description)
                }

                is NetworkResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isAnalyzing = false,
                            hasResult = false,
                            error = result.message
                        )
                    }
                }

                is NetworkResult.Loading -> Unit
            }
        }
    }

    private fun observeUser() {
        viewModelScope.launch {
            prefsRepository.userPreferences.collect { prefs ->
                if (prefs.userId.isNotBlank()) {
                    userId = prefs.userId
                }
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    fun resetResult() {
        _uiState.update {
            it.copy(
                description = "",
                objectsDetected = emptyList(),
                hasResult = false,
                error = null
            )
        }
    }
}
