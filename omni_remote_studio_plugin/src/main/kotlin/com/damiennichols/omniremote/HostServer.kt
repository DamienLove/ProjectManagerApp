package com.damiennichols.omniremote

import com.fasterxml.jackson.databind.ObjectMapper
import com.google.auth.oauth2.GoogleCredentials
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.cloud.firestore.SetOptions
import com.google.firebase.cloud.FirestoreClient
import com.intellij.ide.util.PropertiesComponent
import com.intellij.openapi.project.Project
import io.javalin.Javalin
import java.io.BufferedReader
import java.io.File
import java.io.FileInputStream
import java.io.InputStreamReader
import java.util.concurrent.ConcurrentHashMap

data class CommandRequest(val cmd: String, val cwd: String?)
data class CommandResponse(val output: String, val exitCode: Int)
data class ProjectInfo(val name: String, val path: String)

class HostServer(private val project: Project, private val onLog: (String) -> Unit) {

    private var server: Javalin? = null
    private val objectMapper = ObjectMapper()
    private val defaultFirebaseProjectId = "omniremote-e7afd"
    private val sessions = ConcurrentHashMap<String, Process>()

    fun start(port: Int, token: String) {
        if (server != null) {
            onLog("Server is already running.")
            return
        }

        ensureFirebaseInitialized()
        syncToFirestore(port, token)

        server = Javalin.create().apply {
            before { ctx ->
                val requestToken = ctx.header("X-Omni-Token") ?: ctx.queryParam("token")
                if (requestToken != token) {
                    ctx.status(401).result("Unauthorized")
                }
            }

            get("/api/health") { ctx ->
                ctx.json(mapOf("status" to "ok"))
            }

            post("/api/command") { ctx ->
                val request = objectMapper.readValue(ctx.body(), CommandRequest::class.java)
                onLog("Executing command: ${request.cmd}")
                val response = executeCommand(request.cmd, request.cwd)
                ctx.json(response)
            }

            ws("/ws/terminal") { ws ->
                ws.onConnect { ctx ->
                    val requestToken = ctx.header("X-Omni-Token") ?: ctx.queryParam("token")
                    if (requestToken != token) {
                        ctx.closeSession(1008, "Unauthorized")
                        return@onConnect
                    }
                    onLog("Terminal connected")
                }

                ws.onMessage { ctx ->
                    val message = ctx.message()
                    // onLog("Terminal message: $message")
                    try {
                        val data = objectMapper.readValue(message, Map::class.java)
                        val type = data["type"] as? String

                        when (type) {
                            "run" -> {
                                val cmd = data["cmd"] as? String ?: return@onMessage
                                val cwd = data["cwd"] as? String
                                onLog("Terminal command: $cmd")

                                val process = ProcessBuilder(parseCommand(cmd))
                                    .directory(cwd?.let { java.io.File(it) } ?: project.basePath?.let { java.io.File(it) })
                                    .redirectErrorStream(true)
                                    .start()

                                val sessionId = java.util.UUID.randomUUID().toString()
                                sessions[sessionId] = process

                                ctx.send(objectMapper.writeValueAsString(mapOf(
                                    "type" to "started",
                                    "sessionId" to sessionId
                                )))

                                Thread {
                                    try {
                                        val reader = process.inputStream.bufferedReader()
                                        val buffer = CharArray(1024)
                                        var read: Int
                                        while (process.isAlive || process.inputStream.available() > 0) {
                                            read = reader.read(buffer)
                                            if (read == -1) break
                                            if (read > 0) {
                                                val chunk = String(buffer, 0, read)
                                                try {
                                                    ctx.send(objectMapper.writeValueAsString(mapOf(
                                                        "type" to "output",
                                                        "sessionId" to sessionId,
                                                        "data" to chunk
                                                    )))
                                                } catch (e: Exception) {
                                                    break
                                                }
                                            }
                                        }
                                    } catch (e: Exception) {
                                         // ignore
                                    } finally {
                                        val exitCode = try { process.waitFor() } catch(e:Exception) { -1 }
                                        try {
                                            ctx.send(objectMapper.writeValueAsString(mapOf(
                                                "type" to "exit",
                                                "sessionId" to sessionId,
                                                "code" to exitCode.toString()
                                            )))
                                        } catch(e:Exception) {}
                                        sessions.remove(sessionId)
                                    }
                                }.start()
                            }
                            "stdin" -> {
                                val sessionId = data["sessionId"] as? String
                                val inputData = data["data"] as? String
                                if (sessionId != null && inputData != null) {
                                    val proc = sessions[sessionId]
                                    if (proc != null) {
                                        try {
                                            val writer = proc.outputStream.bufferedWriter()
                                            writer.write(inputData)
                                            writer.flush()
                                        } catch (e: Exception) {
                                            onLog("Failed to write to stdin: ${e.message}")
                                        }
                                    }
                                }
                            }
                            "cancel" -> {
                                val sessionId = data["sessionId"] as? String
                                if (sessionId != null) {
                                    sessions[sessionId]?.destroy()
                                }
                            }
                            else -> {
                                ctx.send(objectMapper.writeValueAsString(mapOf(
                                    "type" to "error",
                                    "message" to "Unknown message type: $type"
                                )))
                            }
                        }
                    } catch (e: Exception) {
                        ctx.send(objectMapper.writeValueAsString(mapOf(
                            "type" to "error",
                            "message" to (e.message ?: "Unknown error")
                        )))
                    }
                }

                ws.onClose { ctx ->
                    onLog("Terminal disconnected")
                    sessions.values.forEach { try { it.destroy() } catch(e:Exception){} }
                    sessions.clear()
                }
            }
        }.start(port)

        onLog("Host server started on port $port")
    }

    fun stop() {
        server?.stop()
        server = null
        sessions.values.forEach { try { it.destroy() } catch(e:Exception){} }
        sessions.clear()
        onLog("Host server stopped.")
    }

    private fun syncToFirestore(port: Int, token: String) {
        try {
            ensureFirebaseInitialized()
            val db = FirestoreClient.getFirestore()
            val props = PropertiesComponent.getInstance()
            val env = loadEnvFile()
            val docPath = System.getenv("FIREBASE_DOCUMENT_PATH")
                ?: props.getValue("omniremote.firebaseDocPath")
                ?: env["FIREBASE_DOCUMENT_PATH"]
                
            if (docPath != null && docPath.contains('/')) {
                val parts = docPath.split('/')
                val collection = parts[0]
                val userDocId = parts[1]
                val data = mapOf(
                    "host" to (System.getenv("REMOTE_SYNC_HOST") ?: "127.0.0.1"),
                    "pmPort" to port,
                    "idePort" to port,
                    "token" to token,
                    "updated_at" to com.google.cloud.Timestamp.now(),
                    "agent" to "intellij-plugin"
                )
                // Write to root level (primary location for Android app)
                db.collection(collection).document(userDocId).set(data, SetOptions.merge()).get()
                // Also write to subcollection for backward compatibility  
                db.collection(collection).document(userDocId).collection("config").document("connection").set(data).get()
                onLog("Synced connection info to Firestore (root + subcollection).")
            } else {
                onLog("FIREBASE_DOCUMENT_PATH not set (format: users/{uid}). Skipping Firestore sync.")
            }
        } catch (e: Exception) {
            onLog("Firestore sync failed: ${e.message}")
        }
    }

    private fun ensureFirebaseInitialized() {
        if (FirebaseApp.getApps().isNotEmpty()) {
            return
        }
        try {
            val props = PropertiesComponent.getInstance()
            val env = loadEnvFile()
            val credentialsPath = System.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                ?: props.getValue("omniremote.firebaseCredentialsPath")
                ?: env["GOOGLE_APPLICATION_CREDENTIALS"]
            val resolvedCredPath = resolveCredentialsPath(credentialsPath)
            if (resolvedCredPath != null) {
                val serviceAccount = FileInputStream(resolvedCredPath)
                val projectId = (System.getenv("FIREBASE_PROJECT_ID")
                    ?: props.getValue("omniremote.firebaseProjectId")
                    ?: env["FIREBASE_PROJECT_ID"]).orEmpty().ifBlank { defaultFirebaseProjectId }
                val options = FirebaseOptions.builder()
                    .setCredentials(GoogleCredentials.fromStream(serviceAccount))
                    .setProjectId(projectId)
                    .build()
                FirebaseApp.initializeApp(options)
                onLog("Firebase initialized with project: $projectId")
            } else {
                onLog("Firebase not initialized (Credentials path not set in environment or settings).")
            }
        } catch (e: Exception) {
            onLog("Firebase initialization failed: ${e.message}")
        }
    }

    private fun resolveCredentialsPath(path: String?): String? {
        if (path == null || path.isBlank()) {
            return null
        }
        val file = File(path)
        if (file.isFile) {
            return file.absolutePath
        }
        if (!file.exists() || !file.isDirectory) {
            return null
        }
        val jsonFiles = file.listFiles { f -> f.isFile && f.extension.equals("json", ignoreCase = true) }
            ?: return null
        for (candidate in jsonFiles) {
            try {
                val text = candidate.readText()
                if (text.contains("\"type\": \"service_account\"")) {
                    return candidate.absolutePath
                }
            } catch (_: Exception) {
                // ignore unreadable files
            }
        }
        return null
    }

    private fun loadEnvFile(): Map<String, String> {
        val base = project.basePath ?: return emptyMap()
        val envFile = File(base, "secrets.env")
        if (!envFile.exists()) {
            return emptyMap()
        }
        val env = mutableMapOf<String, String>()
        envFile.readLines().forEach { line ->
            val trimmed = line.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                return@forEach
            }
            val idx = trimmed.indexOf('=')
            if (idx <= 0) {
                return@forEach
            }
            val key = trimmed.substring(0, idx).trim()
            val value = trimmed.substring(idx + 1).trim()
            if (key.isNotEmpty()) {
                env[key] = value
            }
        }
        return env
    }

    private fun executeCommand(command: String, workingDir: String?): CommandResponse {
        return try {
            val process = ProcessBuilder(parseCommand(command))
                .directory(workingDir?.let { java.io.File(it) } ?: project.basePath?.let { java.io.File(it) })
                .redirectErrorStream(true)
                .start()

            val output = process.inputStream.bufferedReader().readText()
            val exitCode = process.waitFor()
            CommandResponse(output, exitCode)
        } catch (e: Exception) {
            CommandResponse(e.message ?: "An error occurred", -1)
        }
    }

    private fun parseCommand(command: String): List<String> {
        val args = mutableListOf<String>()
        val currentArg = StringBuilder()
        var inQuotes = false
        for (char in command) {
            when {
                char == ' ' && !inQuotes -> {
                    if (currentArg.isNotEmpty()) {
                        args.add(currentArg.toString())
                        currentArg.clear()
                    }
                }
                char == '"' -> inQuotes = !inQuotes
                else -> currentArg.append(char)
            }
        }
        if (currentArg.isNotEmpty()) {
            args.add(currentArg.toString())
        }
        return args
    }
}
