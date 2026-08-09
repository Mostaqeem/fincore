import DatasetManager from "../components/DatasetManager";
import "./RiskManagement.css";

function RiskManagement() {
  return (
    <DatasetManager
      section="risk"
      activePage="/risk-management"
      title="Risk Management"
      titleIcon="fas fa-shield-alt"
      wrapperClass="risk-page"
      headerTitle="Risk Register"
      headerIcon="fa-shield-virus"
      emptyIcon="fa-shield-alt"
      emptyTitle="No risk tables yet"
      emptySubtitle="Upload a file or create a new table to start tracking risks."
    />
  );
}

export default RiskManagement;
