package com.sahayai.android.ui.navigation

import androidx.lifecycle.ViewModel
import com.sahayai.android.core.datastore.UserPreferencesRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class NavViewModel @Inject constructor(
    val prefsRepository: UserPreferencesRepository
) : ViewModel()
