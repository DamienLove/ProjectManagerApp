package com.damiennichols.omniremote

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import com.intellij.openapi.diagnostic.Logger
import java.awt.BorderLayout
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.JTextArea

class OmniRemoteToolWindowFactory : ToolWindowFactory {
    private val log = Logger.getInstance(OmniRemoteToolWindowFactory::class.java)

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val content = try {
            val panel = OmniRemotePanel(project)
            ContentFactory.getInstance().createContent(panel, "", false)
        } catch (e: Exception) {
            log.error("Omni Remote failed to initialize.", e)
            val errorPanel = JPanel(BorderLayout())
            val errorText = JTextArea().apply {
                isEditable = false
                text = "Omni Remote failed to initialize.\n\n" +
                    (e.message ?: e.javaClass.simpleName)
            }
            errorPanel.add(JScrollPane(errorText), BorderLayout.CENTER)
            ContentFactory.getInstance().createContent(errorPanel, "Error", false)
        }
        toolWindow.contentManager.addContent(content)
    }
}
