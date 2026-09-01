import React, { useState, useEffect, useMemo } from "react";
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
  ArrowUp,
  FolderTree,
  ExternalLink,
} from "lucide-react";

export default function FileBrowserManager({ status, onRefresh }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [filesTree, setFilesTree] = useState([]);
  const [currentPath, setCurrentPath] = useState("/sdcard");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [copiedPath, setCopiedPath] = useState(null);
  const [downloadingPath, setDownloadingPath] = useState(null);
  const [expandedFolders, setExpandedFolders] = useState({});
  const [selectedFile, setSelectedFile] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  const loadTree = async (path = currentPath) => {
    try {
      const res = await getFilesTree(path);
      if (res.data && res.data.files) {
        setFilesTree(res.data.files);
        if (res.data.path) {
          setCurrentPath(res.data.path);
        }
        const initialExpanded = {};
        res.data.files.forEach((node) => {
          if (node.is_dir) {
            initialExpanded[node.path] = true;
          }
        });
        setExpandedFolders(initialExpanded);
      }
    } catch (e) {}
  };

  useEffect(() => {
    loadTree();
  }, []);

  useEffect(() => {
    if (status?.client_connected && filesTree.length === 0) {
      loadTree();
    }
  }, [status?.client_connected]);

  const handleFetch = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await fetchFiles(currentPath);
      if (res?.data?.status === "ok") {
        if (res.data.data) {
          setFilesTree(res.data.data);
          const initialExpanded = {};
          res.data.data.forEach((node) => {
            if (node.is_dir) {
              initialExpanded[node.path] = true;
            }
          });
          setExpandedFolders(initialExpanded);
        } else {
          await loadTree(currentPath);
        }
      } else {
        setFetchError(res?.data?.message || "Sync failed");
      }
      await onRefresh();
    } catch (e) {
      setFetchError(e?.message || "Sync failed");
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

  const handleDownloadFile = (file, e) => {
    if (e) e.stopPropagation();
    setDownloadingPath(file.path);
    const downloadUrl = getFileDownloadUrl(file.path, status?.active_client_id, file.name);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => {
      setDownloadingPath(null);
    }, 1500);
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
        <span className="text-[9px] font-mono px-1 py-0 rounded bg-amber-950/40 text-amber-400 border border-amber-500/20">
          DIR
        </span>
      );
    }
    const ext = (file.extension || file.name.split(".").pop() || "").toUpperCase();
    return (
      <span className="text-[9px] font-mono px-1 py-0 rounded bg-surface-elevated text-dim border border-border">
        {ext || "BIN"}
      </span>
    );
  };

  const flattenAllFiles = useMemo(() => {
    const list = [];
    const traverse = (nodes, depth = 0, parentPath = "") => {
      if (!nodes || !Array.isArray(nodes)) return;
      nodes.forEach((item) => {
        list.push({ ...item, depth, parentPath });
        if (item.is_dir && item.children && Array.isArray(item.children)) {
          traverse(item.children, depth + 1, item.path);
        }
      });
    };
    traverse(filesTree, 0, currentPath);
    return list;
  }, [filesTree, currentPath]);

  const stats = useMemo(() => {
    let foldersCount = 0;
    let filesCount = 0;
    let totalBytes = 0;
    flattenAllFiles.forEach((f) => {
      if (f.is_dir) {
        foldersCount++;
      } else {
        filesCount++;
        totalBytes += f.size || 0;
      }
    });
    return { foldersCount, filesCount, totalBytes };
  }, [flattenAllFiles]);

  const filterMatches = (item) => {
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      const matchName = item.name.toLowerCase().includes(term);
      const matchPath = item.path.toLowerCase().includes(term);
      if (!matchName && !matchPath) return false;
    }

    if (filterCategory === "folders") return item.is_dir;
    if (filterCategory === "docs") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["pdf", "doc", "docx", "txt", "log", "xlsx", "xls", "csv"].includes(ext);
    }
    if (filterCategory === "media") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["jpg", "jpeg", "png", "webp", "mp4", "mp3", "wav", "m4a", "ogg"].includes(ext);
    }
    if (filterCategory === "archives") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["zip", "rar", "7z", "tar", "gz"].includes(ext);
    }
    if (filterCategory === "apps") {
      const ext = (item.extension || item.name.split(".").pop() || "").toLowerCase();
      return ["apk", "obb", "cache"].includes(ext);
    }
    return true;
  };

  const renderTreeNode = (node, depth = 0) => {
    if (!node) return null;
    const isDir = node.is_dir;
    const isExpanded = !!expandedFolders[node.path];
    const isMatching = filterMatches(node);
    const hasChildren = isDir && node.children && Array.isArray(node.children) && node.children.length > 0;
    const isDownloading = downloadingPath === node.path;
    const isCopied = copiedPath === node.path;
    const isSelected = selectedFile?.path === node.path;

    return (
      <div key={node.path} className="flex flex-col">
        {isMatching && (
          <div
            onClick={() => {
              if (isDir) {
                toggleFolder(node.path);
              } else {
                setSelectedFile(node);
                handleDownloadFile(node);
              }
            }}
            style={{ paddingLeft: `${Math.max(8, depth * 18 + 8)}px` }}
            className={`group flex items-center justify-between py-1.5 pr-2.5 rounded-md text-xs cursor-pointer transition-colors ${
              isSelected
                ? "bg-surface-elevated text-emerald-400 font-medium"
                : "hover:bg-surface-elevated/70 text-main"
            }`}
          >
            <div className="flex items-center space-x-2 rtl:space-x-reverse min-w-0 flex-1">
              {isDir ? (
                <button
                  type="button"
                  onClick={(e) => toggleFolder(node.path, e)}
                  className="p-0.5 rounded hover:bg-input text-dim"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-3.5 h-3.5 text-amber-400" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-amber-400" />
                  )}
                </button>
              ) : (
                <span className="w-3.5 h-3.5 inline-block" />
              )}

              {getFileIcon(node)}

              <span className="truncate font-mono text-[11px] font-medium" title={node.path}>
                {node.name}
              </span>

              {getBadgeForExtension(node)}
            </div>

            <div className="flex items-center space-x-2 rtl:space-x-reverse flex-shrink-0 text-dim text-[10px] font-mono">
              {!isDir && (
                <span className="text-dim hidden sm:inline-block">
                  {formatFileSize(node.size)}
                </span>
              )}

              {isDir && hasChildren && (
                <span className="text-amber-400/80 bg-amber-950/20 px-1 py-0 rounded text-[9px]">
                  {node.children.length}
                </span>
              )}

              <div className="flex items-center space-x-1 rtl:space-x-reverse">
                {!isDir && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => handleDownloadFile(node, e)}
                    className="h-6 w-6 p-0 text-dim hover:text-emerald-400 hover:bg-emerald-950/20"
                    title={t("files.download")}
                  >
                    <Download className={`w-3 h-3 ${isDownloading ? "animate-bounce text-emerald-400" : ""}`} />
                  </Button>
                )}

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={(e) => handleCopyPath(node.path, e)}
                  className="h-6 w-6 p-0 text-dim hover:text-main opacity-0 group-hover:opacity-100 transition-opacity"
                  title={t("files.copy_path")}
                >
                  {isCopied ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {isDir && isExpanded && hasChildren && (
          <div className="flex flex-col border-l border-border-muted/40 ml-3.5 rtl:ml-0 rtl:mr-3.5 rtl:border-l-0 rtl:border-r">
            {node.children.map((child) => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const breadcrumbSegments = useMemo(() => {
    const parts = currentPath.split("/").filter(Boolean);
    const res = [{ name: "root", path: "/" }];
    let acc = "";
    parts.forEach((p) => {
      acc += `/${p}`;
      res.push({ name: p, path: acc });
    });
    return res;
  }, [currentPath]);

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
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-input border border-border text-amber-400 font-semibold">
              {stats.filesCount} {t("files.items_count")}
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-950/30 border border-emerald-500/20 text-emerald-400 hidden sm:inline-block">
              2-LEVEL DEPTH
            </span>
            {fetchError && (
              <span className="text-[10px] font-mono text-rose-400">
                {fetchError}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-1.5 rtl:space-x-reverse">
            <Button
              size="sm"
              variant="outline"
              disabled={loading}
              onClick={handleFetch}
              className="h-7 px-2 text-[11px] font-mono"
            >
              <RefreshCw className={`w-3 h-3 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
              {t("files.sync")}
            </Button>

            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (!selectedFile && flattenAllFiles.length > 0) {
                  const firstFile = flattenAllFiles.find((f) => !f.is_dir) || flattenAllFiles[0];
                  setSelectedFile(firstFile);
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
          <div className="flex items-center justify-between bg-input px-2 py-1 rounded-md border border-border text-[11px] font-mono overflow-x-auto">
            <div className="flex items-center space-x-1 rtl:space-x-reverse text-dim">
              <HardDrive className="w-3 h-3 text-dim flex-shrink-0" />
              {breadcrumbSegments.map((seg, idx) => (
                <React.Fragment key={seg.path}>
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentPath(seg.path);
                      loadTree(seg.path);
                    }}
                    className="hover:text-amber-400 text-dim transition-colors"
                  >
                    {seg.name}
                  </button>
                  {idx < breadcrumbSegments.length - 1 && (
                    <span className="text-border">/</span>
                  )}
                </React.Fragment>
              ))}
            </div>

            <span className="text-[10px] text-dim flex-shrink-0 pl-2">
              {formatFileSize(stats.totalBytes)}
            </span>
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
              {["all", "docs", "media", "archives"].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFilterCategory(cat)}
                  className={`px-1.5 py-1 rounded transition-colors uppercase ${
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

          <div className="flex-1 max-h-[300px] overflow-y-auto rounded-lg border border-border bg-input p-2 space-y-0.5 font-mono">
            {filesTree.length > 0 ? (
              filesTree.map((rootNode) => renderTreeNode(rootNode, 0))
            ) : (
              <div className="py-12 text-center text-xs text-dim font-mono flex flex-col items-center justify-center space-y-2">
                <Folder className="w-8 h-8 text-dim/40" />
                <p>{t("files.no_records")}</p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={loading}
                  onClick={handleFetch}
                  className="h-6 text-[10px] font-mono"
                >
                  <RefreshCw className={`w-2.5 h-2.5 mr-1 rtl:mr-0 rtl:ml-1 ${loading ? "animate-spin" : ""}`} />
                  {t("files.sync")}
                </Button>
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
                  <div className="flex items-center justify-between bg-input px-2.5 py-1 rounded border border-border text-xs font-mono">
                    <span className="text-dim">Path: {currentPath}</span>
                    <span className="text-amber-400 text-[11px] font-semibold">{flattenAllFiles.length} nodes</span>
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
                    filesTree.map((node) => renderTreeNode(node, 0))
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
                          <Download className={`w-4 h-4 mr-2 rtl:mr-0 rtl:ml-2 ${downloadingPath === selectedFile.path ? "animate-bounce" : ""}`} />
                          {downloadingPath === selectedFile.path ? t("files.downloading") : t("files.download_file")}
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
