package com.aminhashempour.metacriticfinder

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

interface GamesApi {
    @GET("v1/games/search")
    suspend fun search(@Query("q") query: String): List<SearchResult>

    @GET("v1/games/{id}")
    suspend fun details(@Path(value = "id", encoded = true) id: String): GameDetails
}

object ApiClient {
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .callTimeout(100, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    val games: GamesApi = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(httpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(GamesApi::class.java)
}
