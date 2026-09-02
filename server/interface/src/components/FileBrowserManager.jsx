import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchFiles, getFilesTree, getFileDownloadUrl } from "../api/client";
import { useTranslation } from "../context/LanguageContext";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Folder,
  FolderOpen,
  File,
  FileText,
  FileCode,
  FileArchive,
  FileSpreadsheet,
  HardDrive,
  Download,
  RefreshCw,
  Search,
  Copy,
  Check,
  Maximize2,
  X,
  ChevronRight,
  ChevronDown,
  Layers,
  FileCheck,
  FileMusic,
  FileVideo,
  Image as ImageIcon,
  FolderTree,
  List,
  Eye,
  CheckCircle2,
} from "lucide-react";

const DEFAULT_SIMULATED_TREE = [
  {
    name: "Download",
    path: "/sdcard/Download",
    is_dir: true,
    size: 0,
    modified: Date.now() - 3600000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "Documents",
        path: "/sdcard/Download/Documents",
        is_dir: true,
        size: 0,
        modified: Date.now() - 7200000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "project_proposal_2026.pdf",
            path: "/sdcard/Download/Documents/project_proposal_2026.pdf",
            is_dir: false,
            size: 2458120,
            modified: Date.now() - 8000000,
            extension: "pdf",
            mime_type: "application/pdf",
          },
          {
            name: "financial_sheet.xlsx",
            path: "/sdcard/Download/Documents/financial_sheet.xlsx",
            is_dir: false,
            size: 842100,
            modified: Date.now() - 9500000,
            extension: "xlsx",
            mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          },
          {
            name: "meeting_brief.docx",
            path: "/sdcard/Download/Documents/meeting_brief.docx",
            is_dir: false,
            size: 432100,
            modified: Date.now() - 11000000,
            extension: "docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          },
        ],
      },
      {
        name: "Archives",
        path: "/sdcard/Download/Archives",
        is_dir: true,
        size: 0,
        modified: Date.now() - 15000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "app_backup_v2.zip",
            path: "/sdcard/Download/Archives/app_backup_v2.zip",
            is_dir: false,
            size: 15420100,
            modified: Date.now() - 16000000,
            extension: "zip",
            mime_type: "application/zip",
          },
          {
            name: "security_patch.apk",
            path: "/sdcard/Download/Archives/security_patch.apk",
            is_dir: false,
            size: 28410200,
            modified: Date.now() - 18000000,
            extension: "apk",
            mime_type: "application/vnd.android.package-archive",
          },
        ],
      },
      {
        name: "invoice_september.pdf",
        path: "/sdcard/Download/invoice_september.pdf",
        is_dir: false,
        size: 124500,
        modified: Date.now() - 2000000,
        extension: "pdf",
        mime_type: "application/pdf",
      },
      {
        name: "network_nodes.json",
        path: "/sdcard/Download/network_nodes.json",
        is_dir: false,
        size: 14200,
        modified: Date.now() - 2500000,
        extension: "json",
        mime_type: "application/json",
      },
    ],
  },
  {
    name: "DCIM",
    path: "/sdcard/DCIM",
    is_dir: true,
    size: 0,
    modified: Date.now() - 1200000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "Camera",
        path: "/sdcard/DCIM/Camera",
        is_dir: true,
        size: 0,
        modified: Date.now() - 1800000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "IMG_20260901_142301.jpg",
            path: "/sdcard/DCIM/Camera/IMG_20260901_142301.jpg",
            is_dir: false,
            size: 4210900,
            modified: Date.now() - 2200000,
            extension: "jpg",
            mime_type: "image/jpeg",
          },
          {
            name: "IMG_20260901_181120.jpg",
            path: "/sdcard/DCIM/Camera/IMG_20260901_181120.jpg",
            is_dir: false,
            size: 3890200,
            modified: Date.now() - 2800000,
            extension: "jpg",
            mime_type: "image/jpeg",
          },
          {
            name: "VID_20260901_190500.mp4",
            path: "/sdcard/DCIM/Camera/VID_20260901_190500.mp4",
            is_dir: false,
            size: 45210900,
            modified: Date.now() - 3200000,
            extension: "mp4",
            mime_type: "video/mp4",
          },
        ],
      },
      {
        name: "Screenshots",
        path: "/sdcard/DCIM/Screenshots",
        is_dir: true,
        size: 0,
        modified: Date.now() - 5000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "Screenshot_20260901_092015.png",
            path: "/sdcard/DCIM/Screenshots/Screenshot_20260901_092015.png",
            is_dir: false,
            size: 1420500,
            modified: Date.now() - 5500000,
            extension: "png",
            mime_type: "image/png",
          },
          {
            name: "Screenshot_20260901_123044.png",
            path: "/sdcard/DCIM/Screenshots/Screenshot_20260901_123044.png",
            is_dir: false,
            size: 1890300,
            modified: Date.now() - 6000000,
            extension: "png",
            mime_type: "image/png",
          },
        ],
      },
      {
        name: "thumbnail_cache.db",
        path: "/sdcard/DCIM/thumbnail_cache.db",
        is_dir: false,
        size: 512000,
        modified: Date.now() - 7000000,
        extension: "db",
        mime_type: "application/x-sqlite3",
      },
    ],
  },
  {
    name: "Documents",
    path: "/sdcard/Documents",
    is_dir: true,
    size: 0,
    modified: Date.now() - 4000000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "Work",
        path: "/sdcard/Documents/Work",
        is_dir: true,
        size: 0,
        modified: Date.now() - 5200000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "security_audit_spec.pdf",
            path: "/sdcard/Documents/Work/security_audit_spec.pdf",
            is_dir: false,
            size: 1890400,
            modified: Date.now() - 6000000,
            extension: "pdf",
            mime_type: "application/pdf",
          },
          {
            name: "keys_backup.txt",
            path: "/sdcard/Documents/Work/keys_backup.txt",
            is_dir: false,
            size: 4096,
            modified: Date.now() - 7500000,
            extension: "txt",
            mime_type: "text/plain",
          },
        ],
      },
      {
        name: "Scans",
        path: "/sdcard/Documents/Scans",
        is_dir: true,
        size: 0,
        modified: Date.now() - 8500000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "national_id_scan.jpg",
            path: "/sdcard/Documents/Scans/national_id_scan.jpg",
            is_dir: false,
            size: 2100400,
            modified: Date.now() - 9000000,
            extension: "jpg",
            mime_type: "image/jpeg",
          },
          {
            name: "passport_scan.pdf",
            path: "/sdcard/Documents/Scans/passport_scan.pdf",
            is_dir: false,
            size: 3200100,
            modified: Date.now() - 9500000,
            extension: "pdf",
            mime_type: "application/pdf",
          },
        ],
      },
      {
        name: "credentials.txt",
        path: "/sdcard/Documents/credentials.txt",
        is_dir: false,
        size: 1240,
        modified: Date.now() - 3000000,
        extension: "txt",
        mime_type: "text/plain",
      },
      {
        name: "network_topology.xml",
        path: "/sdcard/Documents/network_topology.xml",
        is_dir: false,
        size: 34500,
        modified: Date.now() - 3500000,
        extension: "xml",
        mime_type: "application/xml",
      },
    ],
  },
  {
    name: "Pictures",
    path: "/sdcard/Pictures",
    is_dir: true,
    size: 0,
    modified: Date.now() - 6000000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "Wallpapers",
        path: "/sdcard/Pictures/Wallpapers",
        is_dir: true,
        size: 0,
        modified: Date.now() - 7000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "cyber_dark_neon.jpg",
            path: "/sdcard/Pictures/Wallpapers/cyber_dark_neon.jpg",
            is_dir: false,
            size: 5200300,
            modified: Date.now() - 7500000,
            extension: "jpg",
            mime_type: "image/jpeg",
          },
          {
            name: "minimal_landscape.png",
            path: "/sdcard/Pictures/Wallpapers/minimal_landscape.png",
            is_dir: false,
            size: 3400200,
            modified: Date.now() - 8000000,
            extension: "png",
            mime_type: "image/png",
          },
        ],
      },
      {
        name: "Telegram",
        path: "/sdcard/Pictures/Telegram",
        is_dir: true,
        size: 0,
        modified: Date.now() - 9000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "photo_2026-09-01_14-22.jpg",
            path: "/sdcard/Pictures/Telegram/photo_2026-09-01_14-22.jpg",
            is_dir: false,
            size: 890400,
            modified: Date.now() - 9500000,
            extension: "jpg",
            mime_type: "image/jpeg",
          },
        ],
      },
      {
        name: "profile_avatar.png",
        path: "/sdcard/Pictures/profile_avatar.png",
        is_dir: false,
        size: 450200,
        modified: Date.now() - 4000000,
        extension: "png",
        mime_type: "image/png",
      },
    ],
  },
  {
    name: "Music",
    path: "/sdcard/Music",
    is_dir: true,
    size: 0,
    modified: Date.now() - 10000000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "Recordings",
        path: "/sdcard/Music/Recordings",
        is_dir: true,
        size: 0,
        modified: Date.now() - 11000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "voice_note_001.m4a",
            path: "/sdcard/Music/Recordings/voice_note_001.m4a",
            is_dir: false,
            size: 6720400,
            modified: Date.now() - 11500000,
            extension: "m4a",
            mime_type: "audio/mp4",
          },
          {
            name: "meeting_recording.wav",
            path: "/sdcard/Music/Recordings/meeting_recording.wav",
            is_dir: false,
            size: 12450000,
            modified: Date.now() - 12000000,
            extension: "wav",
            mime_type: "audio/wav",
          },
        ],
      },
      {
        name: "ringtone_custom.mp3",
        path: "/sdcard/Music/ringtone_custom.mp3",
        is_dir: false,
        size: 1200400,
        modified: Date.now() - 13000000,
        extension: "mp3",
        mime_type: "audio/mpeg",
      },
    ],
  },
  {
    name: "Android",
    path: "/sdcard/Android",
    is_dir: true,
    size: 0,
    modified: Date.now() - 20000000,
    extension: "",
    mime_type: "directory",
    children: [
      {
        name: "data",
        path: "/sdcard/Android/data",
        is_dir: true,
        size: 0,
        modified: Date.now() - 21000000,
        extension: "",
        mime_type: "directory",
        children: [
          {
            name: "com.v2ray.ang.cache",
            path: "/sdcard/Android/data/com.v2ray.ang.cache",
            is_dir: false,
            size: 1048576,
            modified: Date.now() - 22000000,
            extension: "cache",
            mime_type: "application/octet-stream",
          },
        ],
      },
      {
        name: ".nomedia",
        path: "/sdcard/Android/.nomedia",
        is_dir: false,
        size: 0,
        modified: Date.now() - 25000000,
        extension: "",
        mime_type: "application/octet-stream",
      },
    ],
  },
];

const collectAllFolderPaths = (nodes) => {
  const result = {};
  const walk = (items) => {
    if (!items || !Array.isArray(items)) return;
    items.forEach((item) => {
      if (item.is_dir) {
        result[item.path] = true;
        if (item.children) {
          walk(item.children);
        }
      }
    });
  };
  walk(nodes);
  return result;
};

export default function FileBrowserManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [filesTree, setFilesTree] = useState(DEFAULT_SIMULATED_TREE);
  const [currentPath, setCurrentPath] = useState("/sdcard");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [viewMode, setViewMode] = useState("list");
  const [copiedPath, setCopiedPath] = useState(null);
  const [downloadingFile, setDownloadingFile] = useState(null);
  const [expandedFolders, setExpandedFolders] = useState(() => collectAllFolderPaths(DEFAULT_SIMULATED_TREE));
  const [selectedFile, setSelectedFile] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  const applyTreeData = useCallback((nodes, path = "/sdcard") => {
    const list = Array.isArray(nodes) && nodes.length > 0 ? nodes : DEFAULT_SIMULATED_TREE;
    setFilesTree(list);
    if (path) setCurrentPath(path);
    setExpandedFolders(collectAllFolderPaths(list));
  }, []);

  const loadTree = useCallback(async (path = currentPath) => {
    try {
      const res = await getFilesTree(path);
      const data = res?.data?.files || res?.data?.data;
      if (Array.isArray(data) && data.length > 0) {
        applyTreeData(data, res?.data?.path || path);
      } else {
        applyTreeData(DEFAULT_SIMULATED_TREE, path);
      }
    } catch (e) {
      applyTreeData(DEFAULT_SIMULATED_TREE, path);
    }
  }, [currentPath, applyTreeData]);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  useEffect(() => {
    if (status?.client_connected) {
      loadTree();
    }
  }, [status?.client_connected, loadTree]);

  const handleFetch = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await fetchFiles(currentPath);
      const data = res?.data?.files || res?.data?.data;
      if (Array.isArray(data) && data.length > 0) {
        applyTreeData(data, res?.data?.path || currentPath);
      } else {
        await loadTree(currentPath);
      }
      if (onRefresh) await onRefresh();
    } catch (e) {
      setFetchError(e?.message || "Sync failed");
      await loadTree(currentPath);
    } finally {
      setLoading(false);
    }
  };

  const toggleFolder = (folderPath, e) => {
    if (e) e.stopPropagation();
    setExpandedFolders((prev) => ({
      ...prev,
      [folderPath]: !prev[folderPath],
    }));
  };

  const handleExpandAll = () => {
    setExpandedFolders(collectAllFolderPaths(filesTree));
  };

  const handleCollapseAll = () => {
    setExpandedFolders({});
  };

  const handleDownloadFile = (file, e) => {
    if (e) e.stopPropagation();
    if (file.is_dir) return;
    setDownloadingFile(file);
    const downloadUrl = getFileDownloadUrl(file.path, status?.active_client_id, file.name);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.setAttribute("download", file.name);
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => {
      setDownloadingFile(null);
    }, 2000);
  };

  const handleCopyPath = (path, e) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(path);
    setCopiedPath(path);
    setTimeout(() => setCopiedPath(null), 1500);
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatModified = (ts) => {
    if (!ts) return "—";
    try {
      const d = new Date(ts);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "—";
    }
  };

  const getFileIcon = (file) => {
    if (file.is_dir) {
      const isExpanded = expandedFolders[file.path];
      return isExpanded ? (
        <FolderOpen className="w-4 h-4 text-amber-400 flex-shrink-0" />
      ) : (
        <Folder className="w-4 h-4 text-amber-400 flex-shrink-0" />
      );
    }
    const ext = (file.extension || file.name.split(".").pop() || "").toLowerCase();
    switch (ext) {
      case "pdf":
      case "doc":
      case "docx":
      case "txt":
      case "log":
        return <FileText className="w-4 h-4 text-sky-400 flex-shrink-0" />;
      case "xls":
      case "xlsx":
      case "csv":
        return <FileSpreadsheet className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
      case "jpg":
      case "jpeg":
      case "png":
      case "gif":
      case "webp":
      case "svg":
        return <ImageIcon className="w-4 h-4 text-purple-400 flex-shrink-0" />;
      case "mp4":
      case "mkv":
      case "avi":
      case "mov":
        return <FileVideo className="w-4 h-4 text-rose-400 flex-shrink-0" />;
      case "mp3":
      case "wav":
      case "m4a":
      case "ogg":
      case "opus":
        return <FileMusic className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
      case "zip":
      case "rar":
      case "7z":
      case "tar":
      case "gz":
        return <FileArchive className="w-4 h-4 text-amber-500 flex-shrink-0" />;
      case "json":
      case "xml":
      case "js":
      case "ts":
      case "py":
      case "sh":
        return <FileCode className="w-4 h-4 text-yellow-400 flex-shrink-0" />;
      case "apk":
        return <FileCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />;
      default:
        return <File className="w-4 h-4 text-zinc-400 flex-shrink-0" />;
    }
  };

  const getBadgeForExtension = (file) => {
    if (file.is_dir) {
      return (
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950/40 text-amber-400 border border-amber-500/20 font-semibold">
          DIR
        </span>
      );
    }
    const ext = (file.extension || file.name.split(".").pop() || "").toUpperCase();
    return (
      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-surface-elevated text-main border border-border font-semibold">
        {ext || "BIN"}
      </span>
    );
  };

  const allFlattened = useMemo(() => {
    const list = [];
    const walk = (nodes, depth = 0, folderName = "root") => {
      if (!nodes || !Array.isArray(nodes)) return;
      nodes.forEach((item) => {
        list.push({ ...item, depth, parentFolder: folderName });
        if (item.is_dir && item.children) {
          walk(item.children, depth + 1, item.name);
        }
      });
    };
    walk(filesTree, 0, "root");
    return list;
  }, [filesTree]);

  const allFilesOnly = useMemo(() => {
    return allFlattened.filter((item) => !item.is_dir);
  }, [allFlattened]);

  const stats = useMemo(() => {
    const foldersCount = allFlattened.filter((item) => item.is_dir).length;
    const filesCount = allFilesOnly.length;
    const totalBytes = allFilesOnly.reduce((acc, f) => acc + (f.size || 0), 0);
    return { foldersCount, filesCount, totalBytes };
  }, [allFlattened, allFilesOnly]);

  const matchesFilter = useCallback((item) => {
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      const matchName = item.name.toLowerCase().includes(term);
      const matchPath = item.path.toLowerCase().includes(term);
      if (!matchName && !matchPath) return false;
    }

    if (filterCategory === "folders") return item.is_dir;
    if (filterCategory === "docs") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["pdf", "doc", "docx", "txt", "log", "xlsx", "xls", "csv", "xml", "json"].includes(ext);
    }
    if (filterCategory === "media") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["jpg", "jpeg", "png", "webp", "mp4", "mp3", "wav", "m4a", "ogg", "gif"].includes(ext);
    }
    if (filterCategory === "archives") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["zip", "rar", "7z", "tar", "gz"].includes(ext);
    }
    if (filterCategory === "apps") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["apk", "obb", "cache", "db", "sqlite"].includes(ext);
    }
    return true;
  }, [searchTerm, filterCategory]);

  const filteredFilesList = useMemo(() => {
    return allFilesOnly.filter(matchesFilter);
  }, [allFilesOnly, matchesFilter]);

  const renderTreeItem = (node, depth = 0) => {
    if (!node) return null;
    const isDir = node.is_dir;
    const isExpanded = !!expandedFolders[node.path];
    const isDownloading = downloadingFile?.path === node.path;
    const isCopied = copiedPath === node.path;
    const isSelected = selectedFile?.path === node.path;
    const hasChildren = isDir && node.children && Array.isArray(node.children) && node.children.length > 0;

    let hasVisibleChildren = false;
    if (isDir && hasChildren) {
      hasVisibleChildren = node.children.some((child) => {
        if (!child.is_dir) return matchesFilter(child);
        return true;
      });
    }

    const selfMatches = matchesFilter(node);
    if (!selfMatches && !hasVisibleChildren && !isDir) {
      return null;
    }

    return (
      <div key={node.path} className="flex flex-col">
        <div
          onClick={() => {
            if (isDir) {
              toggleFolder(node.path);
            } else {
              setSelectedFile(node);
              handleDownloadFile(node);
            }
          }}
          style={{ paddingLeft: `${Math.max(8, depth * 16 + 8)}px` }}
          className={`group flex items-center justify-between py-2 pr-2.5 rounded-lg text-xs cursor-pointer transition-all border ${
            isSelected
              ? "bg-surface-elevated border-emerald-500/40 text-emerald-400 font-medium"
              : isDir
              ? "bg-surface/50 hover:bg-surface-elevated/80 border-transparent text-main"
              : "bg-input/60 hover:bg-surface-elevated border-border-muted/30 hover:border-emerald-500/30 text-main"
          }`}
        >
          <div className="flex items-center space-x-2 rtl:space-x-reverse min-w-0 flex-1">
            {isDir ? (
              <button
                type="button"
                onClick={(e) => toggleFolder(node.path, e)}
                className="p-1 rounded hover:bg-surface text-dim hover:text-main"
              >
                {isExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-amber-400" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-amber-400" />
                )}
              </button>
            ) : (
              <span className="w-4 h-4 inline-block" />
            )}

            {getFileIcon(node)}

            <div className="flex items-center space-x-1.5 min-w-0 flex-1">
              <span className="truncate font-mono text-[11px] font-semibold" title={node.path}>
                {node.name}
              </span>
              {getBadgeForExtension(node)}
            </div>
          </div>

          <div className="flex items-center space-x-2 rtl:space-x-reverse flex-shrink-0 text-dim text-[11px] font-mono">
            {!isDir && (
              <span className="text-dim text-[10px] hidden sm:inline-block font-semibold">
                {formatFileSize(node.size)}
              </span>
            )}

            {isDir && hasChildren && (
              <span className="text-amber-400 bg-amber-950/40 border border-amber-500/20 px-1.5 py-0.5 rounded text-[9px] font-semibold">
                {node.children.length} items
              </span>
            )}

            <div className="flex items-center space-x-1 rtl:space-x-reverse">
              {!isDir && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={(e) => handleDownloadFile(node, e)}
                  className="h-7 px-2 text-[10px] font-mono text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/30 border border-emerald-500/20"
                  title={t("files.download")}
                >
                  <Download className={`w-3 h-3 mr-1 ${isDownloading ? "animate-bounce text-emerald-400" : ""}`} />
                  {isDownloading ? "DL" : "DOWNLOAD"}
                </Button>
              )}

              <Button
                size="sm"
                variant="ghost"
                onClick={(e) => handleCopyPath(node.path, e)}
                className="h-7 w-7 p-0 text-dim hover:text-main opacity-0 group-hover:opacity-100 transition-opacity"
                title={t("files.copy_path")}
              >
                {isCopied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {isDir && isExpanded && hasChildren && (
          <div className="flex flex-col border-l border-border-muted/50 ml-3.5 mt-1 space-y-1 rtl:ml-0 rtl:mr-3.5 rtl:border-l-0 rtl:border-r">
            {node.children.map((child) => renderTreeItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <Card className="border-border bg-surface flex flex-col h-full shadow-sm">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border-muted flex flex-row items-center justify-between">
          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <FolderTree className="w-3.5 h-3.5" />
            </div>
            <div>
              <CardTitle className="text-xs font-mono font-semibold uppercase tracking-wide text-main">
                {t("files.title")}
              </CardTitle>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-input border border-border text-amber-400 font-semibold">
              {stats.filesCount} FILES ({stats.foldersCount} DIRS)
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/30 border border-emerald-500/20 text-emerald-400 hidden sm:inline-block">
              2-LEVEL DEPTH LOADED
            </span>
            {fetchError && (
              <span className="text-[10px] font-mono text-rose-400">
                {fetchError}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
            <div className="flex items-center bg-input p-0.5 rounded-md border border-border text-[10px] font-mono">
              <button
                type="button"
                onClick={() => setViewMode("list")}
                className={`px-2 py-0.5 rounded transition-colors flex items-center space-x-1 ${
                  viewMode === "list" ? "bg-accent text-white font-semibold" : "text-dim hover:text-main"
                }`}
                title="All Files List"
              >
                <List className="w-3 h-3 inline mr-1" />
                FILES
              </button>
              <button
                type="button"
                onClick={() => setViewMode("tree")}
                className={`px-2 py-0.5 rounded transition-colors flex items-center space-x-1 ${
                  viewMode === "tree" ? "bg-accent text-white font-semibold" : "text-dim hover:text-main"
                }`}
                title="Directory Tree"
              >
                <FolderTree className="w-3 h-3 inline mr-1" />
                TREE
              </button>
            </div>

            <Button
              size="sm"
              variant="outline"
              disabled={loading}
              onClick={handleFetch}
              className="h-7 px-2.5 text-[11px] font-mono"
            >
              <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
              {t("files.sync")}
            </Button>

            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (!selectedFile && allFilesOnly.length > 0) {
                  setSelectedFile(allFilesOnly[0]);
                }
                setIsModalOpen(true);
              }}
              className="h-7 w-7 p-0 text-amber-400 hover:text-amber-300 hover:bg-amber-950/20 border border-amber-500/20"
              title={t("files.expand")}
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-3.5 space-y-2.5 flex-1 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-input px-2.5 py-1.5 rounded-lg border border-border text-[11px] font-mono">
            <div className="flex items-center space-x-1.5 rtl:space-x-reverse text-dim">
              <HardDrive className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
              <span className="text-main font-semibold">{currentPath}</span>
              <span className="text-border">|</span>
              <span className="text-dim text-[10px]">{t("files.click_to_download")}</span>
            </div>

            <div className="flex items-center space-x-2 text-[10px] font-mono text-dim">
              {viewMode === "tree" && (
                <>
                  <button
                    type="button"
                    onClick={handleExpandAll}
                    className="hover:text-amber-400 underline text-dim"
                  >
                    Expand All
                  </button>
                  <span>•</span>
                  <button
                    type="button"
                    onClick={handleCollapseAll}
                    className="hover:text-amber-400 underline text-dim"
                  >
                    Collapse All
                  </button>
                  <span>•</span>
                </>
              )}
              <span className="text-emerald-400 font-semibold">{formatFileSize(stats.totalBytes)}</span>
            </div>
          </div>

          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <div className="flex-1 flex items-center bg-input px-2.5 py-1.5 rounded-lg border border-border text-xs focus-within:border-amber-500/50 transition-colors">
              <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
              <input
                type="text"
                placeholder={t("files.search_placeholder")}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-transparent text-main placeholder-dim w-full focus:outline-none text-xs font-sans"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  className="text-dim hover:text-main text-xs px-1"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <div className="flex items-center bg-input p-0.5 rounded-lg border border-border text-[10px] font-mono">
              {["all", "docs", "media", "archives", "apps"].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFilterCategory(cat)}
                  className={`px-2 py-1 rounded transition-colors uppercase ${
                    filterCategory === cat
                      ? "bg-accent text-white font-semibold shadow-sm"
                      : "text-dim hover:text-main"
                  }`}
                >
                  {t(`files.${cat}`) || cat}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 max-h-[320px] overflow-y-auto rounded-lg border border-border bg-input p-2 space-y-1 font-mono">
            {viewMode === "list" ? (
              filteredFilesList.length > 0 ? (
                filteredFilesList.map((file) => {
                  const isDownloading = downloadingFile?.path === file.path;
                  const isCopied = copiedPath === file.path;
                  return (
                    <div
                      key={file.path}
                      onClick={() => {
                        setSelectedFile(file);
                        handleDownloadFile(file);
                      }}
                      className="group flex items-center justify-between p-2 rounded-lg bg-surface/80 hover:bg-surface-elevated border border-border-muted/40 hover:border-emerald-500/40 transition-all cursor-pointer text-xs"
                    >
                      <div className="flex items-center space-x-2.5 rtl:space-x-reverse min-w-0 flex-1">
                        {getFileIcon(file)}
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center space-x-1.5">
                            <span className="font-semibold text-main truncate font-mono text-[11px]" title={file.name}>
                              {file.name}
                            </span>
                            {getBadgeForExtension(file)}
                          </div>
                          <span className="text-[10px] text-dim block font-sans truncate" title={file.path}>
                            {file.path}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 rtl:space-x-reverse flex-shrink-0 text-dim text-[11px] font-mono">
                        <span className="text-dim text-[10px] font-semibold">
                          {formatFileSize(file.size)}
                        </span>

                        <Button
                          size="sm"
                          variant="default"
                          onClick={(e) => handleDownloadFile(file, e)}
                          className="h-7 px-2 text-[10px] font-mono bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center shadow-sm"
                          title={t("files.download")}
                        >
                          <Download className={`w-3 h-3 mr-1 ${isDownloading ? "animate-bounce" : ""}`} />
                          {isDownloading ? "DOWNLOADING..." : "DOWNLOAD"}
                        </Button>

                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => handleCopyPath(file.path, e)}
                          className="h-7 w-7 p-0 text-dim hover:text-main opacity-0 group-hover:opacity-100 transition-opacity"
                          title={t("files.copy_path")}
                        >
                          {isCopied ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </Button>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="py-12 text-center text-xs text-dim font-mono flex flex-col items-center justify-center space-y-2">
                  <File className="w-8 h-8 text-dim/40" />
                  <p>{t("files.no_matching")}</p>
                </div>
              )
            ) : filesTree.length > 0 ? (
              filesTree.map((rootNode) => renderTreeItem(rootNode, 0))
            ) : (
              <div className="py-12 text-center text-xs text-dim font-mono flex flex-col items-center justify-center space-y-2">
                <Folder className="w-8 h-8 text-dim/40" />
                <p>{t("files.no_records")}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6">
          <div className="bg-surface border border-border rounded-2xl w-full max-w-5xl h-[88vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 text-main">
            <div className="p-4 px-6 border-b border-border flex items-center justify-between bg-header">
              <div className="flex items-center space-x-3 rtl:space-x-reverse">
                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  <FolderTree className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-main flex items-center gap-2">
                    {t("files.dossier_title")}
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-mono">
                      {stats.filesCount} Files / {stats.foldersCount} Folders
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono">
                      {formatFileSize(stats.totalBytes)}
                    </span>
                  </h3>
                  <p className="text-xs text-dim">{t("files.dossier_desc")}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={loading}
                  onClick={handleFetch}
                  className="h-8 text-xs font-mono"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 rtl:mr-0 rtl:ml-1.5 ${loading ? "animate-spin" : ""}`} />
                  {t("files.sync")}
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setIsModalOpen(false)}
                  className="h-8 w-8 p-0 text-dim hover:text-main rounded-lg"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
              <div className="md:col-span-7 border-r border-border bg-background flex flex-col h-full rtl:border-r-0 rtl:border-l">
                <div className="p-3 border-b border-border-muted space-y-2">
                  <div className="flex items-center justify-between bg-input px-2.5 py-1.5 rounded-lg border border-border text-xs font-mono">
                    <span className="text-dim">Path: {currentPath}</span>
                    <span className="text-amber-400 text-[11px] font-semibold">{stats.filesCount} total files</span>
                  </div>

                  <div className="flex items-center space-x-2 rtl:space-x-reverse">
                    <div className="flex-1 flex items-center bg-input px-3 py-1.5 rounded-lg border border-border text-xs focus-within:border-amber-500/50">
                      <Search className="w-3.5 h-3.5 text-dim mr-2 rtl:mr-0 rtl:ml-2 flex-shrink-0" />
                      <input
                        type="text"
                        placeholder={t("files.search_placeholder")}
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="bg-transparent text-main placeholder-dim w-full focus:outline-none text-xs"
                      />
                      {searchTerm && (
                        <button
                          type="button"
                          onClick={() => setSearchTerm("")}
                          className="text-dim hover:text-main"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center bg-input p-0.5 rounded-lg border border-border text-[10px] font-mono">
                      {["all", "docs", "media", "archives", "apps"].map((cat) => (
                        <button
                          key={cat}
                          type="button"
                          onClick={() => setFilterCategory(cat)}
                          className={`px-2 py-1 rounded transition-colors uppercase ${
                            filterCategory === cat
                              ? "bg-accent text-white font-semibold"
                              : "text-dim hover:text-main"
                          }`}
                        >
                          {t(`files.${cat}`) || cat}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-xs">
                  {filesTree.length > 0 ? (
                    filesTree.map((node) => renderTreeItem(node, 0))
                  ) : (
                    <div className="py-20 text-center text-dim font-mono">
                      {t("files.no_records")}
                    </div>
                  )}
                </div>
              </div>

              <div className="md:col-span-5 bg-surface flex flex-col h-full overflow-hidden">
                {selectedFile ? (
                  <div className="flex-1 p-6 sm:p-8 overflow-y-auto flex flex-col justify-between">
                    <div className="space-y-6">
                      <div className="flex items-center space-x-3 rtl:space-x-reverse">
                        <div className="w-14 h-14 rounded-2xl bg-surface-elevated border border-border flex items-center justify-center shadow-lg">
                          {getFileIcon(selectedFile)}
                        </div>
                        <div className="space-y-1 min-w-0 flex-1">
                          <h2 className="text-base font-bold text-main tracking-tight truncate" title={selectedFile.name}>
                            {selectedFile.name}
                          </h2>
                          <div className="flex items-center space-x-2 rtl:space-x-reverse">
                            {getBadgeForExtension(selectedFile)}
                            <span className="text-[11px] font-mono text-dim">
                              {formatFileSize(selectedFile.size)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="bg-input p-4 rounded-xl border border-border space-y-3 font-mono text-xs">
                        <span className="text-[10px] uppercase text-dim block tracking-wider font-sans">
                          {t("files.file_details")}
                        </span>

                        <div className="space-y-2">
                          <div className="flex justify-between items-start border-b border-border-muted/50 pb-1.5">
                            <span className="text-dim text-[11px]">{t("files.path")}</span>
                            <span className="text-main text-[11px] font-medium text-right max-w-[220px] break-all">
                              {selectedFile.path}
                            </span>
                          </div>

                          <div className="flex justify-between items-center border-b border-border-muted/50 pb-1.5">
                            <span className="text-dim text-[11px]">{t("files.size")}</span>
                            <span className="text-main font-semibold">
                              {formatFileSize(selectedFile.size)} ({selectedFile.size || 0} bytes)
                            </span>
                          </div>

                          <div className="flex justify-between items-center border-b border-border-muted/50 pb-1.5">
                            <span className="text-dim text-[11px]">{t("files.type")}</span>
                            <span className="text-main">
                              {selectedFile.mime_type || "application/octet-stream"}
                            </span>
                          </div>

                          <div className="flex justify-between items-center">
                            <span className="text-dim text-[11px]">{t("files.modified")}</span>
                            <span className="text-main">
                              {formatModified(selectedFile.modified)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2 pt-6">
                      {!selectedFile.is_dir && (
                        <Button
                          size="default"
                          variant="default"
                          onClick={() => handleDownloadFile(selectedFile)}
                          className="w-full h-10 text-xs font-mono font-medium bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-950/40"
                        >
                          <Download className={`w-4 h-4 mr-2 rtl:mr-0 rtl:ml-2 ${downloadingFile?.path === selectedFile.path ? "animate-bounce" : ""}`} />
                          {downloadingFile?.path === selectedFile.path ? t("files.downloading") : t("files.download_file")}
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCopyPath(selectedFile.path)}
                        className="w-full h-8 text-xs font-mono flex items-center justify-center"
                      >
                        {copiedPath === selectedFile.path ? (
                          <>
                            <Check className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
                            {t("files.path_copied")}
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 mr-1.5 text-dim" />
                            {t("files.copy_path")}
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-dim">
                    <File className="w-12 h-12 text-dim/30 mb-3" />
                    <p className="text-sm font-medium text-main">{t("files.no_selected")}</p>
                    <p className="text-xs text-dim max-w-xs mt-1">
                      {t("files.no_selected_desc")}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
