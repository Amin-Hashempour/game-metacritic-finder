package com.aminhashempour.metacriticfinder

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.rememberAsyncImagePainter
import coil.request.ImageRequest

private val WarmAmber = Color(0xFFE1A84B)
private val WarmAmberDark = Color(0xFF5A421C)
private val Canvas = Color(0xFF242526)
private val Surface = Color(0xFF303133)
private val SurfaceRaised = Color(0xFF393A3C)
private val TextPrimary = Color(0xFFF1EEE8)
private val TextSecondary = Color(0xFFBEBAB2)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MetacriticTheme { FinderScreen() } }
    }
}

@Composable
fun MetacriticTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = WarmAmber,
            onPrimary = Color(0xFF302309),
            primaryContainer = WarmAmberDark,
            onPrimaryContainer = Color(0xFFFFDEA1),
            background = Canvas,
            onBackground = TextPrimary,
            surface = Surface,
            onSurface = TextPrimary,
            surfaceVariant = SurfaceRaised,
            onSurfaceVariant = TextSecondary,
            outline = Color(0xFF77736C),
            errorContainer = Color(0xFF52362E),
            onErrorContainer = Color(0xFFFFDAD0),
        ),
        content = content,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FinderScreen(vm: MainViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    val canGoBack = state is ScreenState.Suggestions || state is ScreenState.Details || state is ScreenState.Error
    BackHandler(enabled = canGoBack, onBack = vm::goHome)
    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("METACRITIC FINDER", fontWeight = FontWeight.Black, letterSpacing = 1.sp) },
                navigationIcon = {
                    if (canGoBack) {
                        IconButton(onClick = vm::goHome) {
                            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back to home")
                        }
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Surface),
            )
        },
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
    Text("Find the score.", fontSize = 36.sp, fontWeight = FontWeight.Black, color = TextPrimary)
    Text("Type a full or partial game title. Misspellings are okay.", color = TextSecondary)
}

@Composable
private fun SearchForm(query: String, update: (String) -> Unit, search: () -> Unit, loading: Boolean) {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = SurfaceRaised)) {
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
    val context = LocalContext.current
    val coverRequest = game.image_url?.let {
        ImageRequest.Builder(context)
            .data(it)
            .setHeader("Referer", "https://www.metacritic.com/")
            .setHeader("User-Agent", "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36")
            .crossfade(true)
            .build()
    }
    Card(Modifier.fillMaxWidth().clickable(onClick = select), shape = RoundedCornerShape(18.dp)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(width = 58.dp, height = 82.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(Color(0xFF47484A)),
                contentAlignment = Alignment.Center,
            ) {
                if (coverRequest != null) {
                    Image(
                        painter = rememberAsyncImagePainter(coverRequest),
                        contentDescription = "${game.title} cover",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop,
                    )
                }
            }
            Column(Modifier.padding(horizontal = 14.dp).weight(1f)) {
                Text(game.title, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                game.year?.let { Text(it.toString(), color = TextSecondary) }
            }
            Text("${(game.confidence * 100).toInt()}%", color = WarmAmber, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun GameHeader(game: GameDetails) = Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
    Text(game.title, fontSize = 32.sp, fontWeight = FontWeight.Black, color = TextPrimary)
    Text(listOfNotNull(game.year?.toString(), "Critic metascores").joinToString(" · "), color = TextSecondary)
}

@Composable
private fun PlatformCard(score: PlatformScore) {
    val scoreColor = when (score.metascore ?: 0) { in 75..100 -> Color(0xFF2F9E44); in 50..74 -> Color(0xFFF0A000); else -> Color(0xFFD64545) }
    Card(shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(score.platform, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text(score.review_count?.let { "Based on $it critic reviews" } ?: "Metacritic critic score", color = TextSecondary, fontSize = 13.sp)
            }
            Box(Modifier.size(58.dp).background(scoreColor, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
                Text(score.metascore?.toString() ?: "TBD", color = Color.White, fontWeight = FontWeight.Black, fontSize = if (score.metascore == null) 16.sp else 24.sp)
            }
        }
    }
}

@Composable
private fun MessageCard(message: String) = Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF4A3A24))) {
    Text(message, Modifier.padding(18.dp), color = Color(0xFFFFDCA0))
}
