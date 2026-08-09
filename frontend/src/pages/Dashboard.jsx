import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import OTPModal from "../components/OTPModal";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";
import "./Dashboard.css";

function Dashboard() {
  const { user } = useAuth();

  return (
    <div className="dashboard-container">
      <Sidebar activePage="/dashboard" />

      <div className="main-wrapper">
        <TopBar title="Dashboard" titleIcon="fas fa-th-large" />

        <div className="dashboard-content">
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">
                Total Assets{" "}
                <i className="fas fa-arrow-up" style={{ color: "#2a7a4a" }}></i>
              </div>
              <div className="stat-value">$48.2B</div>
              <div>
                <span className="stat-change">
                  <i className="fas fa-caret-up"></i> 2.4%
                </span>{" "}
                vs last month
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">NPL Ratio</div>
              <div className="stat-value">1.28%</div>
              <div>
                <span className="stat-change negative">
                  <i className="fas fa-caret-down"></i> 0.06%
                </span>{" "}
                improved
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label"> Liquidity Coverage</div>
              <div className="stat-value">147%</div>
              <div>
                <span className="stat-change">
                  <i className="fas fa-caret-up"></i> 3%
                </span>{" "}
                above threshold
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Risk-Weighted Assets</div>
              <div className="stat-value">$32.7B</div>
              <div>
                <span className="stat-change negative">
                  <i className="fas fa-caret-down"></i> 0.3%
                </span>{" "}
                this quarter
              </div>
            </div>
          </div>

          <div className="analytics-grid">
            <div className="chart-panel">
              <h4>
                <i className="fas fa-chart-line"></i> Monthly revenue & volume
              </h4>
              <div className="chart-placeholder">
                <div className="bar-label">
                  <div className="bar" style={{ height: "68px" }}></div> Jan
                </div>
                <div className="bar-label">
                  <div className="bar light" style={{ height: "82px" }}></div>{" "}
                  Feb
                </div>
                <div className="bar-label">
                  <div className="bar alt" style={{ height: "52px" }}></div> Mar
                </div>
                <div className="bar-label">
                  <div className="bar" style={{ height: "74px" }}></div> Apr
                </div>
                <div className="bar-label">
                  <div className="bar light" style={{ height: "94px" }}></div>{" "}
                  May
                </div>
                <div className="bar-label">
                  <div className="bar alt" style={{ height: "60px" }}></div> Jun
                </div>
                <div className="bar-label">
                  <div className="bar" style={{ height: "108px" }}></div> Jul
                </div>
              </div>
              <div className="inline-stats">
                <span>
                  <i
                    className="fas fa-arrow-up"
                    style={{ color: "#1a7a3a" }}
                  ></i>{" "}
                  +18% QoQ
                </span>
                <span>
                  <i className="fas fa-exchange-alt"></i> 2.4M transactions
                </span>
              </div>
            </div>

            <div className="chart-panel">
              <h4>
                <i className="fas fa-shield-virus"></i> Risk Management report
              </h4>
              <div className="risk-item">
                <span>
                  <i
                    className="fas fa-circle"
                    style={{ color: "#b33a3a", fontSize: "10px" }}
                  ></i>{" "}
                  Credit risk
                </span>
                <span className="risk-level high">High</span>
              </div>
              <div className="risk-item">
                <span>
                  <i
                    className="fas fa-circle"
                    style={{ color: "#b3802b", fontSize: "10px" }}
                  ></i>{" "}
                  Market risk
                </span>
                <span className="risk-level medium">Medium</span>
              </div>
              <div className="risk-item">
                <span>
                  <i
                    className="fas fa-circle"
                    style={{ color: "#1e7e34", fontSize: "10px" }}
                  ></i>{" "}
                  Operational risk
                </span>
                <span className="risk-level low">Low</span>
              </div>
              <div className="risk-item">
                <span>
                  <i
                    className="fas fa-circle"
                    style={{ color: "#b3802b", fontSize: "10px" }}
                  ></i>{" "}
                  Liquidity risk
                </span>
                <span className="risk-level medium">Medium</span>
              </div>
              <div className="flex-row">
                <span className="risk-badge">
                  <i className="fas fa-file-alt"></i> 4 open risks
                </span>
                <span style={{ fontSize: "13px", color: "#1f3a60" }}>
                  <i className="fas fa-chevron-right"></i> details
                </span>
              </div>
              <div
                style={{
                  marginTop: "14px",
                  background: "#ecf3fe",
                  borderRadius: "30px",
                  padding: "6px 14px",
                  fontSize: "13px",
                  display: "flex",
                  gap: "10px",
                }}
              >
                <i className="fas fa-clock" style={{ color: "#1f4c8a" }}></i>{" "}
                Last review: today 09:30
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
            <div
              style={{
                flex: 1,
                background: "white",
                borderRadius: "24px",
                padding: "18px 22px",
                border: "1px solid #eef3fa",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600, color: "#1d2f4a" }}>
                  <i
                    className="fas fa-credit-card"
                    style={{ marginRight: "10px" }}
                  ></i>
                  Top performing products
                </span>
                <span style={{ color: "#3b7bd6", fontSize: "13px" }}>
                  view all
                </span>
              </div>
              <div
                style={{
                  marginTop: "16px",
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "6px 12px",
                  fontSize: "14px",
                }}
              >
                <span>✔ Digital savings</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>
                  +12.4%
                </span>
                <span>✔ Business loans</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>
                  +8.7%
                </span>
                <span>✔ Wealth management</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>
                  +6.2%
                </span>
                <span>✔ Payment gateway</span>
                <span style={{ textAlign: "right", fontWeight: 500 }}>
                  +15.1%
                </span>
              </div>
            </div>
            <div
              style={{
                flex: 0.8,
                background: "white",
                borderRadius: "24px",
                padding: "18px 22px",
                border: "1px solid #eef3fa",
              }}
            >
              <div>
                <i
                  className="fas fa-robot"
                  style={{ color: "#1f4c8a", marginRight: "6px" }}
                ></i>
                <span style={{ fontWeight: 600 }}>AI forecast</span>
              </div>
              <div
                style={{
                  marginTop: "10px",
                  background: "#f1f7ff",
                  borderRadius: "18px",
                  padding: "10px 14px",
                }}
              >
                <span style={{ color: "#2d4f7a" }}>
                  Q3 revenue projected <strong>$13.8B</strong>
                </span>
                <div style={{ display: "flex", gap: "4px", marginTop: "8px" }}>
                  <span
                    style={{
                      background: "#1f3a60",
                      height: "6px",
                      width: "28%",
                      borderRadius: "4px",
                    }}
                  ></span>
                  <span
                    style={{
                      background: "#3b7bd6",
                      height: "6px",
                      width: "48%",
                      borderRadius: "4px",
                    }}
                  ></span>
                  <span
                    style={{
                      background: "#82acf0",
                      height: "6px",
                      width: "24%",
                      borderRadius: "4px",
                    }}
                  ></span>
                </div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: "24px",
              fontSize: "13px",
              color: "#6c81a0",
              borderTop: "1px solid #e2eaf2",
              paddingTop: "20px",
              display: "flex",
              gap: "20px",
              flexWrap: "wrap",
            }}
          >
            <span>
              <i className="fas fa-sync-alt" style={{ marginRight: "6px" }}></i>{" "}
              Last data sync: 10 min ago
            </span>
            <span>
              <i className="fas fa-lock" style={{ marginRight: "6px" }}></i>{" "}
              SOC2 compliant
            </span>
            <span>
              <i className="fas fa-flag"></i> ERP v3.2 · fintech
            </span>
          </div>
        </div>
      </div>
      {user && !user.is_verified && <OTPModal />}
    </div>
  );
}

export default Dashboard;
