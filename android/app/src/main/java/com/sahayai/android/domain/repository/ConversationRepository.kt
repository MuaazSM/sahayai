package com.sahayai.android.domain.repository

import com.sahayai.android.core.network.NetworkResult
import com.sahayai.android.domain.model.ConversationResponse

interface ConversationRepository {
    suspend fun sendMessage(userId: String, message: String, conversationId: String? = null): NetworkResult<ConversationResponse>
}
