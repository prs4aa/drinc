package com.drink

import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.InetSocketAddress
import java.net.Socket

class SocketManager(host: String, port: Int, timeoutMs: Int = 10000) {

    private val socket = Socket().apply {
        tcpNoDelay = true
        keepAlive = true
        connect(InetSocketAddress(host, port), timeoutMs)
    }
    private val input = DataInputStream(socket.getInputStream())
    private val output = DataOutputStream(socket.getOutputStream())

    @Synchronized
    fun sendFrame(json: JSONObject) {
        val bytes = json.toString().toByteArray(Charsets.UTF_8)
        output.writeInt(bytes.size)
        output.write(bytes)
        output.flush()
    }

    @Synchronized
    fun sendFrame(header: JSONObject, body: ByteArray) {
        val headerBytes = header.toString().toByteArray(Charsets.UTF_8)
        output.writeInt(headerBytes.size)
        output.write(headerBytes)
        output.writeInt(body.size)
        output.write(body)
        output.flush()
    }

    @Synchronized
    fun readFrame(): JSONObject {
        val length = input.readInt()
        val bytes = readBytes(length)
        return JSONObject(String(bytes, Charsets.UTF_8))
    }

    @Synchronized
    fun readBytes(n: Int): ByteArray {
        val buffer = ByteArray(n)
        var offset = 0
        while (offset < n) {
            val read = input.read(buffer, offset, n - offset)
            if (read == -1) throw java.io.EOFException("Connection closed")
            offset += read
        }
        return buffer
    }

    fun close() {
        runCatching { socket.close() }
    }

    fun isConnected() = socket.isConnected && !socket.isClosed
}
