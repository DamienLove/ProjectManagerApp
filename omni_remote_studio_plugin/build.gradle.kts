plugins {
    id("org.jetbrains.kotlin.jvm") version "1.9.25"
    id("org.jetbrains.intellij") version "1.17.4"
}

group = "com.damiennichols"
version = "4.4.0"

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
    implementation("io.javalin:javalin:6.1.3")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.17.0")
    implementation("org.slf4j:slf4j-simple:2.0.12")
    implementation("com.google.firebase:firebase-admin:9.2.0")
    implementation("io.ktor:ktor-server-core:2.3.12")
    implementation("io.ktor:ktor-server-netty:2.3.12")
    implementation("io.ktor:ktor-server-websockets:2.3.12")
    implementation("io.ktor:ktor-server-content-negotiation:2.3.12")
    implementation("io.ktor:ktor-serialization-gson:2.3.12")
}

tasks {
    patchPluginXml {
        sinceBuild.set("241")
        untilBuild.set("261.*")
    }

    buildSearchableOptions {
        enabled = false
    }
}
