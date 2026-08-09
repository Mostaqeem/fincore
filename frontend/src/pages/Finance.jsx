import DatasetManager from "../components/DatasetManager";
import "./Finance.css";

function Finance() {
  return (
    <DatasetManager
      section="finance"
      activePage="/finance"
      title="Finance"
      titleIcon="fas fa-coins"
      wrapperClass="finance-page"
      contentClass="finance-content"
      headerTitle="Financial data tables"
      emptyTitle="No financial tables yet"
      emptySubtitle="Upload a file or create a new table to get started."
    />
  );
}

export default Finance;
