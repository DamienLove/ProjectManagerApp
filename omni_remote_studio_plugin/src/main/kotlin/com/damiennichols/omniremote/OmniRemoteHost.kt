package com.damiennichols.omniremote

import com.google.gson.Gson
import io.ktor.serialization.gson.*
import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.plugins.contentnegotiation.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import java.io.InputStreamReader
import java.util.*
import java.util.concurrent.ConcurrentHashMap

class OmniRemoteHost {
    private var server: NettyApplicationEngine? = null
    private val gson = Gson()
    private val sessions = ConcurrentHashMap<String, Process>()
    private var authToken: String = ""

    fun start(port: Int, token: String) {
        authToken = token
        server = embeddedServer(Netty, port = port) {
            install(WebSockets)
            install(ContentNegotiation) {
                gson()
            }

            routing {
                get("/api/health") {
                    val tokenHeader = call.request.headers["X-Omni-Token"]
                    if (tokenHeader != authToken) {
                        call.respond(io.ktor.http.HttpStatusCode.Unauthorized)
                    } else {
                        call.respond(mapOf("status" to "ok", "app" to "Omni Remote Plugin Host"))
                    }
                }

                webSocket("/ws/terminal") {
                    val tokenParam = call.request.queryParameters["token"]
                    if (tokenParam != authToken) {
                        close(CloseReason(CloseReason.Codes.CANNOT_ACCEPT, "Unauthorized"))
                        return@webSocket
                    }

                    try {
                        for (frame in incoming) {
                            if (frame is Frame.Text) {
                                val text = frame.readText()
                                handleTerminalMessage(this, text)
                            }
                        }
                    } catch (e: Exception) {
                        send(Frame.Text(gson.toJson(mapOf("type" to "error", "message" to e.message))))
                    }
                }
            }
        }.start(wait = false)
    }

    fun stop() {
        server?.stop(1000, 2000)
        server = null
    }

    private suspend fun handleTerminalMessage(session: WebSocketServerSession, message: String) {
        val payload = gson.fromJson(message, Map::class.java)
        val type = payload["type"] as? String
        when (type) {
            "run" -> {
                val cmd = payload["cmd"] as? String ?: return
                val cwd = payload["cwd"] as? String
                val sessionId = UUID.randomUUID().toString()
                
                val builder = ProcessBuilder(cmd.split(" "))
                if (cwd != null) builder.directory(java.io.File(cwd))
                builder.redirectErrorStream(true)
                
                val process = builder.start()
                sessions[sessionId] = process
                
                session.send(Frame.Text(gson.toJson(mapOf("type" to "started", "sessionId" to sessionId))))
                
                CoroutineScope(Dispatchers.IO).launch {
                    val reader = InputStreamReader(process.inputStream)
                    val buffer = CharArray(1024)
                    var length: Int
                    while (reader.read(buffer).also { length = it } != -1) {
                        val data = String(buffer, 0, length)
                        session.send(Frame.Text(gson.toJson(mapOf("type" to "output", "sessionId" to sessionId, "data" to data))))
                    }
                    val exitCode = process.waitFor()
                    session.send(Frame.Text(gson.toJson(mapOf("type" to "exit", "sessionId" to sessionId, "code" to exitCode.toString()))))
                    sessions.remove(sessionId)
                }
            }
            "stdin" -> {
                val sid = payload["sessionId"] as? String ?: return
                val data = payload["data"] as? String ?: return
                val process = sessions[sid] ?: return
                process.outputStream.write(data.toByteArray())
                process.outputStream.flush()
            }
        }
    }
}
