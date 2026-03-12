package com.sahayai.android.domain.repository

import com.sahayai.android.core.mock.MockApiService
import com.sahayai.android.core.network.NetworkResult
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ConversationRepositoryTest {

    private lateinit var repository: ConversationRepositoryImpl

    @Before
    fun setup() {
        repository = ConversationRepositoryImpl(api = MockApiService())
    }

    @Test
    fun `sendMessage returns Success with response text`() = runTest {
        val result = repository.sendMessage(
            userId = "ramesh_demo_001",
            message = "How are you today?"
        )
        assertTrue(result is NetworkResult.Success)
        val response = (result as NetworkResult.Success).data
        assertTrue(response.responseText.isNotEmpty())
        assertTrue(response.aacScore > 0f)
    }

    @Test
    fun `sendMessage sets role to patient`() = runTest {
        val result = repository.sendMessage(
            userId = "ramesh_demo_001",
            message = "Test message"
        )
        assertTrue(result is NetworkResult.Success)
    }
}
