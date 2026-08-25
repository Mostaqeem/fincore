import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import "./DepartmentStats.css";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function DepartmentStats({ totalUsers, departments }) {
  const chartData = {
    labels: departments.map((d) => d.name),
    datasets: [
      {
        label: "Tables",
        data: departments.map((d) => d.count),
        backgroundColor: "#3b7bd6",
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } },
  };

  return (
    <section className="department-stats-panel">
      <div className="total-users">
        <span className="total-label">Total Users</span>
        <span className="total-value">{totalUsers}</span>
      </div>

      <div className="chart-container">
        <h4>Tables per Department</h4>
        <Bar data={chartData} options={options} />
      </div>
    </section>
  );
}

export default DepartmentStats;