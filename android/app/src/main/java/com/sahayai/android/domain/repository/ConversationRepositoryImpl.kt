package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.core.network.SahayAIApiService
import com.sahayai.android.core.network.safeApiCall
import com.sahayai.android.domain.model.ConversationRequest
import com.sahayai.android.domain.model.ConversationResponse
import javax.inject.Inject

class ConversationRepositoryImpl @Inject constructor(
    private val api: SahayAIApiService
) : ConversationRepository {

    override suspend fun sendMessage(userId: String, message: String): NetworkResult<ConversationResponse> {
        return safeApiCall {
            api.sendConversation(ConversationRequest(userId = userId, message = message))
        }
    }
}
