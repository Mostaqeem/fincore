import { useState, useEffect, useCallback } from "react";
import { datasetApi } from "../services/datasetApi";
import { useAuth } from "../context/AuthContext";
import "./DataEditor.css";

const STATUS_META = {
  draft: { label: "Draft", cls: "draft" },
  submitted: { label: "Submitted", cls: "submitted" },
  in_review: { label: "In Review", cls: "in_review" },
  reviewed: { label: "Reviewed", cls: "reviewed" },
  confirmed: { label: "Confirmed", cls: "confirmed" },
  rejected: { label: "Rejected", cls: "rejected" },
};

const EDITABLE_STATUSES = ["draft", "rejected"];

function statusMeta(status) {
  return STATUS_META[status] || { label: status || "", cls: "" };
}

function DataEditor({ datasetId, onBack, onUpdate }) {
  const [dataset, setDataset] = useState(null);
  const [data, setData] = useState([]);
  const [columns, setColumns] = useState([]);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 50,
    totalCount: 0,
    totalPages: 1,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [isAddingRow, setIsAddingRow] = useState(false);
  const [newRowData, setNewRowData] = useState({});

  const [isEditingRow, setIsEditingRow] = useState(false);
  const [editingRowId, setEditingRowId] = useState(null);
  const [editingRowData, setEditingRowData] = useState({});

  const [isRenamingColumn, setIsRenamingColumn] = useState(false);
  const [renamingColumn, setRenamingColumn] = useState(null);
  const [newColumnName, setNewColumnName] = useState("");

  const [isEditMode, setIsEditMode] = useState(false);

  const [actionFeedback, setActionFeedback] = useState("");
  const [workflowModal, setWorkflowModal] = useState(null);

  const { user } = useAuth();
  const section = dataset?.section;
  const ALL_CAPS = ["can_view", "can_create", "can_edit", "can_delete", "can_review", "can_approve"];
  const isAdmin = user?.is_admin || user?.is_staff;
  const caps = isAdmin
    ? ALL_CAPS
    : user?.employee?.capabilities?.[section] || [];
  const can = (cap) => caps.includes(cap);
  const editable = EDITABLE_STATUSES.includes(dataset?.status);
  const isCreator = user?.id === dataset?.created_by;

  const loadDataset = useCallback(async () => {
    try {
      const ds = await datasetApi.getDataset(datasetId);
      setDataset(ds);
    } catch (err) {
      console.error("Failed to load dataset:", err);
    }
  }, [datasetId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await datasetApi.getDatasetData(
        datasetId,
        pagination.page,
        pagination.pageSize
      );
      setData(result.rows);
      setColumns(result.columns);
      setPagination((prev) => ({
        ...prev,
        totalCount: result.total_count,
        totalPages: result.total_pages,
      }));
    } catch (err) {
      setError("Failed to load data: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, [datasetId, pagination.page, pagination.pageSize]);

  useEffect(() => {
    loadDataset();
  }, [loadDataset]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showFeedback = (message, isError = false) => {
    setActionFeedback(
      <span style={{ color: isError ? "#b33a3a" : "#1a7a3a" }}>
        <i className={`fas ${isError ? "fa-exclamation-circle" : "fa-check-circle"}`}></i>{" "}
        {message}
      </span>
    );
    setTimeout(() => setActionFeedback(""), 3000);
  };

  const handleAddRow = async () => {
    if (Object.keys(newRowData).length === 0) {
      showFeedback("Please fill in at least one field", true);
      return;
    }

    try {
      await datasetApi.addRow(datasetId, newRowData);
      await loadData();
      await loadDataset();
      setIsAddingRow(false);
      setNewRowData({});
      showFeedback("Row added successfully");
    } catch (err) {
      showFeedback("Failed to add row: " + (err.response?.data?.detail || err.message), true);
    }
  };

  const openEditModal = (row) => {
    setEditingRowId(row.id);
    const { id: _rowId, ...rowData } = row;
    setEditingRowData(rowData);
    setIsEditingRow(true);
    console.log("Editing row:", row.id, rowData);
  };

  const handleSaveEdit = async () => {
    try {
      await datasetApi.updateRow(datasetId, editingRowId, editingRowData);
      await loadData();
      setIsEditingRow(false);
      showFeedback("Row updated successfully");
    } catch (err) {
      showFeedback("Failed to update row: " + (err.response?.data?.error || err.message), true);
    }
  };

  const handleDeleteRow = async (rowId) => {
    if (!window.confirm("Are you sure you want to delete this row?")) return;

    try {
      await datasetApi.deleteRow(datasetId, rowId);
      await loadData();
      await loadDataset();
      showFeedback("Row deleted successfully");
    } catch (err) {
      showFeedback("Failed to delete row: " + (err.response?.data?.detail || err.message), true);
    }
  };

  const handleRenameColumn = async (oldName) => {
    if (!newColumnName.trim()) {
      showFeedback("Please enter a column name", true);
      return;
    }

    try {
      await datasetApi.renameColumn(datasetId, oldName, newColumnName.trim());
      await loadData();
      setIsRenamingColumn(false);
      setRenamingColumn(null);
      setNewColumnName("");
      showFeedback("Column renamed successfully");
    } catch (err) {
      showFeedback("Failed to rename column: " + (err.response?.data?.error || err.message), true);
    }
  };

  const openWorkflowModal = (type) => {
    const meta = {
      submit: { title: "Submit for Review", label: "Submit", hint: "Send this table for review." },
      start_review: { title: "Start Review", label: "Start Review", hint: "Begin reviewing this table." },
      review_approve: { title: "Approve Review", label: "Approve Review", hint: "Review complete — pass it on for final approval." },
      approve: { title: "Approve Table", label: "Approve", hint: "Confirm this table." },
      reject: { title: "Request Changes", label: "Reject", hint: "Send this table back for rework." },
    };
    setWorkflowModal({ type, comment: "", ...meta[type] });
  };

  const runWorkflowAction = async (type, comment) => {
    try {
      if (type === "submit") await datasetApi.submitDataset(datasetId);
      else if (type === "start_review") await datasetApi.startReview(datasetId);
      else if (type === "review_approve") await datasetApi.reviewApprove(datasetId, comment);
      else if (type === "approve") await datasetApi.approveDataset(datasetId, comment);
      else if (type === "reject") await datasetApi.rejectDataset(datasetId, comment);

      await loadDataset();
      if (onUpdate) onUpdate();
      setWorkflowModal(null);
      showFeedback("Action completed successfully");
    } catch (err) {
      showFeedback(
        (err.response?.data?.error || err.response?.data?.detail || err.message),
        true
      );
    }
  };

  const handleDiscard = async () => {
    if (!window.confirm("Are you sure you want to discard this dataset? This action cannot be undone.")) return;

    try {
      await datasetApi.deleteDataset(datasetId);
      if (onUpdate) onUpdate();
      onBack();
    } catch (err) {
      showFeedback("Failed to discard: " + (err.response?.data?.detail || err.message), true);
    }
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= pagination.totalPages) {
      setPagination((prev) => ({ ...prev, page: newPage }));
    }
  };

  const handleCellBlur = async (rowId, columnName, value) => {
    if (!isEditMode) return;
    try {
      await datasetApi.updateCell(datasetId, rowId, columnName, value);
      showFeedback(`Cell ${columnName} updated`);
      console.log(`Cell updated: row ${rowId}, column ${columnName}, value ${value}`);
    } catch (err) {
      showFeedback("Failed to update cell: " + (err.response?.data?.error || err.message), true);
    }
  };

  return (
    <div className="data-editor">
      <div className="editor-header">
        <button className="btn btn-outline back-btn" onClick={onBack}>
          <i className="fas fa-arrow-left"></i> Back
        </button>
        <div className="editor-title">
          <h2>
            <i className="fas fa-table"></i> {dataset?.name || "Loading..."}
          </h2>
          {dataset?.status && (
            <span className={`status-badge ${statusMeta(dataset.status).cls}`}>
              {statusMeta(dataset.status).label}
            </span>
          )}
        </div>
        <div className="editor-info">
          <span>{pagination.totalCount} rows</span>
          {dataset?.section && <span className="section-pill">{statusMeta(dataset.section).label || dataset.section}</span>}
        </div>
      </div>

      {dataset && (
        <div className="workflow-strip">
          {dataset.status !== "draft" && (
            <span>
              <i className="fas fa-paper-plane"></i> Submitted by{" "}
              <strong>{dataset.submitted_by_name || "—"}</strong>
              {dataset.submitted_at ? ` · ${new Date(dataset.submitted_at).toLocaleString()}` : ""}
            </span>
          )}
          {dataset.reviewed_by_name && (
            <span>
              <i className="fas fa-search"></i> Reviewed by{" "}
              <strong>{dataset.reviewed_by_name}</strong>
              {dataset.review_comment ? ` · "${dataset.review_comment}"` : ""}
            </span>
          )}
          {dataset.approved_by_name && (
            <span>
              <i className="fas fa-check-double"></i> Approved by{" "}
              <strong>{dataset.approved_by_name}</strong>
              {dataset.approval_comment ? ` · "${dataset.approval_comment}"` : ""}
            </span>
          )}
          {dataset.rejection_comment && (
            <span className="workflow-rejected">
              <i className="fas fa-undo"></i> Rejected: "{dataset.rejection_comment}"
            </span>
          )}
        </div>
      )}

      {error && (
        <div className="editor-error">
          <i className="fas fa-exclamation-circle"></i> {error}
        </div>
      )}

       <div className="editor-toolbar">
         {editable && can("can_edit") && (
           <button className="btn btn-primary" onClick={() => setIsAddingRow(true)}>
             <i className="fas fa-plus"></i> Add Row
           </button>
         )}
         {editable && can("can_edit") && (
           <button 
             className={`btn ${isEditMode ? "btn-success" : "btn-outline"}`} 
             onClick={() => setIsEditMode(!isEditMode)}
             style={{ marginLeft: 10 }}
           >
             <i className={`fas ${isEditMode ? "fa-eye" : "fa-edit"}`}></i> 
             {isEditMode ? "Preview Mode" : "Edit Mode"}
           </button>
         )}
         <div className="toolbar-spacer"></div>
         {actionFeedback && (
           <div className="feedback-message feedback-inline">{actionFeedback}</div>
         )}
       </div>


      <div className="editor-table-container">
        {loading ? (
          <div className="editor-loading">
            <i className="fas fa-spinner fa-spin"></i> Loading data...
          </div>
        ) : (
          <table className="editor-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.name}>
                    <div className="th-content">
                      <span className="col-name">{col.name}</span>
                      <span className="col-type">{col.type}</span>
                      {editable && can("can_edit") && (
                        <button
                          className="col-rename-btn"
                          onClick={() => {
                            setIsRenamingColumn(true);
                            setRenamingColumn(col.name);
                            setNewColumnName(col.name);
                          }}
                          title="Rename column"
                        >
                          <i className="fas fa-pen"></i>
                        </button>
                      )}
                    </div>
                  </th>
                ))}
                <th className="actions-col">
                  {editable && can("can_edit") ? "Actions" : ""}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} className="empty-row">
                    No data available
                  </td>
                </tr>
              ) : (
                data.map((row, rowIndex) => (
                  <tr key={row.id || rowIndex}>
                    {columns.map((col) => (
                      <td key={col.name}>
                        {isEditMode && editable && can("can_edit") ? (
                          <input
                            className="cell-edit-input"
                            value={row[col.name] === null ? "" : String(row[col.name])}
                            onChange={(e) => {
                              // We use a temporary local state for the input if we wanted it to be smooth,
                              // but since updateCell is the source of truth, we'll update the data state
                              const newData = [...data];
                              const rowIndex = data.findIndex(r => r.id === row.id);
                              newData[rowIndex] = { ...row, [col.name]: e.target.value };
                              setData(newData);
                            }}
                            onBlur={(e) => handleCellBlur(row.id, col.name, e.target.value)}
                          />
                        ) : (
                          <span className="cell-value">
                            {row[col.name] === null ? "" : String(row[col.name])}
                          </span>
                        )}
                      </td>
                    ))}
                    {editable && can("can_edit") && (
                      <td className="actions-col">
                        <button
                          className="row-edit-btn"
                          onClick={() => openEditModal(row)}
                          title="Edit row"
                        >
                          <i className="fas fa-edit"></i>
                        </button>
                        <button
                          className="row-delete-btn"
                          onClick={() => handleDeleteRow(row.id)}
                          title="Delete row"
                        >
                          <i className="fas fa-trash-alt"></i>
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      <div className="editor-footer">
        <div className="pagination">
          <button
            className="btn btn-outline"
            onClick={() => handlePageChange(1)}
            disabled={pagination.page === 1}
          >
            <i className="fas fa-angle-double-left"></i>
          </button>
          <button
            className="btn btn-outline"
            onClick={() => handlePageChange(pagination.page - 1)}
            disabled={pagination.page === 1}
          >
            <i className="fas fa-angle-left"></i>
          </button>
          <span className="page-info">
            Page {pagination.page} of {pagination.totalPages}
          </span>
          <button
            className="btn btn-outline"
            onClick={() => handlePageChange(pagination.page + 1)}
            disabled={pagination.page === pagination.totalPages}
          >
            <i className="fas fa-angle-right"></i>
          </button>
          <button
            className="btn btn-outline"
            onClick={() => handlePageChange(pagination.totalPages)}
            disabled={pagination.page === pagination.totalPages}
          >
            <i className="fas fa-angle-double-right"></i>
          </button>
        </div>

         <div className="editor-actions">
           {dataset?.status === "draft" && can("can_create") && isCreator && (
             <button className="btn btn-primary" onClick={() => openWorkflowModal("submit")}>
               <i className="fas fa-paper-plane"></i> Submit for Review
             </button>
           )}
           {dataset?.status === "rejected" && can("can_create") && isCreator && (
             <button className="btn btn-primary" onClick={() => openWorkflowModal("submit")}>
               <i className="fas fa-paper-plane"></i> Re-submit
             </button>
           )}
           {dataset?.status === "submitted" && can("can_review") && (
             <button className="btn btn-primary" onClick={() => openWorkflowModal("start_review")}>
               <i className="fas fa-search"></i> Start Review
             </button>
           )}
           {dataset?.status === "in_review" && can("can_review") && (
             <>
               <button className="btn btn-success" onClick={() => openWorkflowModal("review_approve")}>
                 <i className="fas fa-check"></i> Approve Review
               </button>
               <button className="btn btn-outline" onClick={() => openWorkflowModal("reject")}>
                 <i className="fas fa-undo"></i> Request Changes
               </button>
             </>
           )}
           {dataset?.status === "reviewed" && can("can_approve") && (
             <>
               <button className="btn btn-success" onClick={() => openWorkflowModal("approve")}>
                 <i className="fas fa-check-double"></i> Approve
               </button>
               <button className="btn btn-outline" onClick={() => openWorkflowModal("reject")}>
                 <i className="fas fa-undo"></i> Request Changes
               </button>
             </>
           )}
           {can("can_delete") && (
             <button className="btn btn-danger" onClick={handleDiscard}>
               <i className="fas fa-trash"></i>{" "}
               {dataset?.status === "confirmed" ? "Delete Dataset" : "Discard"}
             </button>
           )}
         </div>

      </div>

      {isAddingRow && (
        <div className="modal-overlay" onClick={() => setIsAddingRow(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-plus-circle"></i> Add New Row
              </h4>
              <button className="modal-close" onClick={() => setIsAddingRow(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="add-row-form">
              {columns.map((col) => (
                <div className="form-group" key={col.name}>
                  <label>
                    {col.name} <span className="type-hint">({col.type})</span>
                  </label>
                  <input
                    type="text"
                    value={newRowData[col.name] || ""}
                    onChange={(e) =>
                      setNewRowData({ ...newRowData, [col.name]: e.target.value })
                    }
                    placeholder={`Enter ${col.name}`}
                  />
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleAddRow}>
                <i className="fas fa-plus"></i> Add Row
              </button>
              <button className="btn btn-outline" onClick={() => setIsAddingRow(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isEditingRow && (
        <div className="modal-overlay" onClick={() => setIsEditingRow(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-edit"></i> Edit Row
              </h4>
              <button className="modal-close" onClick={() => setIsEditingRow(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="add-row-form">
              {columns.map((col) => (
                <div className="form-group" key={col.name}>
                  <label>
                    {col.name} <span className="type-hint">({col.type})</span>
                  </label>
                  <input
                    type="text"
                    value={editingRowData[col.name] || ""}
                    onChange={(e) =>
                      setEditingRowData({ ...editingRowData, [col.name]: e.target.value })
                    }
                    placeholder={`Enter ${col.name}`}
                  />
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleSaveEdit}>
                <i className="fas fa-check"></i> Save Changes
              </button>
              <button className="btn btn-outline" onClick={() => setIsEditingRow(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isRenamingColumn && (
        <div className="modal-overlay" onClick={() => setIsRenamingColumn(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-pen"></i> Rename Column
              </h4>
              <button className="modal-close" onClick={() => setIsRenamingColumn(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="form-group">
              <label>Current name</label>
              <input type="text" value={renamingColumn} disabled />
            </div>
            <div className="form-group">
              <label>New name</label>
              <input
                type="text"
                value={newColumnName}
                onChange={(e) => setNewColumnName(e.target.value)}
                placeholder="Enter new column name"
                onKeyDown={(e) => e.key === "Enter" && handleRenameColumn(renamingColumn)}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => handleRenameColumn(renamingColumn)}>
                <i className="fas fa-check"></i> Rename
              </button>
              <button className="btn btn-outline" onClick={() => setIsRenamingColumn(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {workflowModal && (
        <div className="modal-overlay" onClick={() => setWorkflowModal(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>
                <i className="fas fa-tasks"></i> {workflowModal.title}
              </h4>
              <button className="modal-close" onClick={() => setWorkflowModal(null)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <p className="workflow-hint">{workflowModal.hint}</p>
            {(workflowModal.type === "review_approve" ||
              workflowModal.type === "approve" ||
              workflowModal.type === "reject") && (
              <div className="form-group">
                <label>Comment</label>
                <textarea
                  rows={3}
                  value={workflowModal.comment}
                  onChange={(e) => setWorkflowModal({ ...workflowModal, comment: e.target.value })}
                  placeholder="Add a comment for the record (optional)"
                />
              </div>
            )}
            <div className="modal-actions">
              <button
                className="btn btn-primary"
                onClick={() => runWorkflowAction(workflowModal.type, workflowModal.comment)}
              >
                <i className="fas fa-check"></i> {workflowModal.label}
              </button>
              <button className="btn btn-outline" onClick={() => setWorkflowModal(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataEditor;
