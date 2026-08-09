import { useState, useEffect } from "react";
import api from "../axiosconfig";
import { useAuth } from "../context/AuthContext";
import "./OTPModal.css";

function OTPModal() {
  const { user, setUser } = useAuth();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [timeLeft, setTimeLeft] = useState(600);

  useEffect(() => {
    if (!user?.is_verified) {
      setTimeLeft(600);
    }
  }, [user]);

  useEffect(() => {
    if (timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/verify-otp/", { otp });
      if (res.data.is_verified) {
        setUser({ ...user, is_verified: true });
      }
    } catch (err) {
      setError(err.response?.data?.error || "Verification failed");
      setOtp("");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    setError("");

    try {
      await api.post("/auth/resend-otp/");
      setTimeLeft(600);
      setOtp("");
    } catch {
      setError("Failed to resend OTP. Please try again.");
    } finally {
      setResending(false);
    }
  };

  if (user?.is_verified) return null;

  return (
    <div className="otp-overlay">
      <div className="otp-modal">
        <h2>Verify Your Email</h2>
        <p className="otp-description">
          Please enter the 4-digit code sent to your email address.
        </p>

        <form onSubmit={handleVerify}>
          <input
            type="text"
            maxLength={4}
            pattern="\d{4}"
            inputMode="numeric"
            placeholder="Enter 4-digit OTP"
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
            required
            className="otp-input"
          />

          {error && <p className="otp-error">{error}</p>}

          <button type="submit" disabled={loading || otp.length !== 4} className="otp-verify-btn">
            {loading ? "Verifying..." : "Verify"}
          </button>
        </form>

        <div className="otp-footer">
          <p className="otp-timer">Time remaining: {formatTime(timeLeft)}</p>
          <button
            type="button"
            onClick={handleResend}
            disabled={resending}
            className="otp-resend-btn"
          >
            {resending ? "Sending..." : "Resend OTP"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default OTPModal;
