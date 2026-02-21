# BUILD ANDROID APP - QUICK STEPS

## PREREQ
- Download & install **Android Studio** from https://developer.android.com/studio
- Open Android Studio

---

## STEP 1: Create Project (1 min)
- **File** → **New** → **New Android Project**
- Template: **Empty Compose Activity**
- Name: `VoiceAction`
- Language: **Kotlin**
- Min SDK: **API 30**
- Click **Finish** → Wait for Gradle sync

---

## STEP 2: Add Dependencies (1 min)
Open `app/build.gradle.kts`

Find `dependencies { }` block, add:
```gradle
implementation("com.squareup.okhttp3:okhttp:4.11.0")
implementation("com.google.code.gson:gson:2.10.1")
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
```

Click **Sync Now** (top banner)

---

## STEP 3: Add Permission (30 sec)
Open `app/src/main/AndroidManifest.xml`

Add before `<application>`:
```xml
<uses-permission android:name="android.permission.INTERNET" />
```

---

## STEP 4: Create Client Class (1 min)
Right-click `com.example.voiceaction` → **New** → **Kotlin Class...**

Name: `HybridRouterClient`

Paste:
```kotlin
package com.example.voiceaction

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

data class ToolCall(val name: String, val arguments: Map<String, Any>)
data class RouteResponse(val status: String, val function_calls: List<ToolCall>, val confidence: Double, val source: String, val total_time_ms: Double)

class HybridRouterClient(val serverUrl: String) {
    private val client = OkHttpClient()
    private val gson = Gson()
    
    suspend fun route(query: String): RouteResponse? = withContext(Dispatchers.IO) {
        try {
            val requestBody = mapOf("messages" to listOf(mapOf("role" to "user", "content" to query)))
            val json = gson.toJson(requestBody)
            val request = Request.Builder().url("$serverUrl/route").post(json.toRequestBody("application/json".toMediaType())).build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) gson.fromJson(response.body?.string(), RouteResponse::class.java) else null
        } catch (e: Exception) { e.printStackTrace(); null }
    }
}
```

---

## STEP 5: Replace MainActivity (1 min)
Open `MainActivity.kt` → **Select all** → Delete → Paste:

```kotlin
package com.example.voiceaction

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { VoiceActionApp() }
    }
}

@Composable
fun VoiceActionApp() {
    val apiClient = HybridRouterClient("http://192.168.1.100:5000")
    var query by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<RouteResponse?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    
    Column(Modifier.fillMaxSize().padding(16.dp), Arrangement.Center, Alignment.CenterHorizontally) {
        Text("🤖 Hybrid Router", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        
        TextField(query, { query = it }, label = { Text("Enter command") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Spacer(Modifier.height(12.dp))
        
        Button(onClick = { if (query.isNotEmpty()) { loading = true; error = ""; scope.launch { try { result = apiClient.route(query); if (result == null) error = "Failed" } catch (e: Exception) { error = e.message ?: "Error" } finally { loading = false } } } }, enabled = !loading, modifier = Modifier.fillMaxWidth()) {
            Text(if (loading) "Routing..." else "Route")
        }
        
        Spacer(Modifier.height(16.dp))
        if (error.isNotEmpty()) Text("❌ $error", color = MaterialTheme.colorScheme.error)
        if (result != null) Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) { Text("✅ ${result!!.status}"); Text("📊 Conf: ${String.format("%.0f", result!!.confidence * 100)}%"); Text("🔧 ${result!!.source}"); Text("⏱️ ${String.format("%.1f", result!!.total_time_ms)}ms"); if (result!!.function_calls.isNotEmpty()) { Spacer(Modifier.height(8.dp)); Text("Calls:"); result!!.function_calls.forEach { Text("  ${it.name}(${it.arguments})") } } } }
    }
}
```

---

## STEP 6: Update IP Address (30 sec)
In `MainActivity.kt`, line ~12:
```kotlin
val apiClient = HybridRouterClient("http://192.168.1.100:5000")
```

Replace `192.168.1.100` with your PC's IP from `ipconfig`

---

## STEP 7: Run (1 min)
- **Click Run** (green play button, top toolbar) OR `Shift+F10`
- Choose device/emulator
- Wait for app to launch

---

## STEP 8: Test
1. Type: `What is the weather in San Francisco`
2. Click **Route**
3. See result pop up

---

## ✅ DONE
Total time: **~7-10 minutes**

If connection fails: Check IP, check backend is running `python api_server.py --host 0.0.0.0 --port 5000`, check device is on same WiFi.
