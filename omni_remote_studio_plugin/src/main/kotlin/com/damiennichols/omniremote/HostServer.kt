package com.damiennichols.omniremote

import com.fasterxml.jackson.databind.ObjectMapper
import com.google.auth.oauth2.GoogleCredentials
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.cloud.FirestoreClient
import com.intellij.openapi.project.Project
import io.javalin.Javalin
import java.io.BufferedReader
import java.io.FileInputStream
import java.io.InputStreamReader

data class CommandRequest(val cmd: String, val cwd: String?)
data class CommandResponse(val output: String, val exitCode: Int)
data class ProjectInfo(val name: String, val path: String)

class HostServer(private val project: Project, private val onLog: (String) -> Unit) {

    private var server: Javalin? = null
    private val objectMapper = ObjectMapper()

    init {
        try {
            if (FirebaseApp.getApps().isEmpty()) {
                val credentialsPath = System.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if (credentialsPath != null) {
                    val serviceAccount = FileInputStream(credentialsPath)
                    val options = FirebaseOptions.builder()
                        .setCredentials(GoogleCredentials.fromStream(serviceAccount))
                        .setProjectId(System.getenv("FIREBASE_PROJECT_ID"))
                        .build()
                    FirebaseApp.initializeApp(options)
                    onLog("Firebase initialized.")
                } else {
                    onLog("Firebase not initialized (GOOGLE_APPLICATION_CREDENTIALS not set).")
                }
            }
        } catch (e: Exception) {
            onLog("Firebase initialization failed: ${e.message}")
        }
    }

    fun start(port: Int, token: String) {
        if (server != null) {
            onLog("Server is already running.")
            return
        }

        syncToFirestore(port, token)

        server = Javalin.create().apply {
            before { ctx ->
                val requestToken = ctx.header("X-Omni-Token")
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
                    onLog("Terminal connected")
                }

                ws.onMessage { ctx ->
                    val command = ctx.message()
                    onLog("Terminal command: $command")
                    try {
                        val process = ProcessBuilder(parseCommand(command))
                            .directory(project.basePath?.let { java.io.File(it) })
                            .redirectErrorStream(true)
                            .start()

                        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
                            var line: String?
                            while (reader.readLine().also { line = it } != null) {
                                ctx.send(line!!)
                            }
                        }
                        val exitCode = process.waitFor()
                        ctx.send("Process exited with code $exitCode")
                    } catch (e: Exception) {
                        ctx.send("Error executing command: ${e.message}")
                    }
                }

                ws.onClose { ctx ->
                    onLog("Terminal disconnected")
                }
            }
        }.start(port)

        onLog("Host server started on port $port")
    }

    fun stop() {
        server?.stop()
        server = null
        onLog("Host server stopped.")
    }

    private fun syncToFirestore(port: Int, token: String) {
        try {
            val db = FirestoreClient.getFirestore()
            val docPath = System.getenv("FIREBASE_DOCUMENT_PATH")
            if (docPath != null) {
                val (collection, doc) = docPath.split('/')
                val data = mapOf(
                    "host" to (System.getenv("REMOTE_SYNC_HOST") ?: "127.0.0.1"),
                    "port" to port,
                    "token" to token,
                    "updated_at" to com.google.cloud.Timestamp.now()
                )
                db.collection(collection).document(doc).set(data).get()
                onLog("Synced connection info to Firestore.")
            } else {
                onLog("FIREBASE_DOCUMENT_PATH not set. Skipping Firestore sync.")
            }
        } catch (e: Exception) {
            onLog("Firestore sync failed: ${e.message}")
        }
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
