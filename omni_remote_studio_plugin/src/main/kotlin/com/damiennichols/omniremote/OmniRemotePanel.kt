package com.damiennichols.omniremote

import com.google.gson.Gson
import com.intellij.ide.util.PropertiesComponent
import com.intellij.openapi.application.ApplicationManager
import java.awt.BorderLayout
import java.awt.Color
import java.awt.Font
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import java.awt.Insets
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.net.http.WebSocket
import java.time.Duration
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CompletionStage
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JCheckBox
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JOptionPane
import javax.swing.JPanel
import javax.swing.JPasswordField
import javax.swing.JScrollPane
import com.intellij.openapi.project.Project
import javax.swing.JTabbedPane
import javax.swing.JTextArea
import javax.swing.JTextField
import javax.swing.SwingUtilities

class OmniRemotePanel(project: Project) : JPanel(BorderLayout()) {
      private val MAX_TERMINAL_LINES = 2000

    private val props = PropertiesComponent.getInstance()
    private val hostField = JTextField()
    private val hostServer = HostServer(project) { msg -> logHostMessage(msg) }
    private val portField = JTextField()
    private val tokenField = JPasswordField()
    private val secureCheck = JCheckBox("Secure (HTTPS)")
    private val statusLabel = JLabel("Not connected")
    private val listModel = DefaultListModel<ProjectEntry>()
    private val projectList = JList(listModel)
    private val terminalStatusLabel = JLabel("Terminal: disconnected")
    private val terminalOutput = JTextArea()
    private val terminalCommandField = JTextField()
    private val terminalCwdField = JTextField()
    private val terminalConnectButton = JButton("Connect Terminal")
    private val terminalDisconnectButton = JButton("Disconnect")
    private val terminalRunButton = JButton("Run")
    private val terminalSendButton = JButton("Send")
    private val terminalStopButton = JButton("Stop")
    private var terminalSocket: WebSocket? = null
    private var terminalSessionId: String? = null

    private val client = HttpClient.newBuilder().build()
    private val gson = Gson()

    init {
        loadSettings()
        add(buildConfigPanel(), BorderLayout.NORTH)
        add(buildContentTabs(), BorderLayout.CENTER)
    }

    private fun buildContentTabs(): JTabbedPane {
        val tabs = JTabbedPane()
        tabs.addTab("Projects", buildProjectsPanel())
        tabs.addTab("Terminal", buildTerminalPanel())
        tabs.addTab("Host Mode", buildHostModePanel())
        return tabs
    }

    private fun buildHostModePanel(): JPanel {
        val panel = JPanel(BorderLayout())
        val hostPortField = JTextField("8766")
        val hostTokenField = JPasswordField()
        val startHostButton = JButton("Start Host")
        val stopHostButton = JButton("Stop Host")
        val hostLog = JTextArea()

        hostLog.isEditable = false
        hostLog.font = Font("Consolas", Font.PLAIN, 12)

        val configPanel = JPanel(GridBagLayout())
        val c = GridBagConstraints().apply {
            fill = GridBagConstraints.HORIZONTAL
            insets = Insets(4, 8, 4, 8)
            weightx = 1.0
        }

        addRow(configPanel, c, 0, "Host Port", hostPortField)
        addRow(configPanel, c, 1, "Host Token", hostTokenField)

        c.gridy = 2
        c.gridx = 0
        configPanel.add(startHostButton, c)
        c.gridx = 1
        configPanel.add(stopHostButton, c)

        startHostButton.addActionListener {
            val port = hostPortField.text.toIntOrNull() ?: 8766
            val token = String(hostTokenField.password)
            if (token.isNotBlank()) {
                hostServer.start(port, token)
            } else {
                logHostMessage("Token cannot be empty.")
            }
        }

        stopHostButton.addActionListener {
            hostServer.stop()
        }

        panel.add(configPanel, BorderLayout.NORTH)
        panel.add(JScrollPane(hostLog), BorderLayout.CENTER)

        // Find the JTextArea in the host panel to log messages
        val logTextArea = (panel.getComponent(1) as JScrollPane).viewport.view as JTextArea
        hostServerLog = logTextArea

        return panel
    }

    private fun logHostMessage(message: String) {
        SwingUtilities.invokeLater {
            hostServerLog?.append("$message\n")
        }
    }

    @Volatile
    private var hostServerLog: JTextArea? = null

    private fun buildProjectsPanel(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.add(JScrollPane(projectList), BorderLayout.CENTER)
        panel.add(buildActionPanel(), BorderLayout.SOUTH)
        return panel
    }

    private fun buildConfigPanel(): JPanel {
        val panel = JPanel(GridBagLayout())
        val c = GridBagConstraints().apply {
            fill = GridBagConstraints.HORIZONTAL
            insets = Insets(4, 8, 4, 8)
            weightx = 1.0
        }

        var row = 0
        addRow(panel, c, row++, "Host", hostField)
        addRow(panel, c, row++, "Port", portField)
        addRow(panel, c, row++, "Token", tokenField)

        c.gridx = 0
        c.gridy = row
        c.gridwidth = 2
        panel.add(secureCheck, c)

        val testButton = JButton("Test Connection")
        testButton.addActionListener {
            saveSettings()
            runInBackground {
                val response = request("GET", "/api/health")
                if (response != null && response.statusCode() == 200) {
                    updateStatus("Connected")
                } else {
                    val code = response?.statusCode() ?: 0
                    updateStatus("Connection failed ($code)")
                }
            }
        }

        val refreshButton = JButton("Refresh Projects")
        refreshButton.addActionListener {
            saveSettings()
            refreshProjects()
        }

        c.gridy = row + 1
        c.gridwidth = 1
        c.gridx = 0
        panel.add(testButton, c)
        c.gridx = 1
        panel.add(refreshButton, c)

        c.gridx = 0
        c.gridy = row + 2
        c.gridwidth = 2
        panel.add(statusLabel, c)

        return panel
    }

    private fun buildTerminalPanel(): JPanel {
        val panel = JPanel(BorderLayout())

        terminalOutput.isEditable = false
        terminalOutput.font = Font("Consolas", Font.PLAIN, 12)
        terminalOutput.background = Color(16, 18, 20)
        terminalOutput.foreground = Color(170, 255, 170)
        terminalOutput.caretColor = Color(170, 255, 170)
        terminalOutput.lineWrap = false

        val header = JPanel(GridBagLayout())
        val c = GridBagConstraints().apply {
            fill = GridBagConstraints.HORIZONTAL
            insets = Insets(4, 8, 4, 8)
            weightx = 1.0
        }

        c.gridx = 0
        c.gridy = 0
        c.weightx = 0.0
        header.add(terminalConnectButton, c)

        c.gridx = 1
        header.add(terminalDisconnectButton, c)

        c.gridx = 2
        header.add(JLabel("CWD"), c)

        c.gridx = 3
        c.weightx = 1.0
        header.add(terminalCwdField, c)

        c.gridx = 0
        c.gridy = 1
        c.gridwidth = 4
        header.add(terminalStatusLabel, c)

        terminalConnectButton.addActionListener { connectTerminal() }
        terminalDisconnectButton.addActionListener { disconnectTerminal() }

        val inputPanel = JPanel(BorderLayout())
        inputPanel.add(terminalCommandField, BorderLayout.CENTER)

        val commandButtons = JPanel()
        commandButtons.add(terminalRunButton)
        commandButtons.add(terminalSendButton)
        commandButtons.add(terminalStopButton)
        inputPanel.add(commandButtons, BorderLayout.EAST)

        terminalRunButton.addActionListener { runTerminalCommand() }
        terminalSendButton.addActionListener { sendTerminalInput() }
        terminalStopButton.addActionListener { cancelTerminalCommand() }
        terminalCommandField.addActionListener {
            if (terminalSessionId == null) {
                runTerminalCommand()
            } else {
                sendTerminalInput()
            }
        }

        panel.add(header, BorderLayout.NORTH)
        panel.add(JScrollPane(terminalOutput), BorderLayout.CENTER)
        panel.add(inputPanel, BorderLayout.SOUTH)
        return panel
    }

    private fun buildActionPanel(): JPanel {
        val panel = JPanel()

        val activateButton = JButton("Activate")
        activateButton.addActionListener {
            val entry = projectList.selectedValue ?: return@addActionListener
            runInBackground {
                request("POST", "/api/projects/${encode(entry.name)}/activate")
                refreshProjects()
            }
        }

        val deactivateButton = JButton("Deactivate")
        deactivateButton.addActionListener {
            val entry = projectList.selectedValue ?: return@addActionListener
            runInBackground {
                request("POST", "/api/projects/${encode(entry.name)}/deactivate")
                refreshProjects()
            }
        }

        val openStudioButton = JButton("Open in Studio")
        openStudioButton.addActionListener {
            val entry = projectList.selectedValue ?: return@addActionListener
            runInBackground {
                request("POST", "/api/projects/${encode(entry.name)}/open-studio")
            }
        }

        panel.add(activateButton)
        panel.add(deactivateButton)
        panel.add(openStudioButton)
        return panel
    }

    private fun addRow(panel: JPanel, c: GridBagConstraints, row: Int, label: String, field: JTextField) {
        c.gridx = 0
        c.gridy = row
        c.weightx = 0.0
        panel.add(JLabel(label), c)

        c.gridx = 1
        c.weightx = 1.0
        panel.add(field, c)
    }

    private fun loadSettings() {
        hostField.text = props.getValue("omniremote.host", "")
        portField.text = props.getValue("omniremote.port", "")
        tokenField.text = props.getValue("omniremote.token", "")
        secureCheck.isSelected = props.getBoolean("omniremote.secure", false)
    }

    private fun saveSettings() {
        props.setValue("omniremote.host", hostField.text.trim())
        props.setValue("omniremote.port", portField.text.trim())
        props.setValue("omniremote.token", String(tokenField.password))
        props.setValue("omniremote.secure", secureCheck.isSelected)
    }

    private fun buildBaseUrl(): String? {
        val host = hostField.text.trim()
        if (host.isBlank()) {
            showMessage("Host is required.")
            return null
        }
        val token = String(tokenField.password).trim()
        if (token.isBlank()) {
            showMessage("Token is required.")
            return null
        }

        if (host.startsWith("http://") || host.startsWith("https://")) {
            return host.trimEnd('/')
        }

        val scheme = if (secureCheck.isSelected) "https" else "http"
        val port = portField.text.trim()
        val portPart = if (port.isNotBlank()) ":$port" else ""
        return "$scheme://$host$portPart"
    }

    private fun buildWsUrl(): String? {
        val baseUrl = buildBaseUrl() ?: return null
        val wsBase = if (baseUrl.startsWith("https://")) {
            baseUrl.replaceFirst("https://", "wss://")
        } else {
            baseUrl.replaceFirst("http://", "ws://")
        }
        return wsBase.trimEnd('/') + "/ws/terminal"
    }

    private fun refreshProjects() {
        runInBackground {
            val response = request("GET", "/api/projects")
            if (response == null) {
                updateStatus("Connection failed")
                return@runInBackground
            }
            if (response.statusCode() != 200) {
                updateStatus("Error ${response.statusCode()}")
                return@runInBackground
            }
            val parsed = gson.fromJson(response.body(), ProjectsResponse::class.java)
            val projects = parsed.projects ?: emptyList()
            SwingUtilities.invokeLater {
                listModel.clear()
                projects.forEach { listModel.addElement(it) }
                updateStatus("Loaded ${projects.size} projects")
            }
        }
    }

    private fun request(method: String, path: String): HttpResponse<String>? {
        val baseUrl = buildBaseUrl() ?: return null
        val token = String(tokenField.password).trim()
        val url = baseUrl + path
        val requestBuilder = HttpRequest.newBuilder(URI.create(url))
            .header("X-Omni-Token", token)

        val request = when (method.uppercase()) {
            "POST" -> requestBuilder.POST(HttpRequest.BodyPublishers.noBody()).build()
            else -> requestBuilder.GET().build()
        }

        return try {
            client.send(request, HttpResponse.BodyHandlers.ofString())
        } catch (e: Exception) {
            showMessage("Request failed: ${e.message}")
            null
        }
    }

    private fun connectTerminal() {
        saveSettings()
        val wsUrl = buildWsUrl() ?: return
        val token = String(tokenField.password).trim()
        if (token.isBlank()) {
            showMessage("Token is required.")
            return
        }
        updateTerminalStatus("Terminal: connecting...")
        runInBackground {
            try {
                val ws = client.newWebSocketBuilder()
                    .connectTimeout(Duration.ofSeconds(10))
                    .header("X-Omni-Token", token)
                    .buildAsync(URI.create(wsUrl), TerminalListener())
                    .join()
                terminalSocket = ws
                updateTerminalStatus("Terminal: connected")
            } catch (e: Exception) {
                updateTerminalStatus("Terminal: connect failed")
                appendTerminal("== connect failed: ${e.message} ==\n")
            }
        }
    }

    private fun disconnectTerminal() {
        terminalSocket?.sendClose(1000, "bye")
        terminalSocket = null
        terminalSessionId = null
        updateTerminalStatus("Terminal: disconnected")
    }

    private fun runTerminalCommand() {
        val ws = terminalSocket
        if (ws == null) {
            showMessage("Terminal is not connected.")
            return
        }
        val cmd = terminalCommandField.text.trim()
        if (cmd.isBlank()) {
            return
        }
        val payload = mutableMapOf<String, Any>(
            "type" to "run",
            "cmd" to cmd,
        )
        val cwd = terminalCwdField.text.trim()
        if (cwd.isNotBlank()) {
            payload["cwd"] = cwd
        }
        ws.sendText(gson.toJson(payload), true)
        appendTerminal("> $cmd\n")
        terminalCommandField.text = ""
    }

    private fun sendTerminalInput() {
        val ws = terminalSocket
        if (ws == null) {
            showMessage("Terminal is not connected.")
            return
        }
        val sessionId = terminalSessionId
        if (sessionId == null) {
            showMessage("No active terminal session.")
            return
        }
        var data = terminalCommandField.text
        if (data.isBlank()) {
            return
        }
        if (!data.endsWith("\n")) {
            data += "\n"
        }
        val payload = mapOf(
            "type" to "stdin",
            "sessionId" to sessionId,
            "data" to data,
        )
        ws.sendText(gson.toJson(payload), true)
        terminalCommandField.text = ""
    }

    private fun cancelTerminalCommand() {
        val ws = terminalSocket
        if (ws == null) {
            return
        }
        val sessionId = terminalSessionId ?: return
        val payload = mapOf(
            "type" to "cancel",
            "sessionId" to sessionId,
        )
        ws.sendText(gson.toJson(payload), true)
    }

    private fun encode(value: String): String {
        return URLEncoder.encode(value, Charsets.UTF_8.name())
    }

    private fun updateStatus(text: String) {
        SwingUtilities.invokeLater { statusLabel.text = text }
    }

    private fun updateTerminalStatus(text: String) {
        SwingUtilities.invokeLater { terminalStatusLabel.text = text }
    }

    private fun appendTerminal(text: String) {
        SwingUtilities.invokeLater {
            terminalOutput.append(text)
            if (terminalOutput.lineCount > MAX_TERMINAL_LINES) {
                val linesToRemove = terminalOutput.lineCount - MAX_TERMINAL_LINES
                try {
                    val endOffset = terminalOutput.getLineEndOffset(linesToRemove - 1)
                    terminalOutput.document.remove(0, endOffset)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
            terminalOutput.caretPosition = terminalOutput.document.length
        }
    }

    private fun showMessage(message: String) {
        SwingUtilities.invokeLater {
            JOptionPane.showMessageDialog(this, message, "Omni Remote", JOptionPane.INFORMATION_MESSAGE)
        }
    }

    private fun runInBackground(task: () -> Unit) {
        ApplicationManager.getApplication().executeOnPooledThread(task)
    }

    private inner class TerminalListener : WebSocket.Listener {
        private val buffer = StringBuilder()

        override fun onOpen(webSocket: WebSocket) {
            appendTerminal("== terminal connected ==\n")
            webSocket.request(1)
        }

        override fun onText(
            webSocket: WebSocket,
            data: CharSequence,
            last: Boolean
        ): CompletionStage<*> {
            buffer.append(data)
            if (last) {
                val message = buffer.toString()
                buffer.setLength(0)
                handleTerminalMessage(message)
            }
            webSocket.request(1)
            return CompletableFuture.completedFuture(null)
        }

        override fun onClose(webSocket: WebSocket, statusCode: Int, reason: String?): CompletionStage<*> {
            appendTerminal("== terminal disconnected ($statusCode) ==\n")
            terminalSocket = null
            terminalSessionId = null
            updateTerminalStatus("Terminal: disconnected")
            return CompletableFuture.completedFuture(null)
        }

        override fun onError(webSocket: WebSocket?, error: Throwable) {
            appendTerminal("== terminal error: ${error.message} ==\n")
            terminalSocket = null
            terminalSessionId = null
            updateTerminalStatus("Terminal: error")
        }
    }

    private fun handleTerminalMessage(message: String) {
        try {
            val payload = gson.fromJson(message, Map::class.java)
            val type = payload["type"] as? String
            when (type) {
                "output" -> appendTerminal(payload["data"] as? String ?: "")
                "started" -> {
                    terminalSessionId = payload["sessionId"] as? String
                    appendTerminal("== session ${terminalSessionId ?: ""} ==\n")
                }
                "exit" -> {
                    val code = payload["code"]?.toString() ?: ""
                    appendTerminal("== exit $code ==\n")
                    terminalSessionId = null
                }
                "error" -> appendTerminal("== error: ${payload["message"]} ==\n")
                else -> appendTerminal(message + "\n")
            }
        } catch (e: Exception) {
            appendTerminal(message + "\n")
        }
    }
}

data class ProjectsResponse(val projects: List<ProjectEntry>?)

data class ProjectEntry(val name: String, val status: String) {
    override fun toString(): String {
        return "$name [$status]"
    }
}
