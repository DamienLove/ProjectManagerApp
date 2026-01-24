import os

file_path = r'..\omni_remote_studio_plugin\src\main\kotlin\com\damiennichols\omniremote\HostServer.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add necessary imports
new_imports = """import com.intellij.openapi.project.ProjectManager
import java.util.concurrent.ConcurrentHashMap
import java.util.UUID"""

if "import com.intellij.openapi.project.ProjectManager" not in content:
    content = content.replace("import com.intellij.openapi.project.Project", "import com.intellij.openapi.project.Project\n" + new_imports)

# Update HostServer class to manage sessions
# We will use a map:sessionId -> TerminalSession
terminal_session_class = """
class TerminalSession(
    val id: String,
    val project: Project?,
    val process: Process,
    val outputThread: Thread
)
"""

if "class TerminalSession" not in content:
    content = content.replace("class HostServer", terminal_session_class + "\nclass HostServer")

# Add sessions map to HostServer
if "private val sessions = ConcurrentHashMap<String, TerminalSession>()" not in content:
    content = content.replace("private val objectMapper = ObjectMapper()", "private val objectMapper = ObjectMapper()\n    private val sessions = ConcurrentHashMap<String, TerminalSession>()")

# Add /api/projects endpoint
projects_api = """
            get(\"/api/projects\") { ctx ->
                val projects = ProjectManager.getInstance().openProjects.map { 
                    mapOf(\"name\" to it.name, \"path\" to it.basePath)
                }
                ctx.json(mapOf(\"projects\" to projects))
            }

            post(\"/api/close-project\") { ctx ->
                val name = ctx.queryParam(\"name\")
                val projectToClose = ProjectManager.getInstance().openProjects.find { it.name == name }
                if (projectToClose != null) {
                    com.intellij.openapi.wm.impl.ProjectFrameHelper.getFrameHelper(com.intellij.openapi.wm.WindowManager.getInstance().getFrame(projectToClose))?.close()
                    ctx.json(mapOf(\"status\" to \"closing\"))
                } else {
                    ctx.status(404).result(\"Project not found\")
                }
            }
"""

if "/api/projects" not in content:
    content = content.replace('get(\"/api/health\") { ctx ->', projects_api + '\n            get(\"/api/health\") { ctx ->')

# Update WebSocket handler to support interactive terminal
# This is a complex replacement, so we'll replace the whole ws block
new_ws_handler = """
            ws(\"/ws/terminal\") { ws ->
                ws.onConnect { ctx ->
                    val requestToken = ctx.header(\"X-Omni-Token\") ?: ctx.queryParam(\"token\")
                    if (requestToken != token) {
                        ctx.closeSession(1008, \"Unauthorized\")
                        return@onConnect
                    }
                    onLog(\"Terminal connected\")
                }

                ws.onMessage { ctx ->
                    val message = ctx.message()
                    try {
                        val data = objectMapper.readValue(message, Map::class.java)
                        val type = data[\"type\"] as? String

                        when (type) {
                            \"run\" -> {
                                val projectName = data[\"project\"] as? String
                                val cmd = data[\"cmd\"] as? String ?: \"powershell.exe\"
                                val cwd = data[\"cwd\"] as? String
                                
                                val targetProject = if (projectName != null && projectName != \"System\") {
                                    ProjectManager.getInstance().openProjects.find { it.name == projectName }
                                } else null
                                
                                val workingDir = cwd?.let { File(it) } 
                                    ?: targetProject?.basePath?.let { File(it) }
                                    ?: project.basePath?.let { File(it) }

                                val pb = ProcessBuilder(parseCommand(cmd))
                                if (workingDir != null && workingDir.exists()) pb.directory(workingDir)
                                pb.redirectErrorStream(true)
                                val proc = pb.start()
                                
                                val sid = UUID.randomUUID().toString()
                                
                                val thread = Thread { 
                                    try {
                                        val reader = proc.inputStream.bufferedReader()
                                        val buffer = CharArray(1024)
                                        var charsRead: Int
                                        while (reader.read(buffer).also { charsRead = it }) != -1) {
                                            val output = String(buffer, 0, charsRead)
                                            ctx.send(objectMapper.writeValueAsString(mapOf(
                                                "type" to "output",
                                                "sessionId" to sid,
                                                "data" to output
                                            )))
                                        }
                                    } catch (e: Exception) { } // TODO: Handle exceptions properly
                                    
                                    val exitCode = proc.waitFor()
                                    ctx.send(objectMapper.writeValueAsString(mapOf(
                                        "type" to "exit",
                                        "sessionId" to sid,
                                        "code" to exitCode.toString()
                                    )))
                                    sessions.remove(sid)
                                }
                                thread.start()
                                
                                val session = TerminalSession(sid, targetProject, proc, thread)
                                sessions[sid] = session
                                
                                ctx.send(objectMapper.writeValueAsString(mapOf(
                                    "type" to "started",
                                    "sessionId" to sid,
                                    "project" to (targetProject?.name ?: "System")
                                )))
                            }
                            \"stdin\" -> {
                                val sid = data[\"sessionId\"] as? String ?: return@onMessage
                                val input = data[\"data\"] as? String ?: ""
                                val session = sessions[sid]
                                if (session != null) {
                                    session.process.outputStream.write(input.toByteArray())
                                    session.process.outputStream.flush()
                                }
                            }
                            \"cancel\" -> {
                                val sid = data[\"sessionId\"] as? String ?: return@onMessage
                                sessions[sid]?.process?.destroy()
                            }
                        }
                    } catch (e: Exception) {
                        onLog("WS Error: ${e.message}")
                    }
                }

                ws.onClose { ctx ->
                    onLog("Terminal disconnected")
                    // We don't automatically kill sessions on close to allow re-attach if needed?
                    # For now, let's keep it simple and clean up.
                }
            }
"""

# I need to be careful with the replacement to not break the Javalin start() structure.
# I'll use a simpler search/replace for the ws block.
import re
content = re.sub(r'ws\(\"/ws/terminal\"\) \{.*?\}\n\s*\}\.start\(port\)', new_ws_handler + '        }.start(port)', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully updated HostServer.kt")
