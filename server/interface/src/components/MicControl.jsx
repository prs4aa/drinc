import React, { useState, useEffect, useRef } from "react";
import { startMic, stopMic } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Mic, MicOff, Volume2, VolumeX, Activity } from "lucide-react";

export default function MicControl({ status, onRefresh }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [listeningAudio, setListeningAudio] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const audioCtxRef = useRef(null);
  const wsRef = useRef(null);
  const nextPlayTimeRef = useRef(0);
  const canvasRef = useRef(null);
  const audioLevelRef = useRef(0);
  const animFrameRef = useRef(null);
  const phaseRef = useRef(0);

  const isTransmitting = !!status?.mic_active;

  const stopAudioListening = () => {
    if (wsRef.current) {
      try {
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
      } catch (e) {}
      wsRef.current = null;
    }
    if (audioCtxRef.current) {
      try {
        audioCtxRef.current.close();
      } catch (e) {}
      audioCtxRef.current = null;
    }
    nextPlayTimeRef.current = 0;
    setListeningAudio(false);
    audioLevelRef.current = 0;
  };

  const startAudioListening = () => {
    stopAudioListening();
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx({ sampleRate: 16000 });
      audioCtxRef.current = ctx;
      nextPlayTimeRef.current = ctx.currentTime;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/audio`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      ws.onmessage = (event) => {
        if (!(event.data instanceof ArrayBuffer)) return;
        const int16 = new Int16Array(event.data);
        if (int16.length === 0) return;

        let sum = 0;
        const step = Math.max(1, Math.floor(int16.length / 32));
        let count = 0;
        for (let i = 0; i < int16.length; i += step) {
          sum += Math.abs(int16[i]);
          count++;
        }
        const avg = count > 0 ? sum / count : 0;
        const targetLevel = Math.min(1, avg / 8000);
        audioLevelRef.current = audioLevelRef.current * 0.3 + targetLevel * 0.7;

        if (audioCtxRef.current) {
          const currentCtx = audioCtxRef.current;
          const float32 = new Float32Array(int16.length);
          for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768.0;
          }

          const buffer = currentCtx.createBuffer(1, float32.length, 16000);
          buffer.copyToChannel(float32, 0);

          const source = currentCtx.createBufferSource();
          source.buffer = buffer;
          source.connect(currentCtx.destination);
          source.onended = () => {
            try {
              source.disconnect();
            } catch (err) {}
          };

          const startTime = Math.max(currentCtx.currentTime, nextPlayTimeRef.current);
          source.start(startTime);
          nextPlayTimeRef.current = startTime + buffer.duration;
        }
      };

      ws.onerror = () => {
        stopAudioListening();
      };

      ws.onclose = () => {
        stopAudioListening();
      };

      wsRef.current = ws;
      setListeningAudio(true);
    } catch (e) {
      stopAudioListening();
    }
  };

  useEffect(() => {
    let interval = null;
    if (status?.mic_active) {
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedSeconds(0);
      if (listeningAudio) {
        stopAudioListening();
      }
      audioLevelRef.current = 0;
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [status?.mic_active]);

  useEffect(() => {
    return () => {
      stopAudioListening();
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let currentAnimLevel = 0;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      const midY = height / 2;

      ctx.clearRect(0, 0, width, height);

      if (!isTransmitting) {
        ctx.beginPath();
        ctx.strokeStyle = "rgba(16, 185, 129, 0.18)";
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 0;
        ctx.moveTo(0, midY);
        ctx.lineTo(width, midY);
        ctx.stroke();
        return;
      }

      currentAnimLevel = currentAnimLevel * 0.85 + audioLevelRef.current * 0.15;
      audioLevelRef.current *= 0.95;

      const baseAmp = 4;
      const dynamicAmp = baseAmp + currentAnimLevel * (height * 0.38);

      phaseRef.current += 0.08 + currentAnimLevel * 0.15;
      const phase = phaseRef.current;

      ctx.beginPath();
      ctx.strokeStyle = "rgba(16, 185, 129, 0.25)";
      ctx.lineWidth = 4;
      ctx.shadowColor = "rgba(52, 211, 153, 0.4)";
      ctx.shadowBlur = 10;

      const points = 48;
      const step = width / (points - 1);

      for (let i = 0; i < points; i++) {
        const x = i * step;
        const normalizedX = (i / points) * Math.PI * 4;
        const taper = Math.sin((i / (points - 1)) * Math.PI);
        const y =
          midY +
          (Math.sin(normalizedX * 1.5 + phase) * 0.55 +
            Math.sin(normalizedX * 3.2 - phase * 1.4) * 0.3 +
            Math.sin(normalizedX * 5.1 + phase * 2.1) * 0.15) *
            dynamicAmp *
            taper;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = "#34d399";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 8;

      for (let i = 0; i < points; i++) {
        const x = i * step;
        const normalizedX = (i / points) * Math.PI * 4;
        const taper = Math.sin((i / (points - 1)) * Math.PI);
        const y =
          midY +
          (Math.sin(normalizedX * 1.5 + phase) * 0.55 +
            Math.sin(normalizedX * 3.2 - phase * 1.4) * 0.3 +
            Math.sin(normalizedX * 5.1 + phase * 2.1) * 0.15) *
            dynamicAmp *
            taper;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      animFrameRef.current = requestAnimationFrame(render);
    };

    if (isTransmitting) {
      animFrameRef.current = requestAnimationFrame(render);
    } else {
      render();
    }

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [isTransmitting]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const updateSize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        canvas.width = rect.width * window.devicePixelRatio;
        canvas.height = rect.height * window.devicePixelRatio;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        }
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const formatTimer = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      await startMic();
      startAudioListening();
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopMic();
      stopAudioListening();
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border bg-surface flex flex-col h-full shadow-sm">
      <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
        <div className="flex items-center space-x-2 rtl:space-x-reverse">
          <div
            className={`p-1.5 rounded-md border transition-colors ${
              isTransmitting
                ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                : "bg-surface-elevated border-border text-dim"
            }`}
          >
            <Mic className="w-3.5 h-3.5" />
          </div>
          <div>
            <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
              {t("audio.title")}
            </CardTitle>
          </div>
        </div>

        <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
          <Badge
            variant={isTransmitting ? "destructive" : "secondary"}
            className="text-[9px] px-1.5 py-0 font-mono"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1 rtl:mr-0 rtl:ml-1 ${
                isTransmitting ? "bg-rose-400" : "bg-slate-500"
              }`}
            />
            {isTransmitting ? t("audio.live") : t("audio.standby")}
          </Badge>

          {isTransmitting && (
            <Badge variant={listeningAudio ? "success" : "secondary"} className="text-[9px] px-1.5 py-0 font-mono">
              {listeningAudio ? t("audio.audio_on") : t("audio.muted")}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
        <div className="rounded-xl bg-input border border-border overflow-hidden">
          <div className="p-3 pb-2 border-b border-border-muted/60 flex items-center justify-between">
            <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isTransmitting ? "bg-emerald-400 shadow-sm shadow-emerald-500/50" : "bg-zinc-600"
                }`}
              />
              <span className="text-[10px] uppercase font-mono tracking-wider text-dim">
                {isTransmitting ? t("audio.active_stream") : t("audio.recorder_standby")}
              </span>
            </div>

            <div className="flex items-center space-x-2 rtl:space-x-reverse">
              <span className="text-[10px] font-mono text-dim">
                {t("audio.pcm_spec")}
              </span>
              <span
                className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded border ${
                  isTransmitting
                    ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-400"
                    : "bg-surface border-border text-dim"
                }`}
              >
                {formatTimer(elapsedSeconds)}
              </span>
            </div>
          </div>

          <div className="relative p-2 px-3 bg-[#05080c] flex flex-col justify-center items-center h-20">
            <div className="absolute inset-0 flex flex-col justify-between p-2 pointer-events-none opacity-20">
              <div className="w-full border-b border-dashed border-emerald-900/60" />
              <div className="w-full border-b border-dashed border-emerald-900/60" />
              <div className="w-full border-b border-dashed border-emerald-900/60" />
            </div>

            <canvas
              ref={canvasRef}
              className="w-full h-full relative z-10 block"
              style={{ width: "100%", height: "100%" }}
            />
          </div>

          <div className="p-2 px-3 bg-surface/50 border-t border-border-muted/60 flex items-center justify-between text-[10px] font-mono text-dim">
            <div className="flex items-center space-x-1 rtl:space-x-reverse">
              <Activity className={`w-3 h-3 ${isTransmitting ? "text-emerald-400" : "text-zinc-600"}`} />
              <span>{isTransmitting ? "STREAM: ACTIVE (16kHz)" : "SIGNAL: IDLE"}</span>
            </div>
            <span>CH: MONO</span>
          </div>
        </div>

        <div className="space-y-2">
          {!isTransmitting ? (
            <Button
              variant="default"
              disabled={loading || !status?.client_connected}
              onClick={handleStart}
              className="w-full h-8 text-xs font-mono font-medium bg-rose-600 hover:bg-rose-500 text-white shadow-sm"
            >
              <Mic className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
              {t("audio.start_intercept")}
            </Button>
          ) : (
            <Button
              variant="destructive"
              disabled={loading}
              onClick={handleStop}
              className="w-full h-8 text-xs font-mono font-medium"
            >
              <MicOff className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
              {t("audio.stop_intercept")}
            </Button>
          )}

          {isTransmitting && (
            listeningAudio ? (
              <Button
                variant="outline"
                onClick={stopAudioListening}
                className="w-full h-8 text-xs font-mono text-amber-400 border-amber-500/30"
              >
                <VolumeX className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                {t("audio.mute_browser")}
              </Button>
            ) : (
              <Button
                variant="success"
                onClick={startAudioListening}
                className="w-full h-8 text-xs font-mono"
              >
                <Volume2 className="w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5" />
                {t("audio.monitor_browser")}
              </Button>
            )
          )}
        </div>
      </CardContent>
    </Card>
  );
}
