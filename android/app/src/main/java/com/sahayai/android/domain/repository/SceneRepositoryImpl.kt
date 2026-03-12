package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.core.network.safeApiCall
import com.sahayai.android.domain.model.SceneResponse
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject

class SceneRepositoryImpl @Inject constructor(
    private val api: SahayAIApiService
) : SceneRepository {

    override suspend fun analyzeScene(userId: String, imageBytes: ByteArray): NetworkResult<SceneResponse> {
        return safeApiCall {
            val userIdBody = userId.toRequestBody("text/plain".toMediaTypeOrNull())
            val imagePart = MultipartBody.Part.createFormData(
                "image",
                "scene.jpg",
                imageBytes.toRequestBody("image/jpeg".toMediaTypeOrNull())
            )
            api.analyzeScene(userIdBody, imagePart)
        }
    }
}
