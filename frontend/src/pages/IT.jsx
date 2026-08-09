import DatasetManager from "../components/DatasetManager";
import "./IT.css";

function IT() {
  return (
    <DatasetManager
      section="it"
      activePage="/it"
      title="IT"
      titleIcon="fas fa-server"
      wrapperClass="it-page"
      headerTitle="IT Asset Tables"
      headerIcon="fa-database"
      emptyIcon="fa-server"
      emptyTitle="No IT tables yet"
      emptySubtitle="Upload a file or create a new table to get started."
    />
  );
}

export default IT;
