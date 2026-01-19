package com.damiennichols.omniremote

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            OmniRemoteApp()
        }
    }
}

data class Project(val name: String, val status: String)

private val BgTop = Color(0xFF0B0F14)
private val BgBottom = Color(0xFF141A22)
private val Panel = Color(0xFF101820)
private val Accent = Color(0xFF4ADE80)
private val AccentAlt = Color(0xFF38BDF8)
private val Warning = Color(0xFFF59E0B)
private val TextPrimary = Color(0xFFE2E8F0)
private val TextMuted = Color(0xFF94A3B8)
private val TerminalGreen = Color(0xFF7CFC7C)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OmniRemoteApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val mainHandler = remember { Handler(Looper.getMainLooper()) }

    var host by rememberSaveable { mutableStateOf("") }
    var port by rememberSaveable { mutableStateOf("8765") }
    var token by rememberSaveable { mutableStateOf("") }
    var cwd by rememberSaveable { mutableStateOf("") }
    var command by rememberSaveable { mutableStateOf("") }
    var status by remember { mutableStateOf("disconnected") }
    var connected by remember { mutableStateOf(false) }
    var activeSessionId by remember { mutableStateOf<String?>(null) }
    var secure by rememberSaveable { mutableStateOf(false) }

    val terminalLines = remember { mutableStateListOf<String>() }
    val projects = remember { mutableStateListOf<Project>() }

    val client = remember {
        OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()
    }

    var socket by remember { mutableStateOf<WebSocket?>(null) }

    fun appendLine(line: String) {
        terminalLines.add(line)
        if (terminalLines.size > 2000) {
            terminalLines.removeAt(0)
        }
    }

    fun normalizedHost(): String {
        var cleanHost = host.trim()
        cleanHost = cleanHost.removePrefix("http://")
        cleanHost = cleanHost.removePrefix("https://")
        cleanHost = cleanHost.removePrefix("ws://")
        cleanHost = cleanHost.removePrefix("wss://")
        cleanHost = cleanHost.trim().trimEnd('/')
        return cleanHost
    }

    fun buildBaseHost(): String {
        val cleanHost = normalizedHost()
        val cleanPort = port.trim()
        return if (cleanPort.isBlank()) cleanHost else "$cleanHost:$cleanPort"
    }

    fun connectWebSocket() {
        val cleanHost = normalizedHost()
        val cleanToken = token.trim()
        if (cleanHost.isBlank() || cleanToken.isBlank()) {
            status = "missing host/token"
            return
        }
        val baseHost = buildBaseHost()
        val scheme = if (secure) "wss" else "ws"
        val encodedToken = URLEncoder.encode(cleanToken, "UTF-8")
        val wsUrl = "$scheme://$baseHost/ws/terminal?token=$encodedToken"
        val request = Request.Builder().url(wsUrl).build()
        val listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                mainHandler.post {
                    status = "connected"
                    connected = true
                    appendLine("[system] connected")
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                mainHandler.post {
                    try {
                        val obj = JSONObject(text)
                        when (obj.optString("type")) {
                            "output" -> appendLine(obj.optString("data"))
                            "exit" -> {
                                val code = obj.optString("code")
                                appendLine("[exit] code=$code")
                            }
                            "started" -> {
                                activeSessionId = obj.optString("sessionId")
                                appendLine("[started] ${activeSessionId ?: ""}")
                            }
                            "error" -> appendLine("[error] ${obj.optString("message")}")
                            else -> appendLine("[event] $text")
                        }
                    } catch (e: Exception) {
                        appendLine("[parse-error] ${e.message}")
                    }
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
                mainHandler.post {
                    status = "closing"
                    connected = false
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                mainHandler.post {
                    status = "error: ${t.message}"
                    connected = false
                    appendLine("[error] ${t.message}")
                }
            }
        }

        socket = client.newWebSocket(request, listener)
        status = "connecting"
    }

    fun disconnectWebSocket() {
        socket?.close(1000, "client disconnect")
        socket = null
        connected = false
        status = "disconnected"
    }

    fun sendRun(cmd: String) {
        val ws = socket ?: return
        if (cmd.isBlank()) return
        val payload = JSONObject()
        payload.put("type", "run")
        payload.put("cmd", cmd)
        if (cwd.isNotBlank()) payload.put("cwd", cwd)
        ws.send(payload.toString())
    }

    fun sendStdin(text: String) {
        val ws = socket ?: return
        val sid = activeSessionId ?: return
        val payload = JSONObject()
        payload.put("type", "stdin")
        payload.put("sessionId", sid)
        payload.put("data", text)
        ws.send(payload.toString())
    }

    suspend fun fetchProjects() {
        val cleanHost = normalizedHost()
        val cleanToken = token.trim()
        if (cleanHost.isBlank() || cleanToken.isBlank()) {
            throw RuntimeException("Host and token required")
        }
        val baseHost = buildBaseHost()
        val scheme = if (secure) "https" else "http"
        val url = "$scheme://$baseHost/api/projects"
        val request = Request.Builder()
            .url(url)
            .addHeader("X-Omni-Token", cleanToken)
            .build()

        val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
        val body = response.body?.string() ?: ""
        if (!response.isSuccessful) {
            throw RuntimeException("${response.code}: $body")
        }
        val obj = JSONObject(body)
        val list = mutableListOf<Project>()
        val arr: JSONArray = obj.optJSONArray("projects") ?: JSONArray()
        for (i in 0 until arr.length()) {
            val item = arr.getJSONObject(i)
            list.add(Project(item.getString("name"), item.getString("status")))
        }
        projects.clear()
        projects.addAll(list)
    }

    suspend fun postProjectAction(name: String, action: String) {
        val cleanHost = normalizedHost()
        val cleanToken = token.trim()
        if (cleanHost.isBlank() || cleanToken.isBlank()) {
            throw RuntimeException("Host and token required")
        }
        val baseHost = buildBaseHost()
        val scheme = if (secure) "https" else "http"
        val url = "$scheme://$baseHost/api/projects/$name/$action"
        val request = Request.Builder()
            .url(url)
            .addHeader("X-Omni-Token", cleanToken)
            .post("".toRequestBody("application/json".toMediaType()))
            .build()
        val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
        if (!response.isSuccessful) {
            val body = response.body?.string() ?: ""
            throw RuntimeException("${response.code}: $body")
        }
    }

    val gradient = Brush.linearGradient(listOf(BgTop, BgBottom))
    val listState = rememberLazyListState()

    LaunchedEffect(terminalLines.size) {
        if (terminalLines.isNotEmpty()) {
            listState.animateScrollToItem(terminalLines.size - 1)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(gradient)
            .padding(16.dp)
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Text(
                text = "Omni Remote",
                color = TextPrimary,
                fontWeight = FontWeight.Bold,
                fontSize = 26.sp
            )
            Text(
                text = "status: $status",
                color = TextMuted,
                fontSize = 12.sp
            )
            Spacer(modifier = Modifier.height(12.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = Panel),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("Connection", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = host,
                            onValueChange = { host = it },
                            label = { Text("Host") },
                            modifier = Modifier.weight(1f),
                            singleLine = true,
                            colors = darkFieldColors()
                        )
                        OutlinedTextField(
                            value = port,
                            onValueChange = { port = it },
                            label = { Text("Port") },
                            modifier = Modifier.width(120.dp),
                            singleLine = true,
                            colors = darkFieldColors()
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = token,
                        onValueChange = { token = it },
                        label = { Text("Token") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        colors = darkFieldColors()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Switch(checked = secure, onCheckedChange = { secure = it })
                        Text(
                            text = "Secure (HTTPS/WSS) for Cloudflare or TLS",
                            color = TextMuted,
                            fontSize = 12.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { connectWebSocket() },
                            colors = ButtonDefaults.buttonColors(containerColor = Accent),
                            enabled = !connected
                        ) {
                            Text("Connect")
                        }
                        Button(
                            onClick = { disconnectWebSocket() },
                            colors = ButtonDefaults.buttonColors(containerColor = Warning),
                            enabled = connected
                        ) {
                            Text("Disconnect")
                        }
                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        status = "loading projects"
                                        fetchProjects()
                                        status = "projects loaded"
                                    } catch (e: Exception) {
                                        status = "error: ${e.message}"
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentAlt)
                        ) {
                            Text("Refresh Projects")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = Panel),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("Terminal", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = cwd,
                        onValueChange = { cwd = it },
                        label = { Text("Working directory (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        colors = darkFieldColors()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(220.dp)
                            .border(BorderStroke(1.dp, Color(0xFF1F2937)), RoundedCornerShape(10.dp))
                            .background(Color(0xFF0B0F14), RoundedCornerShape(10.dp))
                            .padding(8.dp)
                    ) {
                        LazyColumn(state = listState) {
                            items(terminalLines) { line ->
                                Text(
                                    text = line.trimEnd(),
                                    color = TerminalGreen,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 12.sp
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = command,
                        onValueChange = { command = it },
                        label = { Text("Command") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        colors = darkFieldColors()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                sendRun(command)
                                command = ""
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Accent)
                        ) {
                            Text("Run")
                        }
                        Button(
                            onClick = {
                                sendStdin(command + "\n")
                                command = ""
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentAlt),
                            enabled = activeSessionId != null
                        ) {
                            Text("Send Input")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = Panel),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("Projects", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                    Spacer(modifier = Modifier.height(6.dp))
                    if (projects.isEmpty()) {
                        Text("No projects loaded", color = TextMuted, fontSize = 12.sp)
                    } else {
                        LazyColumn(modifier = Modifier.height(180.dp)) {
                            items(projects) { project ->
                                ProjectRow(
                                    project = project,
                                    onActivate = {
                                        scope.launch {
                                            try {
                                                status = "activating ${project.name}"
                                                postProjectAction(project.name, "activate")
                                                fetchProjects()
                                                status = "activated"
                                            } catch (e: Exception) {
                                                status = "error: ${e.message}"
                                            }
                                        }
                                    },
                                    onDeactivate = {
                                        scope.launch {
                                            try {
                                                status = "deactivating ${project.name}"
                                                postProjectAction(project.name, "deactivate")
                                                fetchProjects()
                                                status = "deactivated"
                                            } catch (e: Exception) {
                                                status = "error: ${e.message}"
                                            }
                                        }
                                    }
                                )
                                Divider(color = Color(0xFF1F2937))
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = Panel),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("Remote Desktop", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        "Launch Chrome Remote Desktop for full GUI control.",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(
                        onClick = {
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://remotedesktop.google.com/access"))
                            context.startActivity(intent)
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = AccentAlt)
                    ) {
                        Text("Open Chrome Remote Desktop")
                    }
                }
            }
        }
    }
}

@Composable
fun ProjectRow(project: Project, onActivate: () -> Unit, onDeactivate: () -> Unit) {
    val statusColor = if (project.status == "Local") Accent else Warning
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = project.name,
                color = TextPrimary,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                text = project.status,
                color = statusColor,
                fontSize = 12.sp
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Button(
                onClick = onActivate,
                colors = ButtonDefaults.buttonColors(containerColor = Accent),
                enabled = project.status != "Local"
            ) {
                Text("Activate")
            }
            Button(
                onClick = onDeactivate,
                colors = ButtonDefaults.buttonColors(containerColor = Warning),
                enabled = project.status == "Local"
            ) {
                Text("Deactivate")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun darkFieldColors() = TextFieldDefaults.outlinedTextFieldColors(
    focusedTextColor = TextPrimary,
    unfocusedTextColor = TextPrimary,
    focusedBorderColor = AccentAlt,
    unfocusedBorderColor = Color(0xFF1F2937),
    cursorColor = Accent,
    focusedLabelColor = TextMuted,
    unfocusedLabelColor = TextMuted
)
