# Metacritic Finder

Android app and local API for finding a game—even from a partial or misspelled query—and showing its Metacritic critic score on every available platform.

## Run the API

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs are available at `http://localhost:8000/docs`. The Android emulator reaches the API at `http://10.0.2.2:8000`.

## Run Android

Open the repository in Android Studio, let Gradle sync, start the API, then run the `app` configuration on an emulator (Android 8.0/API 26 or newer).

To build for a deployed API, include its HTTPS base URL (with a trailing slash):

```bash
./gradlew assembleDebug -PapiBaseUrl=https://your-api.example.com/
```

## Deploy on Render

The included `render.yaml` deploys the backend as a Docker web service. Create a Render Blueprint from this repository, wait for `/health` to return `{"status":"ok"}`, then rebuild the APK with the assigned HTTPS URL as `apiBaseUrl`.

Metacritic does not provide a public API. The server isolates page extraction behind a provider, caches results, rate-limits outbound requests, and returns a clear `SOURCE_UNAVAILABLE` response if Metacritic blocks access or changes its markup.

## Tests

```bash
cd backend
.venv/bin/pytest
```
