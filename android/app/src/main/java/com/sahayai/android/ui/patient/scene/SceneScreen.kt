package com.sahayai.android.ui.patient.scene

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import kotlinx.coroutines.launch
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.sahayai.android.ui.components.LoadingOverlay
import com.sahayai.android.ui.components.SahayAITopBar
import com.sahayai.android.ui.theme.SahayBlue500
import com.sahayai.android.ui.theme.SahayBlue700

@Composable
fun SceneScreen(
    onBack: () -> Unit,
    viewModel: SceneViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val coroutineScope = rememberCoroutineScope()

    // ImageCapture use-case reference held across recompositions
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }

    val triggerCapture: () -> Unit = {
        val capture = imageCapture
        if (capture != null) {
            captureImage(
                imageCapture = capture,
                context = context,
                onImage = { bytes -> viewModel.onImageCaptured(bytes) },
                onError = { viewModel.clearError() }
            )
        } else {
            coroutineScope.launch {
                snackbarHostState.showSnackbar("Camera not ready yet.")
            }
        }
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted ->
            if (granted) {
                triggerCapture()
            } else {
                coroutineScope.launch {
                    snackbarHostState.showSnackbar("Camera permission is required to analyze scenes.")
                }
            }
        }
    )

    // Camera lifecycle management — tear down when the composable leaves composition
    DisposableEffect(Unit) {
        onDispose {
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener(
                { runCatching { future.get().unbindAll() } },
                ContextCompat.getMainExecutor(context)
            )
        }
    }

    LaunchedEffect(uiState.error) {
        val error = uiState.error
        if (!error.isNullOrBlank()) {
            snackbarHostState.showSnackbar(error)
            viewModel.clearError()
        }
    }

    Scaffold(
        topBar = {
            SahayAITopBar(
                title = "Scene Analyser",
                onBack = onBack
            )
        },
        snackbarHost = {
            SnackbarHost(hostState = snackbarHostState) { data ->
                Snackbar(
                    snackbarData = data,
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            Column(
                modifier = Modifier.fillMaxSize()
            ) {
                // CameraX live preview — takes up 55% of available height
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(0.55f)
                ) {
                    CameraPreview(
                        context = context,
                        lifecycleOwner = lifecycleOwner,
                        onImageCaptureReady = { capture -> imageCapture = capture },
                        modifier = Modifier.fillMaxSize()
                    )

                    // Capture FAB — pinned to bottom centre of the preview
                    CaptureButton(
                        enabled = !uiState.isAnalyzing,
                        onClick = {
                            val hasCamera = ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasCamera) {
                                triggerCapture()
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        },
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = 20.dp)
                    )
                }

                // Results panel — scrollable, takes remaining height
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(0.45f)
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    when {
                        uiState.hasResult -> {
                            SceneDescriptionCard(
                                description = uiState.description,
                                modifier = Modifier.fillMaxWidth()
                            )

                            if (uiState.objectsDetected.isNotEmpty()) {
                                ObjectChipRow(
                                    objects = uiState.objectsDetected,
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }

                            Button(
                                onClick = { viewModel.resetResult() },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = SahayBlue500
                                )
                            ) {
                                Text("Capture Again")
                            }
                        }

                        !uiState.isAnalyzing -> {
                            IdleHintCard(modifier = Modifier.fillMaxWidth())
                        }
                    }
                }
            }

            // Full-screen loading overlay while GPT-4o Vision is processing
            if (uiState.isAnalyzing) {
                LoadingOverlay()
            }
        }
    }
}

// -----------------------------------------------------------------------------
// Private sub-composables
// -----------------------------------------------------------------------------

@Composable
private fun CameraPreview(
    context: Context,
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    onImageCaptureReady: (ImageCapture) -> Unit,
    modifier: Modifier = Modifier
) {
    AndroidView(
        factory = { ctx ->
            val previewView = PreviewView(ctx).apply {
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            }

            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
            cameraProviderFuture.addListener(
                {
                    val cameraProvider = cameraProviderFuture.get()
                    val preview = Preview.Builder().build().also {
                        it.surfaceProvider = previewView.surfaceProvider
                    }
                    val capture = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                        .build()
                    onImageCaptureReady(capture)

                    runCatching {
                        cameraProvider.unbindAll()
                        cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            capture
                        )
                    }
                },
                ContextCompat.getMainExecutor(ctx)
            )
            previewView
        },
        modifier = modifier
    )
}

@Composable
private fun CaptureButton(
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    FloatingActionButton(
        onClick = { if (enabled) onClick() },
        modifier = modifier.size(72.dp),
        shape = CircleShape,
        containerColor = if (enabled) SahayBlue500 else SahayBlue500.copy(alpha = 0.5f)
    ) {
        Icon(
            imageVector = Icons.Filled.CameraAlt,
            contentDescription = "Capture scene",
            modifier = Modifier.size(36.dp),
            tint = Color.White
        )
    }
}

@Composable
private fun SceneDescriptionCard(
    description: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFD6EAF8)),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                text = "Scene Description",
                style = MaterialTheme.typography.titleSmall.copy(
                    color = SahayBlue700,
                    fontWeight = FontWeight.SemiBold
                )
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = description,
                style = MaterialTheme.typography.bodyLarge.copy(
                    fontSize = 20.sp,
                    lineHeight = 30.sp,
                    color = SahayBlue700
                )
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ObjectChipRow(
    objects: List<String>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "Objects Detected",
            style = MaterialTheme.typography.labelLarge.copy(
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        )
        Spacer(modifier = Modifier.height(4.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            objects.forEach { label ->
                AssistChip(
                    onClick = {},
                    label = { Text(text = label, style = MaterialTheme.typography.bodySmall) }
                )
            }
        }
    }
}

@Composable
private fun IdleHintCard(modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = Icons.Filled.ErrorOutline,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(40.dp)
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "Point the camera at a scene and tap the shutter button.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }
    }
}

// -----------------------------------------------------------------------------
// Utility — capture JPEG bytes from ImageCapture use-case
// -----------------------------------------------------------------------------

private fun captureImage(
    imageCapture: ImageCapture?,
    context: Context,
    onImage: (ByteArray) -> Unit,
    onError: () -> Unit
) {
    val capture = imageCapture ?: run { onError(); return }

    capture.takePicture(
        ContextCompat.getMainExecutor(context),
        object : ImageCapture.OnImageCapturedCallback() {
            override fun onCaptureSuccess(image: ImageProxy) {
                val bytes = imageProxyToByteArray(image)
                image.close()
                onImage(bytes)
            }

            override fun onError(exception: ImageCaptureException) {
                onError()
            }
        }
    )
}

private fun imageProxyToByteArray(image: ImageProxy): ByteArray {
    val buffer = image.planes[0].buffer
    return ByteArray(buffer.remaining()).also { buffer.get(it) }
}
