import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../axiosconfig";
import "./ForgotPassword.css";

function ForgotPassword({ onClose }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isChange = Boolean(user);
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [timeLeft, setTimeLeft] = useState(60);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (step === 2 && timeLeft > 0) {
      const timer = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [step, timeLeft]);

  useEffect(() => {
    if (step === 2) {
      setTimeLeft(60);
    }
  }, [step]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/auth/forgot-password/", { email });
      setStep(2);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleOtpVerify = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/auth/verify-forgot-password-otp/", { email, otp });
      setStep(3);
    } catch (err) {
      setError(err.response?.data?.error || "Invalid or expired OTP");
      setOtp("");
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async (e) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);

    try {
      await api.post("/auth/reset-password/", {
        email,
        otp,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setSuccess(true);
      setTimeout(() => {
        if (onClose) {
          onClose();
        } else {
          navigate("/signin");
        }
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    setError("");

    try {
      await api.post("/auth/forgot-password/", { email });
      setTimeLeft(60);
      setOtp("");
    } catch {
      setError("Failed to resend OTP. Please try again.");
    } finally {
      setResending(false);
    }
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    } else if (isChange) {
      navigate("/dashboard");
    } else {
      navigate("/signin");
    }
  };

  return (
    <div className="fp-overlay">
      <div className="fp-modal">
        <button className="fp-close" onClick={handleClose}>
          &times;
        </button>

        {success ? (
          <div className="fp-success">
            <div className="fp-success-icon">&#10003;</div>
            <h2>{isChange ? "Password Changed!" : "Password Reset!"}</h2>
            <p>Your password has been changed successfully.</p>
            <p>Redirecting to login...</p>
          </div>
        ) : (
          <>
            <h2>
              {step === 1 && (isChange ? "Change Password" : "Forgot Password")}
              {step === 2 && "Verify OTP"}
              {step === 3 && (isChange ? "Change Password" : "Reset Password")}
            </h2>

            {step === 1 && (
              <form onSubmit={handleEmailSubmit}>
                <p className="fp-description">
                  Enter your email address and we&apos;ll send you an OTP to{" "}
                  {isChange ? "change" : "reset"} your password.
                </p>
                <input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="fp-input"
                />
                {error && <p className="fp-error">{error}</p>}
                <button type="submit" disabled={loading} className="fp-btn">
                  {loading ? "Sending..." : "Send OTP"}
                </button>
                {!onClose && (
                  <p className="fp-footer-link">
                    <Link to="/signin">Back to Login</Link>
                  </p>
                )}
              </form>
            )}

            {step === 2 && (
              <form onSubmit={handleOtpVerify}>
                <p className="fp-description">
                  Enter the 4-digit code sent to <strong>{email}</strong>
                </p>
                <input
                  type="text"
                  maxLength={4}
                  pattern="\d{4}"
                  inputMode="numeric"
                  placeholder="Enter 4-digit OTP"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  required
                  className="fp-input"
                />
                {error && <p className="fp-error">{error}</p>}
                <button
                  type="submit"
                  disabled={loading || otp.length !== 4}
                  className="fp-btn"
                >
                  {loading ? "Verifying..." : "Verify"}
                </button>
                <div className="fp-footer">
                  <p className="fp-timer">Time remaining: {formatTime(timeLeft)}</p>
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resending}
                    className="fp-resend-btn"
                  >
                    {resending ? "Sending..." : "Resend OTP"}
                  </button>
                </div>
              </form>
            )}

            {step === 3 && (
              <form onSubmit={handlePasswordReset}>
                <p className="fp-description">
                  Enter your new password below.
                </p>
                <input
                  type="password"
                  placeholder="New password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="fp-input"
                />
                <input
                  type="password"
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="fp-input"
                />
                {error && <p className="fp-error">{error}</p>}
                <button type="submit" disabled={loading} className="fp-btn">
                  {loading
                    ? isChange
                      ? "Changing..."
                      : "Resetting..."
                    : isChange
                    ? "Change Password"
                    : "Reset Password"}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ForgotPassword;
