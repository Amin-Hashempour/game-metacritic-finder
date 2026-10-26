package com.aminhashempour.metacriticfinder

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.net.SocketTimeoutException
import java.io.IOException

sealed interface ScreenState {
    data object Search : ScreenState
    data object Loading : ScreenState
    data class Suggestions(val games: List<SearchResult>) : ScreenState
    data class Details(val game: GameDetails) : ScreenState
    data class Error(val message: String) : ScreenState
}

class MainViewModel(private val api: GamesApi = ApiClient.games) : ViewModel() {
    private val _state = MutableStateFlow<ScreenState>(ScreenState.Search)
    val state: StateFlow<ScreenState> = _state.asStateFlow()
    var query = MutableStateFlow("")
        private set

    fun updateQuery(value: String) { query.value = value }

    fun goHome() {
        query.value = ""
        _state.value = ScreenState.Search
    }

    fun search() {
        val value = query.value.trim()
        if (value.length < 2) {
            _state.value = ScreenState.Error("Enter at least two characters.")
            return
        }
        viewModelScope.launch {
            _state.value = ScreenState.Loading
            _state.value = runCatching { api.search(value) }
                .fold(
                    onSuccess = { if (it.isEmpty()) ScreenState.Error("No matching games found.") else ScreenState.Suggestions(it) },
                    onFailure = { ScreenState.Error(errorMessage(it)) },
                )
        }
    }

    fun select(game: SearchResult) = viewModelScope.launch {
        _state.value = ScreenState.Loading
        _state.value = runCatching { api.details(game.id) }
            .fold(
                onSuccess = { ScreenState.Details(it) },
                onFailure = { ScreenState.Error(errorMessage(it)) },
            )
    }

    private fun errorMessage(error: Throwable): String = when (error) {
        is SocketTimeoutException -> "The server is waking up. Please try once more in a few seconds."
        is HttpException -> when (error.code()) {
            503 -> "Metacritic is temporarily unavailable. Please try again shortly."
            else -> "The score service returned error ${error.code()}."
        }
        is IOException -> "Could not reach the score service. Check your connection and try again."
        else -> "Unexpected error: ${error.javaClass.simpleName}."
    }
}
