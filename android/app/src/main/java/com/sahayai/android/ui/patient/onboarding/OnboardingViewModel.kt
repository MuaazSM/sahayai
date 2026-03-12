package com.sahayai.android.ui.patient.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.sahayai.android.core.datastore.UserPreferencesRepository
import com.sahayai.android.domain.model.UserRole
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class OnboardingUiState(
    val selectedRole: UserRole = UserRole.PATIENT,
    val userId: String = "",
    val patientId: String = "",
    val userName: String = "",
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val prefsRepository: UserPreferencesRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(OnboardingUiState())
    val uiState: StateFlow<OnboardingUiState> = _uiState

    fun onRoleSelected(role: UserRole) {
        _uiState.value = _uiState.value.copy(selectedRole = role, error = null)
    }

    fun onUserIdChanged(id: String) {
        _uiState.value = _uiState.value.copy(userId = id, error = null)
    }

    fun onPatientIdChanged(id: String) {
        _uiState.value = _uiState.value.copy(patientId = id, error = null)
    }

    fun onUserNameChanged(name: String) {
        _uiState.value = _uiState.value.copy(userName = name)
    }

    fun onConfirm(onPatientDone: () -> Unit, onCaregiverDone: () -> Unit) {
        val state = _uiState.value
        if (state.userId.isBlank()) {
            _uiState.value = state.copy(error = "Please enter your User ID")
            return
        }
        if (state.selectedRole == UserRole.CAREGIVER && state.patientId.isBlank()) {
            _uiState.value = state.copy(error = "Please enter the Patient ID to monitor")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            prefsRepository.saveOnboarding(
                role = state.selectedRole,
                userId = state.userId,
                patientId = state.patientId,
                userName = state.userName
            )
            _uiState.value = _uiState.value.copy(isLoading = false)
            if (state.selectedRole == UserRole.PATIENT) onPatientDone() else onCaregiverDone()
        }
    }
}
