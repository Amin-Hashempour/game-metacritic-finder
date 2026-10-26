package com.aminhashempour.metacriticfinder

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.rememberAsyncImagePainter

private val Ink = Color(0xFF13191F)
private val Green = Color(0xFF2DAA6B)
private val Canvas = Color(0xFFF4F6F4)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MetacriticTheme { FinderScreen() } }
    }
}

@Composable
fun MetacriticTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = lightColorScheme(primary = Green, background = Canvas, surface = Color.White), content = content)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinderScreen(vm: MainViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    Scaffold(
        topBar = { CenterAlignedTopAppBar(title = { Text("METACRITIC FINDER", fontWeight = FontWeight.Black, letterSpacing = 1.sp) }) },
        containerColor = Canvas,
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            when (val current = state) {
                ScreenState.Search -> item { Welcome() }
                ScreenState.Loading -> item { Box(Modifier.fillParentMaxHeight(.55f).fillMaxWidth(), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
                is ScreenState.Suggestions -> {
                    item { Text("Choose the game you meant", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
                    items(current.games, key = { it.id }) { game -> SuggestionCard(game) { vm.select(game) } }
                }
                is ScreenState.Details -> {
                    item { GameHeader(current.game) }
                    if (current.game.platforms.isEmpty()) item { MessageCard("No critic score has been published for this game yet.") }
                    items(current.game.platforms) { PlatformCard(it) }
                }
                is ScreenState.Error -> item { MessageCard(current.message) }
            }
            item { SearchForm(query, vm::updateQuery, vm::search, state is ScreenState.Loading) }
        }
    }
}

@Composable
private fun Welcome() = Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Text("Find the score.", fontSize = 36.sp, fontWeight = FontWeight.Black, color = Ink)
    Text("Type a full or partial game title. Misspellings are okay.", color = Color.DarkGray)
}

@Composable
private fun SearchForm(query: String, update: (String) -> Unit, search: () -> Unit, loading: Boolean) {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Name the game", fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = query,
                onValueChange = update,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("e.g. Eldn Ring") },
                leadingIcon = { Icon(Icons.Rounded.Search, contentDescription = null) },
            )
            Button(onClick = search, enabled = !loading, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("Find metascore") }
        }
    }
}

@Composable
private fun SuggestionCard(game: SearchResult, select: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = select), shape = RoundedCornerShape(18.dp)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            if (game.image_url != null) Image(rememberAsyncImagePainter(game.image_url), null, Modifier.size(72.dp), contentScale = ContentScale.Crop)
            Column(Modifier.padding(horizontal = 14.dp).weight(1f)) {
                Text(game.title, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                game.year?.let { Text(it.toString(), color = Color.Gray) }
            }
            Text("${(game.confidence * 100).toInt()}%", color = Green, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun GameHeader(game: GameDetails) = Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
    Text(game.title, fontSize = 32.sp, fontWeight = FontWeight.Black, color = Ink)
    Text(listOfNotNull(game.year?.toString(), "Critic metascores").joinToString(" · "), color = Color.Gray)
}

@Composable
private fun PlatformCard(score: PlatformScore) {
    val scoreColor = when (score.metascore ?: 0) { in 75..100 -> Color(0xFF2F9E44); in 50..74 -> Color(0xFFF0A000); else -> Color(0xFFD64545) }
    Card(shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(score.platform, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text(score.review_count?.let { "Based on $it critic reviews" } ?: "Metacritic critic score", color = Color.Gray, fontSize = 13.sp)
            }
            Box(Modifier.size(58.dp).background(scoreColor, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
                Text(score.metascore?.toString() ?: "TBD", color = Color.White, fontWeight = FontWeight.Black, fontSize = if (score.metascore == null) 16.sp else 24.sp)
            }
        }
    }
}

@Composable
private fun MessageCard(message: String) = Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF2E0))) {
    Text(message, Modifier.padding(18.dp), color = Color(0xFF684719))
}
