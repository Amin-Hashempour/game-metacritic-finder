package com.aminhashempour.metacriticfinder

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface GamesApi {
    @GET("v1/games/search")
    suspend fun search(@Query("q") query: String): List<SearchResult>

    @GET("v1/games/{id}")
    suspend fun details(@Path(value = "id", encoded = true) id: String): GameDetails
}

object ApiClient {
    val games: GamesApi = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(GamesApi::class.java)
}
