package com.drink

import org.json.JSONObject
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.Socket

class SocketManager(host: String, port: Int) {

    private val socket = Socket(host, port)
    private val input = DataInputStream(socket.getInputStream())
    private val output = DataOutputStream(socket.getOutputStream())

    fun sendFrame(json: JSONObject) {
        val bytes = json.toString().toByteArray(Charsets.UTF_8)
        output.writeInt(bytes.size)
        output.write(bytes)
        output.flush()
    }

    fun sendFrame(header: JSONObject, body: ByteArray) {
        val headerBytes = header.toString().toByteArray(Charsets.UTF_8)
        output.writeInt(headerBytes.size)
        output.write(headerBytes)
        output.writeInt(body.size)
        output.write(body)
        output.flush()
    }

    fun readFrame(): JSONObject {
        val length = input.readInt()
        val bytes = readBytes(length)
        return JSONObject(String(bytes, Charsets.UTF_8))
    }

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
