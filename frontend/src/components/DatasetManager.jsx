import { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import DataEditor from "./DataEditor";
import { datasetApi } from "../services/datasetApi";
import { useAuth } from "../context/AuthContext";

const STATUS_META = {
  draft: { label: "Draft", cls: "draft" },
  submitted: { label: "Submitted", cls: "submitted" },
  in_review: { label: "In Review", cls: "in_review" },
  reviewed: { label: "Reviewed", cls: "reviewed" },
  confirmed: { label: "Confirmed", cls: "confirmed" },
  rejected: { label: "Rejected", cls: "rejected" },
};

function statusMeta(status) {
  return STATUS_META[status] || { label: status || "", cls: "" };
}

function DatasetManager({
  section,
  activePage,
  title,
  titleIcon,
  wrapperClass = "page",
  contentClass = "page-content",
  headerIcon = "fa-database",
  headerTitle = "Data tables",
  emptyIcon = "fa-database",
  emptyTitle = "No tables yet",
  emptySubtitle = "Upload a file or create a new table to get started.",
  refreshLabel = "Refresh",
}) {
  const [tables, setTables] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadFeedback, setUploadFeedback] = useState("");
  const [createFeedback, setCreateFeedback] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);

  const [tableName, setTableName] = useState("");
  const [tableDesc, setTableDesc] = useState("");
  const [colCount, setColCount] = useState(4);
  const [rowCount, setRowCount] = useState(10);

  const { user } = useAuth();
  const ALL_CAPS = ["can_view", "can_create", "can_edit", "can_delete", "can_review", "can_approve"];
  const isAdmin = user?.is_admin || user?.is_staff;
  const caps = isAdmin
    ? ALL_CAPS
    : user?.employee?.capabilities?.[section] || [];
  const can = (cap) => caps.includes(cap);

  useEffect(() => {
    loadDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadDatasets = async () => {
    try {
      const data = await datasetApi.getDatasets(section);
      const formattedTables = data.map((ds) => ({
        id: ds.id,
        name: ds.name,
        type: ds.original_filename.split(".").pop().toUpperCase(),
        rows: ds.row_count,
        icon: ds.original_filename.endsWith(".csv") ? "fa-file-csv" : "fa-file-excel",
        status: ds.status,
        tableName: ds.table_name,
      }));
      setTables(formattedTables);
    } catch (error) {
      console.error("Failed to load datasets:", error);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setUploadFeedback(
        <span>
          <i className="fas fa-check-circle" style={{ color: "#1a7a3a" }}></i>{" "}
          File selected: <strong>{file.name}</strong> (ready to upload)
        </span>
      );
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadFeedback(
        <span style={{ color: "#b3802b" }}>
          <i className="fas fa-exclamation-circle"></i> Please select a file first.
        </span>
      );
      return;
    }

    setIsLoading(true);
    setUploadProgress("Uploading file...");

    try {
      const result = await datasetApi.uploadFile(selectedFile, section);
      const jobId = result.job_id;

      setUploadProgress("Processing data...");

      let interval = 1000;
      const maxInterval = 10000;
      const startTime = Date.now();
      const LONG_JOB_THRESHOLD = 15000;

      const pollJobStatus = async () => {
        while (true) {
          const jobStatus = await datasetApi.getJobStatus(jobId);

          if (jobStatus.status === "done") {
            setUploadProgress("Complete!");
            setUploadFeedback(
              <span>
                <i className="fas fa-check-circle" style={{ color: "#1a7a3a" }}></i>{" "}
                File uploaded and processed successfully!
              </span>
            );

            await loadDatasets();

            setTimeout(() => {
              setShowUpload(false);
              setSelectedFile(null);
              setUploadFeedback("");
              setUploadProgress("");
            }, 2000);
            setIsLoading(false);
            return;
          } else if (jobStatus.status === "failed") {
            setUploadProgress("");
            setUploadFeedback(
              <span style={{ color: "#d32f2f" }}>
                <i className="fas fa-exclamation-circle"></i>{" "}
                Error: {jobStatus.error_message}
              </span>
            );
            setIsLoading(false);
            return;
          }

          if (jobStatus.progress) {
            const percent = Math.round((jobStatus.progress.current / jobStatus.progress.total) * 100);
            setUploadProgress(`Processing: ${percent}% (${jobStatus.progress.phase})`);
          } else {
            const elapsed = Date.now() - startTime;
            if (elapsed > LONG_JOB_THRESHOLD) {
              setUploadProgress("Processing... (this may take a while for large files)");
            } else {
              setUploadProgress("Processing data...");
            }
          }

          await new Promise((resolve) => setTimeout(resolve, interval));

          if (interval < maxInterval) {
            interval = Math.min(interval * 1.5, maxInterval);
          }
        }
      };

      pollJobStatus();
    } catch (error) {
      setUploadProgress("");
      setUploadFeedback(
        <span style={{ color: "#d32f2f" }}>
          <i className="fas fa-exclamation-circle"></i>{" "}
          Upload failed: {error.response?.data?.detail || error.message}
        </span>
      );
      setIsLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setCreateFeedback("");

    try {
      const data = {
        name: tableName,
        description: tableDesc,
        col_count: parseInt(colCount),
        row_count: parseInt(rowCount),
        section,
      };
      const result = await datasetApi.createTable(data);

      setCreateFeedback(
        <span style={{ color: "#1a7a3a" }}>
          <i className="fas fa-check-circle"></i> Table created successfully!
        </span>
      );

      setTimeout(() => {
        hideAllPanels();
        setSelectedDatasetId(result.id);
        setTableName("");
        setTableDesc("");
        setColCount(4);
        setRowCount(10);
      }, 1500);
    } catch (error) {
      setCreateFeedback(
        <span style={{ color: "#d32f2f" }}>
          <i className="fas fa-exclamation-circle"></i> Failed to create table: {error.response?.data?.detail || error.message}
        </span>
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this dataset? This action cannot be undone.")) {
      return;
    }

    try {
      await datasetApi.deleteDataset(id);
      setTables(tables.filter((t) => t.id !== id));
    } catch (error) {
      console.error("Failed to delete dataset:", error);
      alert("Failed to delete dataset. Please try again.");
    }
  };

  const handleEdit = (id) => {
    setSelectedDatasetId(id);
  };

  const handleBackToTables = () => {
    setSelectedDatasetId(null);
    loadDatasets();
  };

  const hideAllPanels = () => {
    setShowUpload(false);
    setShowCreate(false);
    setUploadFeedback("");
    setCreateFeedback("");
    setSelectedFile(null);
    setUploadProgress("");
  };

  return (
    <div className={wrapperClass}>
      <Sidebar activePage={activePage} />

      <div className="main-wrapper">
        <TopBar title={title} titleIcon={titleIcon} />

        <div className={contentClass}>
          {!selectedDatasetId && (
            <div className="page-header">
              <h2>
                <i className={`fas ${headerIcon}`}></i> {headerTitle}
              </h2>
              <div className="action-buttons">
                {can("can_create") && (
                  <button className="btn btn-outline" onClick={() => { hideAllPanels(); setShowUpload(true); }}>
                    <i className="fas fa-upload"></i> Upload file
                  </button>
                )}
                {can("can_create") && (
                  <button className="btn btn-primary" onClick={() => { hideAllPanels(); setShowCreate(true); }}>
                    <i className="fas fa-plus-circle"></i> Create table
                  </button>
                )}
              </div>
            </div>
          )}

          <div className="table-list-section">
            <div className="section-title">
              <i className="fas fa-table" style={{ color: "#3b7bd6" }}></i> Existing tables
              {tables.length > 0 && <span>{tables.length} tables</span>}
            </div>

            {tables.length === 0 ? (
              <div className="empty-state">
                <i className={`fas ${emptyIcon}`}></i>
                <p className="empty-title">{emptyTitle}</p>
                <p className="empty-subtitle">{emptySubtitle}</p>
                <div className="empty-actions">
                  {can("can_create") && (
                    <button className="btn btn-primary" onClick={() => { hideAllPanels(); setShowUpload(true); }}>
                      <i className="fas fa-upload"></i> Upload File
                    </button>
                  )}
                  {can("can_create") && (
                    <button className="btn btn-outline" onClick={() => { hideAllPanels(); setShowCreate(true); }}>
                      <i className="fas fa-plus"></i> Create Table
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="table-grid">
                {tables.map((table) => (
                  <div key={table.id} className="table-card">
                    <i className={`fas ${table.icon}`}></i>
                    <div className="table-info">
                      <div className="table-name">{table.name}</div>
                      <div className="table-meta">
                        {table.type} · {table.rows} rows
                        <span className={`status-badge ${statusMeta(table.status).cls}`}>
                          {statusMeta(table.status).label}
                        </span>
                      </div>
                    </div>
                    <div className="table-actions">
                      <i className="fas fa-edit" onClick={() => handleEdit(table.id)}></i>
                      {can("can_delete") && (
                        <i className="fas fa-trash-alt" onClick={() => handleDelete(table.id)}></i>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedDatasetId && (
            <DataEditor
              datasetId={selectedDatasetId}
              onBack={handleBackToTables}
              onUpdate={loadDatasets}
            />
          )}

          {showUpload && (
            <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) hideAllPanels(); }}>
              <div className="modal-content">
                <div className="modal-header">
                  <h4><i className="fas fa-upload"></i> Upload XLS or CSV</h4>
                  <button className="modal-close" onClick={hideAllPanels}><i className="fas fa-times"></i></button>
                </div>
                <div className={`upload-area ${dragOver ? "dragover" : ""}`}
                  onClick={() => document.getElementById("fileInput").click()}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    const file = e.dataTransfer.files[0];
                    if (file) {
                      setSelectedFile(file);
                      setUploadFeedback(<span><i className="fas fa-check-circle" style={{ color: "#1a7a3a" }}></i> File selected: <strong>{file.name}</strong> (ready to upload)</span>);
                    }
                  }}
                >
                  <i className="fas fa-cloud-upload-alt"></i>
                  <p>Drop your file here or click to browse</p>
                  <small>Supports .xls, .xlsx, .csv</small>
                  <input type="file" id="fileInput" accept=".xls,.xlsx,.csv" onChange={handleFileSelect} />
                </div>
                {uploadProgress && (
                  <div className="upload-progress">
                    <i className="fas fa-spinner fa-spin"></i> {uploadProgress}
                  </div>
                )}
                <div style={{ marginTop: 14, display: "flex", gap: 12 }}>
                  <button
                    className="btn btn-success"
                    onClick={handleUpload}
                    style={{ flex: 1 }}
                    disabled={isLoading}
                  >
                    {isLoading ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-check"></i>}
                    {isLoading ? "Uploading..." : "Upload"}
                  </button>
                  <button className="btn btn-outline" onClick={hideAllPanels} disabled={isLoading}><i className="fas fa-times"></i> Cancel</button>
                </div>
                {uploadFeedback && <div className="feedback-message feedback-success">{uploadFeedback}</div>}
              </div>
            </div>
          )}

          {showCreate && (
            <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) hideAllPanels(); }}>
              <div className="modal-content">
                <div className="modal-header">
                  <h4><i className="fas fa-pen-fancy"></i> Create table from scratch</h4>
                  <button className="modal-close" onClick={hideAllPanels}><i className="fas fa-times"></i></button>
                </div>
                <form className="manual-form" onSubmit={handleCreate}>
                  <div className="form-group">
                    <label>Table name</label>
                    <input type="text" placeholder="e.g. Budget_2026" value={tableName} onChange={(e) => setTableName(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Description (optional)</label>
                    <input type="text" placeholder="Short description" value={tableDesc} onChange={(e) => setTableDesc(e.target.value)} />
                  </div>
                  <div className="row2">
                    <div className="form-group">
                      <label>Columns</label>
                      <input type="number" placeholder="e.g. 5" value={colCount} onChange={(e) => setColCount(e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label>Rows</label>
                      <input type="number" placeholder="e.g. 20" value={rowCount} onChange={(e) => setRowCount(e.target.value)} />
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={isLoading}>
                    {isLoading ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plus"></i>} Create table
                  </button>
                </form>
                {createFeedback && <div className="feedback-message feedback-success">{createFeedback}</div>}
              </div>
            </div>
          )}

          {tables.length > 0 && !selectedDatasetId && (
            <div className="demo-toggle">
              <button onClick={loadDatasets}><i className="fas fa-sync"></i> {refreshLabel}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DatasetManager;
