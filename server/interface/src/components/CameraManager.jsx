import React, { useState } from "react";
import { listCameras, captureCamera } from "../api/client";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Camera, Download, RefreshCw } from "lucide-react";

export default function CameraManager({ status, onRefresh }) {
  const [loading, setLoading] = useState(false);
  const [selectedCam, setSelectedCam] = useState("0");
  const [photoTimestamp, setPhotoTimestamp] = useState(Date.now());

  if (!status?.camera_enabled) {
    return null;
  }

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

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-pink-500/10 border border-pink-500/20 text-pink-400">
            <Camera className="w-4 h-4" />
          </div>
          <div>
            <CardTitle>Camera Snapshot</CardTitle>
            <p className="text-xs text-slate-400 mt-0.5">Remote hardware camera capture</p>
          </div>
        </div>
        <Badge variant="secondary">Feature Enabled</Badge>
      </CardHeader>
      <CardContent className="space-y-3 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={loading || !status?.client_connected}
            onClick={handleList}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Detect Cameras
          </Button>

          <select
            value={selectedCam}
            onChange={(e) => setSelectedCam(e.target.value)}
            className="bg-background/80 text-slate-200 border border-border/60 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none"
          >
            {cams.length > 0 ? (
              cams.map((c, i) => {
                const id = typeof c === "object" ? c.id || String(i) : String(c);
                const name = typeof c === "object" ? c.facing || c.name || `Cam ${id}` : `Cam ${id}`;
                return (
                  <option key={id} value={id}>
                    {name} ({id})
                  </option>
                );
              })
            ) : (
              <>
                <option value="0">Camera 0 (Back)</option>
                <option value="1">Camera 1 (Front)</option>
              </>
            )}
          </select>

          <Button
            size="sm"
            variant="default"
            disabled={loading || !status?.client_connected}
            onClick={handleCapture}
          >
            <Camera className="w-3.5 h-3.5 mr-1.5" />
            Capture Photo
          </Button>
        </div>

        {status?.has_photo && (
          <div className="space-y-2 pt-2">
            <div className="flex justify-end">
              <a
                href={`/api/photo/latest?t=${photoTimestamp}`}
                download="photo.jpg"
              >
                <Button size="sm" variant="outline">
                  <Download className="w-3.5 h-3.5 mr-1" />
                  Download Full Res
                </Button>
              </a>
            </div>
            <div className="rounded-xl overflow-hidden border border-border/60 bg-black/40">
              <img
                src={`/api/photo/latest?t=${photoTimestamp}`}
                alt="Latest capture"
                className="max-h-[350px] w-auto mx-auto object-contain"
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
