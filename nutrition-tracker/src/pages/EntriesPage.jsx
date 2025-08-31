import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

function EntriesPage() {
  const [foodItems, setFoodItems] = useState([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  // 🔹 Fetch with token + refresh handling
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

      // 🔹 If unauthorized, attempt refresh
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

  // 🔹 Fetch all today's entries
  useEffect(() => {
    const fetchEntries = async () => {
      try {
        const res = await fetchWithAuth("http://127.0.0.1:8000/api/entries/today/");
        if (!res.ok) throw new Error("Failed to fetch entries");

        const data = await res.json();

        setFoodItems(data.results || data);

        // ✅ Clear error if data is valid
        if ((data.results && data.results.length > 0) || data.length > 0) {
          setError("");
        }
      } catch (err) {
        setError(err.message);
      }
    };

    fetchEntries();
  }, [fetchWithAuth]);

  return (
    <div className="entries-page">
      {/* Header with back button */}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>Today's Entries</h2>
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

      {/* Error Message */}
      {error && (
        <p
          style={{
            color: "red",
            background: "#fdecea",
            padding: "0.8rem",
            borderRadius: "6px",
            marginTop: "1rem",
          }}
        >
          {error}
        </p>
      )}

      {/* Food Entries */}
      <ul style={{ marginTop: "20px", listStyle: "none", padding: 0 }}>
        {foodItems.length > 0 ? (
          foodItems.map((item) => (
            <li
              key={item.id}
              style={{
                marginBottom: "10px",
                padding: "10px",
                background: "#fff",
                borderRadius: "6px",
                boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
              }}
            >
              <strong>{item.user_input}</strong> → {item.name} —{" "}
              {item.calories.toFixed(1)} kcal ({item.weight_g}g)
            </li>
          ))
        ) : (
          <p>No food items found.</p>
        )}
      </ul>
    </div>
  );
}

export default EntriesPage;
