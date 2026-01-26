import os

file_path = r'app\src\main\java\com\damiennichols\omniremote\MainActivity.kt'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add TerminalSession data class
session_class = """
data class TerminalSession(
    val id: String,
    val name: String,
    val project: String,
    val lines: MutableList<String> = mutableStateListOf()
)
"""

if "data class TerminalSession" not in content:
    content = content.replace("data class Project", session_class + "\ndata class Project")

# New TerminalScreen implementation
new_terminal_screen = r"""
@Composable
private fun TerminalScreen(
    cwd: String,
    command: String,
    status: String,
    sessions: List<TerminalSession>,
    activeSessionIdx: Int,
    connected: Boolean,
    onBack: () -> Unit,
    onCwdChange: (String) -> Unit,
    onCommandChange: (String) -> Unit,
    onSendInput: (String) -> Unit,
    onNewSession: (String) -> Unit,
    onSelectSession: (Int) -> Unit,
    onCloseSession: (Int) -> Unit,
    onClear: () -> Unit,
    projects: List<Project>
) {
    val listState = rememberLazyListState()
    var showProjectSelector by remember { mutableStateOf(false) }
    val activeSession = sessions.getOrNull(activeSessionIdx)

    LaunchedEffect(activeSession?.lines?.size) {
        if (activeSession != null && activeSession.lines.isNotEmpty()) {
            listState.animateScrollToItem(activeSession.lines.size - 1)
        }
    }

    if (showProjectSelector) {
        AlertDialog(
            onDismissRequest = { showProjectSelector = false },
            title = { Text("New Terminal Session") },
            text = {
                LazyColumn {
                    item {
                        ListItem(
                            headlineContent = { Text("System Terminal") },
                            modifier = Modifier.clickable {
                                onNewSession("System")
                                showProjectSelector = false
                            }
                        )
                    }
                    items(projects) { proj ->
                        ListItem(
                            headlineContent = { Text(proj.name) },
                            supportingContent = { Text(proj.status) },
                            modifier = Modifier.clickable {
                                onNewSession(proj.name)
                                showProjectSelector = false
                            }
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showProjectSelector = false }) { Text("Cancel") }
            }
        )
    }

    Column(modifier = Modifier.fillMaxSize()) {
        ScreenHeader(
            title = "Terminal", 
            status = status, 
            onBack = onBack,
            actions = {
                IconButton(onClick = { showProjectSelector = true }) {
                    Icon(Icons.Default.Add, contentDescription = "New Session", tint = Accent)
                }
            }
        )
        
        if (sessions.isNotEmpty()) {
            ScrollableTabRow(
                selectedTabIndex = activeSessionIdx,
                containerColor = Color.Transparent,
                contentColor = Accent,
                edgePadding = 8.dp,
                divider = {}
            ) {
                sessions.forEachIndexed { index, session ->
                    Tab(
                        selected = activeSessionIdx == index,
                        onClick = { onSelectSession(index) },
                        text = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(session.name, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Spacer(modifier = Modifier.width(4.dp))
                                Icon(
                                    Icons.Default.Close,
                                    contentDescription = "Close",
                                    modifier = Modifier.size(14.dp).clickable { onCloseSession(index) },
                                    tint = TextMuted
                                )
                            }
                        }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(4.dp))
        
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 8.dp)
                .border(BorderStroke(1.dp, Color(0xFF1F2937)), RoundedCornerShape(10.dp))
                .background(Color(0xFF0B0F14), RoundedCornerShape(10.dp))
                .padding(8.dp)
        ) {
            if (activeSession != null) {
                LazyColumn(state = listState) {
                    items(activeSession.lines) { line ->
                        Text(
                            text = line.trimEnd(),
                            color = TerminalGreen,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp
                        )
                    }
                }
            } else {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No active session. Tap + to start.", color = TextMuted)
                }
            }
        }

        if (activeSession != null) {
            Column(modifier = Modifier.padding(8.dp)) {
                OutlinedTextField(
                    value = cwd,
                    onValueChange = onCwdChange,
                    label = { Text("Working directory (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                    textStyle = TextStyle(color = TextPrimary, fontSize = 14.sp),
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = command,
                        onValueChange = onCommandChange,
                        label = { Text("Command") },
                        modifier = Modifier.weight(1f),
                        textStyle = TextStyle(color = TextPrimary, fontSize = 14.sp),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = { onSendInput(command + "\n") })
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = { onSendInput(command + "\n") },
                        colors = ButtonDefaults.buttonColors(containerColor = Accent),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Send")
                    }
                }
                Row {
                    TextButton(onClick = onClear) { Text("Clear", color = TextMuted) }
                }
            }
        }
    }
}