plugins {
    id("org.jetbrains.kotlin.jvm") version "1.9.25"
    id("org.jetbrains.intellij") version "1.17.4"
}

group = "com.damiennichols"
version = "0.1.0"

repositories {
    mavenCentral()
}

kotlin {
    jvmToolchain(17)
}

intellij {
    type.set("AI")
    version.set("2024.1.1.12")
    plugins.set(listOf())
}

dependencies {
    implementation("com.google.code.gson:gson:2.11.0")
}

tasks {
    patchPluginXml {
        sinceBuild.set("241")
        untilBuild.set("242.*")
    }

    buildSearchableOptions {
        enabled = false
    }
}
