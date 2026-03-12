package com.sahayai.android.domain.model

enum class UserRole { PATIENT, CAREGIVER }

data class UserPreferences(
    val onboardingDone: Boolean = false,
    val userRole: UserRole = UserRole.PATIENT,
    val userId: String = "",
    val patientId: String = "",
    val userName: String = ""
)
