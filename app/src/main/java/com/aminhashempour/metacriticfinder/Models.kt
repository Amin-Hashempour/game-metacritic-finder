package com.aminhashempour.metacriticfinder

data class SearchResult(
    val id: String,
    val title: String,
    val year: Int?,
    val image_url: String?,
    val metacritic_url: String,
    val confidence: Double,
)

data class PlatformScore(
    val platform: String,
    val metascore: Int?,
    val review_count: Int?,
    val release_date: String?,
    val metacritic_url: String,
)

data class GameDetails(
    val id: String,
    val title: String,
    val year: Int?,
    val image_url: String?,
    val platforms: List<PlatformScore>,
)
