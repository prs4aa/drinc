import React, { useState } from "react";
import { listCameras, captureCamera } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Camera, Download, RefreshCw, Eye } from "lucide-react";

export default function CameraManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [selectedCam, setSelectedCam] = useState("0");
  const [photoTimestamp, setPhotoTimestamp] = useState(Date.now());
  const [previewOpen, setPreviewOpen] = useState(false);

  const handleList = async () => {
    setLoading(true);
    try {
      await listCameras();
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const handleCapture = async () => {
    setLoading(true);
    try {
      await captureCamera(selectedCam);
      setPhotoTimestamp(Date.now());
      await onRefresh();
    } finally {
      setLoading(false);
    }
  };

  const cams = status?.cameras || [];

  React.useEffect(() => {
    if (status?.client_connected && cams.length === 0) {
      listCameras().then(onRefresh).catch(() => {});
    }
  }, [status?.client_connected, cams.length]);

  return (
    <Card className="border-border bg-surface shadow-sm h-full flex flex-col justify-between">
      <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
        <div className="flex items-center space-x-2 rtl:space-x-reverse">
          <div className="p-1.5 rounded-md bg-surface-elevated border border-border text-pink-400">
            <Camera className="w-3.5 h-3.5" />
          </div>
          <div>
            <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
              {t("camera.title")}
            </CardTitle>
          </div>
        </div>
        <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-mono">
          {cams.length > 0 ? `${cams.length} CAMS` : "STANDBY"}
        </Badge>
      </CardHeader>
      <CardContent className="p-3.5 space-y-3 flex-1 flex flex-col justify-between">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <Button
              size="sm"
              variant="outline"
              disabled={loading || !status?.client_connected}
              onClick={handleList}
              className="h-7 text-xs font-mono"
            >
              <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
              {t("camera.detect")}
            </Button>

            <select
              value={selectedCam}
              onChange={(e) => setSelectedCam(e.target.value)}
              className="bg-input text-main border border-border rounded-md px-2 py-1 text-xs font-mono outline-none"
            >
              {cams.length > 0 ? (
                cams.map((c, i) => {
                  const id = typeof c === "object" ? c.id || String(i) : String(c);
                  const name = typeof c === "object" ? c.name || `Cam ${id}` : `Cam ${id}`;
                  return (
                    <option key={id} value={id} className="bg-surface text-main">
                      {name}
                    </option>
                  );
                })
              ) : (
                <>
                  <option value="0" className="bg-surface text-main">{t("camera.cam_0")}</option>
                  <option value="1" className="bg-surface text-main">{t("camera.cam_1")}</option>
                </>
              )}
            </select>
          </div>

          <Button
            size="sm"
            variant="default"
            disabled={loading || !status?.client_connected}
            onClick={handleCapture}
            className="h-7 px-3 text-xs font-mono font-medium bg-pink-600 hover:bg-pink-500 text-white whitespace-nowrap flex-shrink-0"
          >
            <Camera className={`w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5 ${loading ? "animate-spin" : ""}`} />
            {t("camera.capture")}
          </Button>
        </div>

        {status?.has_photo ? (
          <div className="space-y-2 pt-1 flex-1 flex flex-col justify-end">
            <div className="flex items-center justify-between text-[11px] font-mono text-dim">
              <span className="text-emerald-400">SNAPSHOT READY</span>
              <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setPreviewOpen(true)}
                  className="h-6 px-2 text-[10px] font-mono"
                >
                  <Eye className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1" />
                  VIEW
                </Button>
                <a
                  href={`/api/photo/latest?t=${photoTimestamp}`}
                  download={`capture_${selectedCam}_${photoTimestamp}.jpg`}
                >
                  <Button size="sm" variant="outline" className="h-6 px-2 text-[10px] font-mono">
                    <Download className="w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1" />
                    {t("camera.download")}
                  </Button>
                </a>
              </div>
            </div>

            <div
              onClick={() => setPreviewOpen(true)}
              className="rounded-xl overflow-hidden border border-border bg-[#05080c] relative cursor-pointer group h-40 flex items-center justify-center"
            >
              <img
                src={`/api/photo/latest?t=${photoTimestamp}`}
                alt="Latest capture"
                className="max-h-40 w-full object-contain mx-auto transition-transform duration-200 group-hover:scale-[1.01]"
              />
            </div>
          </div>
        ) : (
          <div className="h-40 rounded-xl bg-input border border-border flex flex-col items-center justify-center text-center p-4 text-xs font-mono text-dim">
            <Camera className="w-7 h-7 mb-1.5 text-dim/30" />
            <p>{t("camera.no_photo")}</p>
          </div>
        )}

        {previewOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm"
            onClick={() => setPreviewOpen(false)}
          >
            <div className="relative max-w-4xl max-h-[90vh] bg-surface border border-border rounded-2xl overflow-hidden p-2">
              <img
                src={`/api/photo/latest?t=${photoTimestamp}`}
                alt="Full resolution capture"
                className="max-w-full max-h-[80vh] object-contain mx-auto rounded-lg"
              />
              <div className="p-2 flex items-center justify-between text-xs font-mono text-dim">
                <span>Capture: Cam {selectedCam}</span>
                <a
                  href={`/api/photo/latest?t=${photoTimestamp}`}
                  download={`capture_${selectedCam}_${photoTimestamp}.jpg`}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button size="sm" variant="outline" className="h-7 text-xs font-mono">
                    <Download className="w-3 h-3 mr-1" />
                    {t("camera.download")}
                  </Button>
                </a>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
