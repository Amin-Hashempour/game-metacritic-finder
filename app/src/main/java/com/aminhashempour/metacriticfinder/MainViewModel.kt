package com.aminhashempour.metacriticfinder

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

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
                    onFailure = { ScreenState.Error("The score service is unavailable. Try again shortly.") },
                )
        }
    }

    fun select(game: SearchResult) = viewModelScope.launch {
        _state.value = ScreenState.Loading
        _state.value = runCatching { api.details(game.id) }
            .fold(
                onSuccess = { ScreenState.Details(it) },
                onFailure = { ScreenState.Error("Could not load this game's scores.") },
            )
    }
}
