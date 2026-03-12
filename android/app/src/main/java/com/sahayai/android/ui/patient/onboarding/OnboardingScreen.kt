package com.sahayai.android.ui.patient.onboarding

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Accessibility
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Spa
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.sahayai.android.domain.model.UserRole
import com.sahayai.android.ui.theme.AlertCritical
import com.sahayai.android.ui.theme.SahayBlue100
import com.sahayai.android.ui.theme.SahayBlue50
import com.sahayai.android.ui.theme.SahayBlue500
import com.sahayai.android.ui.theme.SahayBlue700
import com.sahayai.android.ui.theme.SahayGray100
import com.sahayai.android.ui.theme.SahayGreen100
import com.sahayai.android.ui.theme.SahayGreen400
import com.sahayai.android.ui.theme.SahayWarmWhite

@Composable
fun OnboardingScreen(
    onPatientOnboarded: () -> Unit,
    onCaregiverOnboarded: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        containerColor = SahayGray100
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            // Background Gradient Accent
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(300.dp)
                    .background(
                        Brush.verticalGradient(
                            listOf(SahayBlue100.copy(alpha = 0.5f), Color.Transparent)
                        )
                    )
            )

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .imePadding()
                    .padding(horizontal = 24.dp, vertical = 40.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Hero Section
                HeroSection()

                Spacer(modifier = Modifier.height(48.dp))

                // Role selector label
                Text(
                    text = "Choose Your Role",
                    style = MaterialTheme.typography.titleLarge,
                    color = SahayBlue700,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.fillMaxWidth()
                )
                Text(
                    text = "This helps us tailor your experience.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.fillMaxWidth()
                )
                
                Spacer(modifier = Modifier.height(20.dp))

                // Role cards
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    RoleCard(
                        icon = Icons.Filled.Person,
                        title = "Patient",
                        description = "I need assistance",
                        isSelected = uiState.selectedRole == UserRole.PATIENT,
                        onClick = { viewModel.onRoleSelected(UserRole.PATIENT) },
                        selectedColor = SahayBlue500,
                        modifier = Modifier
                            .weight(1f)
                            .height(180.dp)
                            .semantics { contentDescription = "Select Patient role" }
                    )
                    RoleCard(
                        icon = Icons.Filled.Favorite,
                        title = "Caregiver",
                        description = "I am providing care",
                        isSelected = uiState.selectedRole == UserRole.CAREGIVER,
                        onClick = { viewModel.onRoleSelected(UserRole.CAREGIVER) },
                        selectedColor = SahayGreen400,
                        modifier = Modifier
                            .weight(1f)
                            .height(180.dp)
                            .semantics { contentDescription = "Select Caregiver role" }
                    )
                }

                Spacer(modifier = Modifier.height(32.dp))

                // Form Section
                FormSection(uiState = uiState, viewModel = viewModel)

                Spacer(modifier = Modifier.height(40.dp))

                // Get Started button
                Button(
                    onClick = {
                        viewModel.onConfirm(
                            onPatientDone = onPatientOnboarded,
                            onCaregiverDone = onCaregiverOnboarded
                        )
                    },
                    enabled = !uiState.isLoading,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp)
                        .semantics { contentDescription = "Get Started button" },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = SahayBlue500,
                        contentColor = Color.White,
                        disabledContainerColor = SahayBlue500.copy(alpha = 0.5f)
                    ),
                    shape = MaterialTheme.shapes.large,
                    elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = "Get Started",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun HeroSection() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .size(100.dp)
                .background(SahayBlue50, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Filled.Spa,
                contentDescription = null,
                tint = SahayBlue500,
                modifier = Modifier.size(56.dp)
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "SahayAI",
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Black,
            color = SahayBlue500,
            textAlign = TextAlign.Center,
            letterSpacing = (-1).sp
        )
        Text(
            text = "Your Compassionate AI Companion",
            style = MaterialTheme.typography.titleMedium,
            color = SahayBlue700,
            textAlign = TextAlign.Center,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun FormSection(uiState: OnboardingUiState, viewModel: OnboardingViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        // Name field (optional)
        OutlinedTextField(
            value = uiState.userName,
            onValueChange = { viewModel.onUserNameChanged(it) },
            label = { Text(text = "Display Name") },
            placeholder = {
                Text(
                    text = if (uiState.selectedRole == UserRole.PATIENT) "e.g. Ramesh" else "e.g. Priya"
                )
            },
            singleLine = true,
            shape = MaterialTheme.shapes.medium,
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = SahayBlue500,
                focusedLabelColor = SahayBlue500,
                unfocusedContainerColor = SahayWarmWhite,
                focusedContainerColor = SahayWarmWhite
            )
        )

        // User ID field (required)
        OutlinedTextField(
            value = uiState.userId,
            onValueChange = { viewModel.onUserIdChanged(it) },
            label = { Text(text = "Your User ID *") },
            placeholder = {
                Text(
                    text = if (uiState.selectedRole == UserRole.PATIENT)
                        "ramesh_demo_001"
                    else
                        "caregiver_priya_001"
                )
            },
            singleLine = true,
            isError = uiState.error != null && uiState.userId.isBlank(),
            shape = MaterialTheme.shapes.medium,
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = SahayBlue500,
                focusedLabelColor = SahayBlue500,
                unfocusedContainerColor = SahayWarmWhite,
                focusedContainerColor = SahayWarmWhite
            )
        )

        // Patient ID field — only for Caregiver
        if (uiState.selectedRole == UserRole.CAREGIVER) {
            OutlinedTextField(
                value = uiState.patientId,
                onValueChange = { viewModel.onPatientIdChanged(it) },
                label = { Text(text = "Patient ID to Monitor *") },
                placeholder = { Text(text = "ramesh_demo_001") },
                singleLine = true,
                isError = uiState.error != null && uiState.patientId.isBlank(),
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = SahayBlue500,
                    focusedLabelColor = SahayBlue500,
                    unfocusedContainerColor = SahayWarmWhite,
                    focusedContainerColor = SahayWarmWhite
                )
            )
        }

        // Error message
        if (uiState.error != null) {
            Text(
                text = uiState.error ?: "",
                color = AlertCritical,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(horizontal = 4.dp)
            )
        }
    }
}

@Composable
private fun RoleCard(
    icon: ImageVector,
    title: String,
    description: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    selectedColor: Color,
    modifier: Modifier = Modifier
) {
    val borderColor by animateColorAsState(
        if (isSelected) selectedColor else MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
        label = "border_color"
    )
    val containerColor by animateColorAsState(
        if (isSelected) selectedColor.copy(alpha = 0.08f) else SahayWarmWhite,
        label = "container_color"
    )
    val elevation by animateDpAsState(
        if (isSelected) 4.dp else 1.dp,
        label = "elevation"
    )

    Card(
        onClick = onClick,
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = containerColor),
        border = BorderStroke(
            width = if (isSelected) 2.dp else 1.dp,
            color = borderColor
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = elevation),
        shape = MaterialTheme.shapes.large
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(56.dp)
                    .background(
                        if (isSelected) selectedColor.copy(alpha = 0.1f) else SahayGray100,
                        CircleShape
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = if (isSelected) selectedColor else SahayBlue700.copy(alpha = 0.6f),
                    modifier = Modifier.size(32.dp)
                )
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = if (isSelected) SahayBlue700 else MaterialTheme.colorScheme.onSurface,
                textAlign = TextAlign.Center
            )
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                lineHeight = 16.sp
            )
        }
    }
}
