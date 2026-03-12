package com.sahayai.android.ui.patient.conversation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.repository.ConversationRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ConversationUiState(
    val isListening: Boolean = false,
    val isSpeaking: Boolean = false,
    val isAwaitingResponse: Boolean = false,
    val transcribedText: String = "",
    val responseText: String = "",
    val aacScore: Float = 0f,
    val emrMemory: String? = null,
    val error: String? = null
)

@HiltViewModel
class ConversationViewModel @Inject constructor(
    private val conversationRepository: ConversationRepository,
    private val ttsManager: TtsManager,
    private val speechRecognitionManager: SpeechRecognitionManager,
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private var userId: String = ""

    private val _uiState = MutableStateFlow(ConversationUiState())
    val uiState: StateFlow<ConversationUiState> = _uiState

    init {
        observeSpeechState()
        observeTtsState()
        observeUserPrefs()
    }

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    fun startListening() {
        ttsManager.stop()
        speechRecognitionManager.startListening(
            onResult = { text -> onSpeechResult(text) },
            onError = { code ->
                _uiState.update { it.copy(error = speechErrorMessage(code), isListening = false) }
            }
        )
    }

    fun stopListening() {
        speechRecognitionManager.stopListening()
    }

    fun stopAudio() {
        speechRecognitionManager.stopListening()
        ttsManager.stop()
    }

    fun onSpeechResult(text: String) {
        if (text.isBlank()) return
        _uiState.update { it.copy(transcribedText = text, isAwaitingResponse = true, error = null) }
        sendMessage(text)
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private fun sendMessage(message: String) {
        val targetUserId = userId.takeIf { it.isNotBlank() } ?: run {
            _uiState.update {
                it.copy(
                    isAwaitingResponse = false,
                    error = "Please complete onboarding to start a conversation."
                )
            }
            return
        }

        viewModelScope.launch {
            when (val result = conversationRepository.sendMessage(targetUserId, message)) {
                is NetworkResult.Success -> {
                    val response = result.data
                    _uiState.update {
                        it.copy(
                            isAwaitingResponse = false,
                            responseText = response.responseText,
                            aacScore = response.aacScore,
                            emrMemory = if (response.emrTriggered) response.emrMemory else null,
                            error = null
                        )
                    }
                    ttsManager.speak(response.responseText)
                }

                is NetworkResult.Error -> {
                    _uiState.update {
                        it.copy(
                            isAwaitingResponse = false,
                            error = result.message
                        )
                    }
                }

                is NetworkResult.Loading -> {
                    // Already handled via isAwaitingResponse = true above.
                }
            }
        }
    }

    private fun observeUserPrefs() {
        viewModelScope.launch {
            prefsRepository.userPreferences.collect { prefs ->
                if (prefs.userId.isNotBlank()) {
                    userId = prefs.userId
                }
            }
        }
    }

    private fun observeSpeechState() {
        viewModelScope.launch {
            speechRecognitionManager.isListening.collect { listening ->
                _uiState.update { it.copy(isListening = listening) }
            }
        }
        viewModelScope.launch {
            speechRecognitionManager.partialText.collect { partial ->
                _uiState.update { it.copy(transcribedText = partial) }
            }
        }
    }

    private fun observeTtsState() {
        viewModelScope.launch {
            ttsManager.isSpeaking.collect { speaking ->
                _uiState.update { it.copy(isSpeaking = speaking) }
            }
        }
    }

    private fun speechErrorMessage(errorCode: Int): String = when (errorCode) {
        android.speech.SpeechRecognizer.ERROR_AUDIO -> "Microphone error. Please try again."
        android.speech.SpeechRecognizer.ERROR_NO_MATCH -> "Could not understand. Please speak clearly."
        android.speech.SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech detected. Please try again."
        android.speech.SpeechRecognizer.ERROR_NETWORK,
        android.speech.SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network error. Check your connection."
        android.speech.SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission required."
        else -> "Speech recognition error. Please try again."
    }

    override fun onCleared() {
        super.onCleared()
        speechRecognitionManager.destroy()
        ttsManager.shutdown()
    }
}
