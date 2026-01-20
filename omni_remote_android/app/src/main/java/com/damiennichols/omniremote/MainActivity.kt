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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
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

enum class AppScreen {
    Login,
    Setup,
    Home,
    Terminal,
    Projects
}

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

    val expectedEmail = "me@damiennichols.com"
    val auth = remember { FirebaseAuth.getInstance() }
    var authed by remember { mutableStateOf(auth.currentUser?.email?.equals(expectedEmail, true) == true) }
    var authEmail by rememberSaveable { mutableStateOf(expectedEmail) }
    var authPassword by rememberSaveable { mutableStateOf("") }
    var authBusy by remember { mutableStateOf(false) }
    var authError by remember { mutableStateOf<String?>(null) }
    var showPassword by rememberSaveable { mutableStateOf(false) }

    var host by rememberSaveable { mutableStateOf("") }
    var port by rememberSaveable { mutableStateOf("8765") }
    var token by rememberSaveable { mutableStateOf("") }
    var cwd by rememberSaveable { mutableStateOf("") }
    var command by rememberSaveable { mutableStateOf("") }
    var status by remember { mutableStateOf("disconnected") }
    var connected by remember { mutableStateOf(false) }
    var activeSessionId by remember { mutableStateOf<String?>(null) }
    var secure by rememberSaveable { mutableStateOf(false) }
    var showToken by rememberSaveable { mutableStateOf(false) }
    var screen by rememberSaveable { mutableStateOf(if (authed) AppScreen.Setup else AppScreen.Login) }
    var projectsLoaded by remember { mutableStateOf(false) }

    val terminalLines = remember { mutableStateListOf<String>() }
    val projects = remember { mutableStateListOf<Project>() }

    val client = remember {
        OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()
    }

    var socket by remember { mutableStateOf<WebSocket?>(null) }

    DisposableEffect(Unit) {
        val listener = FirebaseAuth.AuthStateListener { fbAuth ->
            val email = fbAuth.currentUser?.email
            authed = email != null && email.equals(expectedEmail, true)
        }
        auth.addAuthStateListener(listener)
        onDispose {
            auth.removeAuthStateListener(listener)
        }
    }

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

    fun disconnectWebSocket() {
        socket?.close(1000, "client disconnect")
        socket = null
        connected = false
        activeSessionId = null
        status = "disconnected"
        projectsLoaded = false
    }

    fun signIn() {
        val email = authEmail.trim()
        if (email.isBlank() || authPassword.isBlank()) {
            authError = "Email and password required"
            return
        }
        if (!email.equals(expectedEmail, true)) {
            authError = "Use $expectedEmail"
            return
        }
        authBusy = true
        authError = null
        auth.signInWithEmailAndPassword(email, authPassword)
            .addOnSuccessListener {
                authBusy = false
                authPassword = ""
                val signedInEmail = auth.currentUser?.email
                if (signedInEmail == null || !signedInEmail.equals(expectedEmail, true)) {
                    auth.signOut()
                    authError = "Signed in as $signedInEmail. Use $expectedEmail."
                } else {
                    status = "signed in"
                }
            }
            .addOnFailureListener { e ->
                authBusy = false
                authError = e.message ?: "Sign-in failed"
            }
    }

    fun signOut() {
        disconnectWebSocket()
        auth.signOut()
        authPassword = ""
        authError = null
        status = "signed out"
    }

    fun connectWebSocket() {
        val cleanHost = normalizedHost()
        val cleanToken = token.trim()
        if (cleanHost.isBlank() || cleanToken.isBlank()) {
            status = "missing host/token"
            return
        }
        disconnectWebSocket()
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
                    activeSessionId = null
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                mainHandler.post {
                    status = "error: ${t.message}"
                    connected = false
                    activeSessionId = null
                    appendLine("[error] ${t.message}")
                }
            }
        }

        socket = client.newWebSocket(request, listener)
        status = "connecting"
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

    fun refreshProjectsAsync() {
        scope.launch {
            try {
                status = "loading projects"
                fetchProjects()
                projectsLoaded = true
                status = "projects loaded"
            } catch (e: Exception) {
                status = "error: ${e.message}"
            }
        }
    }

    fun fetchCloudConfig() {
        if (!authed) {
            status = "sign in required"
            return
        }
        status = "loading cloud config"
        FirebaseFirestore.getInstance()
            .collection("omniremote")
            .document("connection")
            .get()
            .addOnSuccessListener { doc ->
                val url = doc.getString("url")
                if (!url.isNullOrBlank()) {
                    val uri = Uri.parse(url.trim())
                    val hostFromUrl = uri.host.orEmpty()
                    if (hostFromUrl.isNotBlank()) {
                        host = hostFromUrl
                    }
                    if (uri.port != -1) {
                        port = uri.port.toString()
                    } else if (uri.scheme.equals("https", ignoreCase = true)) {
                        port = ""
                    }
                    secure = uri.scheme.equals("https", ignoreCase = true) ||
                        uri.scheme.equals("wss", ignoreCase = true)
                }

                val hostOverride = doc.getString("host")
                val portOverride = doc.get("port")
                val secureOverride = doc.getBoolean("secure")
                val tokenOverride = doc.getString("token")
                if (!hostOverride.isNullOrBlank()) {
                    host = hostOverride
                }
                if (!tokenOverride.isNullOrBlank()) {
                    token = tokenOverride
                }
                when (portOverride) {
                    is Number -> port = portOverride.toInt().toString()
                    is String -> if (portOverride.isNotBlank()) {
                        port = portOverride
                    }
                }
                if (secureOverride != null) {
                    secure = secureOverride
                }
                status = "cloud config loaded"
            }
            .addOnFailureListener { e ->
                status = "cloud config error: ${e.message}"
            }
    }

    LaunchedEffect(connected, projectsLoaded) {
        if (connected && projectsLoaded && screen == AppScreen.Setup) {
            screen = AppScreen.Home
        }
    }

    LaunchedEffect(authed) {
        if (!authed) {
            screen = AppScreen.Login
        } else if (screen == AppScreen.Login) {
            screen = AppScreen.Setup
        }
    }

    val gradient = Brush.linearGradient(listOf(BgTop, BgBottom))

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(gradient)
            .padding(16.dp)
    ) {
        when (screen) {
            AppScreen.Login -> LoginScreen(
                email = authEmail,
                password = authPassword,
                showPassword = showPassword,
                busy = authBusy,
                error = authError,
                expectedEmail = expectedEmail,
                onEmailChange = { authEmail = it },
                onPasswordChange = { authPassword = it },
                onShowPasswordChange = { showPassword = it },
                onSignIn = { signIn() }
            )
            AppScreen.Setup -> SetupScreen(
                host = host,
                port = port,
                token = token,
                showToken = showToken,
                secure = secure,
                status = status,
                connected = connected,
                projectsLoaded = projectsLoaded,
                authed = authed,
                authEmail = authEmail,
                onHostChange = { host = it },
                onPortChange = { port = it },
                onTokenChange = { token = it },
                onShowTokenChange = { showToken = it },
                onSecureChange = { secure = it },
                onConnect = { connectWebSocket() },
                onDisconnect = { disconnectWebSocket() },
                onFetchCloudConfig = { fetchCloudConfig() },
                onRefreshProjects = { refreshProjectsAsync() },
                onContinue = { screen = AppScreen.Home },
                onSignOut = { signOut() }
            )
            AppScreen.Home -> HomeScreen(
                status = status,
                connected = connected,
                onOpenTerminal = { screen = AppScreen.Terminal },
                onOpenProjects = { screen = AppScreen.Projects },
                onOpenSettings = { screen = AppScreen.Setup },
                onOpenRemoteDesktop = {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://remotedesktop.google.com/access"))
                    context.startActivity(intent)
                },
                onRefreshProjects = { refreshProjectsAsync() },
                onDisconnect = { disconnectWebSocket() }
            )
            AppScreen.Terminal -> TerminalScreen(
                cwd = cwd,
                command = command,
                status = status,
                terminalLines = terminalLines,
                connected = connected,
                canSendInput = activeSessionId != null,
                onBack = { screen = AppScreen.Home },
                onCwdChange = { cwd = it },
                onCommandChange = { command = it },
                onRun = {
                    sendRun(command)
                    command = ""
                },
                onSendInput = {
                    sendStdin(command + "\n")
                    command = ""
                },
                onClear = { terminalLines.clear() }
            )
            AppScreen.Projects -> ProjectsScreen(
                status = status,
                projects = projects,
                onBack = { screen = AppScreen.Home },
                onRefresh = { refreshProjectsAsync() },
                onActivate = { project ->
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
                onDeactivate = { project ->
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
                },
                onOpenStudio = { project ->
                    scope.launch {
                        try {
                            status = "opening studio"
                            postProjectAction(project.name, "open-studio")
                            status = "studio opened"
                        } catch (e: Exception) {
                            status = "error: ${e.message}"
                        }
                    }
                }
            )
        }
    }
}

@Composable
private fun LoginScreen(
    email: String,
    password: String,
    showPassword: Boolean,
    busy: Boolean,
    error: String?,
    expectedEmail: String,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onShowPasswordChange: (Boolean) -> Unit,
    onSignIn: () -> Unit
) {
    val ready = email.trim().isNotBlank() && password.isNotBlank()

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            text = "Omni Remote",
            color = TextPrimary,
            fontWeight = FontWeight.Bold,
            fontSize = 26.sp
        )
        Text(
            text = "Firebase sign-in required",
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
                Text("Sign In", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = email,
                    onValueChange = onEmailChange,
                    label = { Text("Email") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = darkFieldColors()
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = onPasswordChange,
                    label = { Text("Password") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = if (showPassword) {
                        VisualTransformation.None
                    } else {
                        PasswordVisualTransformation()
                    },
                    colors = darkFieldColors()
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Switch(checked = showPassword, onCheckedChange = onShowPasswordChange)
                    Text(
                        text = "Show password",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = onSignIn,
                    colors = ButtonDefaults.buttonColors(containerColor = Accent),
                    enabled = ready && !busy
                ) {
                    Text(if (busy) "Signing in..." else "Sign In")
                }
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Authorized email: $expectedEmail",
                    color = TextMuted,
                    fontSize = 12.sp
                )
                if (!error.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(text = error, color = Warning, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun SetupScreen(
    host: String,
    port: String,
    token: String,
    showToken: Boolean,
    secure: Boolean,
    status: String,
    connected: Boolean,
    projectsLoaded: Boolean,
    authed: Boolean,
    authEmail: String,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onTokenChange: (String) -> Unit,
    onShowTokenChange: (Boolean) -> Unit,
    onSecureChange: (Boolean) -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onFetchCloudConfig: () -> Unit,
    onRefreshProjects: () -> Unit,
    onContinue: () -> Unit,
    onSignOut: () -> Unit
) {
    val ready = host.trim().isNotBlank() && token.trim().isNotBlank()

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
        Spacer(modifier = Modifier.height(6.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = if (authed) "signed in: $authEmail" else "not signed in",
                color = if (authed) Accent else Warning,
                fontSize = 12.sp
            )
            Button(
                onClick = onSignOut,
                colors = ButtonDefaults.buttonColors(containerColor = Warning),
                enabled = authed
            ) {
                Text("Sign out")
            }
        }
        Spacer(modifier = Modifier.height(12.dp))

        Card(
            colors = CardDefaults.cardColors(containerColor = Panel),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("Connection Setup", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = host,
                        onValueChange = onHostChange,
                        label = { Text("Host") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        colors = darkFieldColors()
                    )
                    OutlinedTextField(
                        value = port,
                        onValueChange = onPortChange,
                        label = { Text("Port") },
                        modifier = Modifier.width(120.dp),
                        singleLine = true,
                        colors = darkFieldColors()
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = token,
                    onValueChange = onTokenChange,
                    label = { Text("Token") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = if (showToken) {
                        VisualTransformation.None
                    } else {
                        PasswordVisualTransformation()
                    },
                    colors = darkFieldColors()
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Switch(checked = showToken, onCheckedChange = onShowTokenChange)
                    Text(
                        text = "Show token",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Switch(checked = secure, onCheckedChange = onSecureChange)
                    Text(
                        text = "Secure (HTTPS/WSS for tunnel)",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onConnect,
                        colors = ButtonDefaults.buttonColors(containerColor = Accent),
                        enabled = ready && !connected
                    ) {
                        Text("Connect")
                    }
                    Button(
                        onClick = onDisconnect,
                        colors = ButtonDefaults.buttonColors(containerColor = Warning),
                        enabled = connected
                    ) {
                        Text("Disconnect")
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onFetchCloudConfig,
                        colors = ButtonDefaults.buttonColors(containerColor = AccentAlt),
                        enabled = authed
                    ) {
                        Text("Fetch Cloud")
                    }
                    Button(
                        onClick = onRefreshProjects,
                        colors = ButtonDefaults.buttonColors(containerColor = Accent),
                        enabled = ready
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
                Text("Next", color = TextPrimary, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Once connected and projects are loaded, jump into the home view.",
                    color = TextMuted,
                    fontSize = 12.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = onContinue,
                    colors = ButtonDefaults.buttonColors(containerColor = Accent),
                    enabled = connected && projectsLoaded
                ) {
                    Text("Go to Home")
                }
            }
        }
    }
}

@Composable
private fun HomeScreen(
    status: String,
    connected: Boolean,
    onOpenTerminal: () -> Unit,
    onOpenProjects: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenRemoteDesktop: () -> Unit,
    onRefreshProjects: () -> Unit,
    onDisconnect: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            text = "Omni Remote",
            color = TextPrimary,
            fontWeight = FontWeight.Bold,
            fontSize = 26.sp
        )
        Text(
            text = if (connected) "connected" else "disconnected",
            color = if (connected) Accent else Warning,
            fontSize = 12.sp
        )
        Text(
            text = "status: $status",
            color = TextMuted,
            fontSize = 12.sp
        )
        Spacer(modifier = Modifier.height(12.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ActionCard(
                title = "Terminal",
                subtitle = "Full screen CLI with live output.",
                buttonText = "Open",
                buttonColor = Accent,
                onClick = onOpenTerminal,
                modifier = Modifier.weight(1f)
            )
            ActionCard(
                title = "Projects",
                subtitle = "Activate, deactivate, and open Studio.",
                buttonText = "Open",
                buttonColor = AccentAlt,
                onClick = onOpenProjects,
                modifier = Modifier.weight(1f)
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ActionCard(
                title = "Remote Desktop",
                subtitle = "Chrome Remote Desktop full UI.",
                buttonText = "Launch",
                buttonColor = AccentAlt,
                onClick = onOpenRemoteDesktop,
                modifier = Modifier.weight(1f)
            )
            ActionCard(
                title = "Settings",
                subtitle = "Edit connection details.",
                buttonText = "Open",
                buttonColor = Warning,
                onClick = onOpenSettings,
                modifier = Modifier.weight(1f)
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onRefreshProjects,
                colors = ButtonDefaults.buttonColors(containerColor = Accent)
            ) {
                Text("Refresh Projects")
            }
            Button(
                onClick = onDisconnect,
                colors = ButtonDefaults.buttonColors(containerColor = Warning)
            ) {
                Text("Disconnect")
            }
        }
    }
}

@Composable
private fun TerminalScreen(
    cwd: String,
    command: String,
    status: String,
    terminalLines: List<String>,
    connected: Boolean,
    canSendInput: Boolean,
    onBack: () -> Unit,
    onCwdChange: (String) -> Unit,
    onCommandChange: (String) -> Unit,
    onRun: () -> Unit,
    onSendInput: () -> Unit,
    onClear: () -> Unit
) {
    val listState = rememberLazyListState()

    LaunchedEffect(terminalLines.size) {
        if (terminalLines.isNotEmpty()) {
            listState.animateScrollToItem(terminalLines.size - 1)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        ScreenHeader(title = "Terminal", status = status, onBack = onBack)
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            value = cwd,
            onValueChange = onCwdChange,
            label = { Text("Working directory (optional)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            colors = darkFieldColors()
        )
        Spacer(modifier = Modifier.height(8.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
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
            onValueChange = onCommandChange,
            label = { Text("Command") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            colors = darkFieldColors()
        )
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onRun,
                colors = ButtonDefaults.buttonColors(containerColor = Accent),
                enabled = connected
            ) {
                Text("Run")
            }
            Button(
                onClick = onSendInput,
                colors = ButtonDefaults.buttonColors(containerColor = AccentAlt),
                enabled = connected && canSendInput
            ) {
                Text("Send Input")
            }
            Button(
                onClick = onClear,
                colors = ButtonDefaults.buttonColors(containerColor = Warning)
            ) {
                Text("Clear")
            }
        }
    }
}

@Composable
private fun ProjectsScreen(
    status: String,
    projects: List<Project>,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
    onActivate: (Project) -> Unit,
    onDeactivate: (Project) -> Unit,
    onOpenStudio: (Project) -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        ScreenHeader(title = "Projects", status = status, onBack = onBack)
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onRefresh,
                colors = ButtonDefaults.buttonColors(containerColor = Accent)
            ) {
                Text("Refresh")
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        if (projects.isEmpty()) {
            Text("No projects loaded", color = TextMuted, fontSize = 12.sp)
        } else {
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(projects) { project ->
                    ProjectRow(
                        project = project,
                        onActivate = { onActivate(project) },
                        onDeactivate = { onDeactivate(project) },
                        onOpenStudio = { onOpenStudio(project) }
                    )
                    Divider(color = Color(0xFF1F2937))
                }
            }
        }
    }
}

@Composable
private fun ScreenHeader(title: String, status: String, onBack: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column {
            Text(
                text = title,
                color = TextPrimary,
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            )
            Text(
                text = "status: $status",
                color = TextMuted,
                fontSize = 12.sp
            )
        }
        Button(
            onClick = onBack,
            colors = ButtonDefaults.buttonColors(containerColor = AccentAlt)
        ) {
            Text("Back")
        }
    }
}

@Composable
private fun ActionCard(
    title: String,
    subtitle: String,
    buttonText: String,
    buttonColor: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Panel),
        shape = RoundedCornerShape(12.dp),
        modifier = modifier
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, color = TextPrimary, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(4.dp))
            Text(subtitle, color = TextMuted, fontSize = 12.sp)
            Spacer(modifier = Modifier.height(10.dp))
            Button(
                onClick = onClick,
                colors = ButtonDefaults.buttonColors(containerColor = buttonColor)
            ) {
                Text(buttonText)
            }
        }
    }
}

@Composable
private fun ProjectRow(
    project: Project,
    onActivate: () -> Unit,
    onDeactivate: () -> Unit,
    onOpenStudio: () -> Unit
) {
    val statusColor = if (project.status == "Local") Accent else Warning
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
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
        Column(horizontalAlignment = Alignment.End) {
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
            Spacer(modifier = Modifier.height(6.dp))
            Button(
                onClick = onOpenStudio,
                colors = ButtonDefaults.buttonColors(containerColor = AccentAlt),
                enabled = project.status == "Local"
            ) {
                Text("Open Studio")
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
