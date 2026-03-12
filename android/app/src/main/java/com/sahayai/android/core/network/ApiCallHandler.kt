package com.sahayai.android.core.network

import retrofit2.Response

suspend fun <T> safeApiCall(call: suspend () -> Response<T>): NetworkResult<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            val body = response.body()
            if (body != null) {
                NetworkResult.Success(body)
            } else {
                NetworkResult.Error("Empty response body", response.code())
            }
        } else {
            NetworkResult.Error(
                response.errorBody()?.string() ?: "Unknown server error",
                response.code()
            )
        }
    } catch (e: Exception) {
        NetworkResult.Error(e.message ?: "Network request failed")
    }
}
