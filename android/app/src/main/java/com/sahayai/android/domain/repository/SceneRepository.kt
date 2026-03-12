package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.SceneResponse

interface SceneRepository {
    suspend fun analyzeScene(userId: String, imageBytes: ByteArray): NetworkResult<SceneResponse>
}
