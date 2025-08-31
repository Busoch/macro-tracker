import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

function SummariesPage() {
  const [summaries, setSummaries] = useState([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  // Reuse authenticated fetch
  const fetchWithAuth = useCallback(
    async (url, options = {}) => {
      let token = localStorage.getItem("access");

      let res = await fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        const refresh = localStorage.getItem("refresh");
        if (!refresh) {
          navigate("/");
          return res;
        }

        const refreshRes = await fetch(
          "http://127.0.0.1:8000/api/token/refresh/",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh }),
          }
        );

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          localStorage.setItem("access", data.access);

          res = await fetch(url, {
            ...options,
            headers: {
              "Content-Type": "application/json",
              ...options.headers,
              Authorization: `Bearer ${data.access}`,
            },
          });
        } else {
          navigate("/");
        }
      }

      return res;
    },
    [navigate]
  );

  useEffect(() => {
    const fetchSummaries = async () => {
      try {
        const res = await fetchWithAuth(
          "http://127.0.0.1:8000/api/entries/daily-summaries/"
        );
        if (!res.ok) throw new Error("Failed to fetch summaries");

        const data = await res.json();
        setSummaries(data);
      } catch (err) {
        setError(err.message);
      }
    };

    fetchSummaries();
  }, [fetchWithAuth]);

  return (
    <div className="summaries-page">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>Daily Macro Summaries</h2>
        <button
          onClick={() => navigate("/dashboard")}
          style={{
            background: "#3498db",
            color: "white",
            border: "none",
            borderRadius: "5px",
            padding: "6px 12px",
            cursor: "pointer",
          }}
        >
          Back to Dashboard
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {summaries.length > 0 ? (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            marginTop: "20px",
          }}
        >
          <thead>
            <tr>
              <th style={{ borderBottom: "1px solid #ccc", padding: "8px" }}>
                Date
              </th>
              <th style={{ borderBottom: "1px solid #ccc", padding: "8px" }}>
                Calories
              </th>
              <th style={{ borderBottom: "1px solid #ccc", padding: "8px" }}>
                Protein (g)
              </th>
              <th style={{ borderBottom: "1px solid #ccc", padding: "8px" }}>
                Carbs (g)
              </th>
              <th style={{ borderBottom: "1px solid #ccc", padding: "8px" }}>
                Fat (g)
              </th>
            </tr>
          </thead>
          <tbody>
            {summaries.map((s, idx) => (
              <tr key={idx}>
                <td style={{ borderBottom: "1px solid #eee", padding: "8px" }}>
                  {s.date}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "8px" }}>
                  {s.total_calories?.toFixed(1)}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "8px" }}>
                  {s.total_protein?.toFixed(1)}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "8px" }}>
                  {s.total_carbs?.toFixed(1)}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "8px" }}>
                  {s.total_fat?.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p style={{ marginTop: "20px" }}>No summaries found.</p>
      )}
    </div>
  );
}

export default SummariesPage;
