import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Pie } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend, Title } from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend, Title);

function Dashboard() {
  const [foodItems, setFoodItems] = useState([]);
  const [todaySummary, setTodaySummary] = useState(null);
  const [error, setError] = useState("");
  const [foodName, setFoodName] = useState("");
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const navigate = useNavigate();

  // 🔹 Fetch with token
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

  // 🔹 Fetch today's entries + summary
  const fetchData = useCallback(async () => {
    try {
      const [entriesRes, summaryRes] = await Promise.all([
        fetchWithAuth("http://127.0.0.1:8000/api/entries/today/"),
        fetchWithAuth("http://127.0.0.1:8000/api/entries/today-summary/"),
      ]);

      if (!entriesRes.ok || !summaryRes.ok) {
        throw new Error("Failed to fetch data");
      }

      const entriesData = await entriesRes.json();
      const summaryData = await summaryRes.json();

      setFoodItems(entriesData.results || entriesData);
      setTodaySummary(summaryData);
    } catch (err) {
      setError(err.message);
    }
  }, [fetchWithAuth]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 🔹 Log food
  const handleLogFood = async (e) => {
    e.preventDefault();

    try {
      const response = await fetchWithAuth(
        "http://127.0.0.1:8000/api/log-food/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: foodName }),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to log food");
      }

      setFoodName("");
      setError("");
      fetchData();
    } catch (err) {
      setError(err.message);
    }
  };

  // 🔹 Logout
  const confirmLogout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    navigate("/");
  };

  // 🔹 Chart data
  const chartData = todaySummary
    ? {
        labels: ["Carbs (g)", "Protein (g)", "Fat (g)"],
        datasets: [
          {
            label: "Macros Breakdown",
            data: [
              todaySummary.total_carbs_g || 0,
              todaySummary.total_protein_g || 0,
              todaySummary.total_fat_g || 0,
            ],
            backgroundColor: ["#3498db", "#2ecc71", "#e74c3c"],
            borderWidth: 1,
          },
        ],
      }
    : null;

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: { position: "bottom" },
      title: { display: true, text: "Today's Macros Distribution" },
    },
  };

  const latestEntries = foodItems.slice(0, 4);

  return (
    <div className="dashboard-container">
      {/* Header */}
      <div className="dashboard-header">
        <h2>Dashboard</h2>
        <div className="header-buttons">
          <button onClick={() => navigate("/summaries")} className="btn green">
            Daily Summaries
          </button>
          <button onClick={() => setShowLogoutModal(true)} className="btn red">
            Logout
          </button>
        </div>
      </div>

      {/* Error */}
      {error && <p className="error-message">{error}</p>}

      {/* Log food */}
      <form onSubmit={handleLogFood} className="log-food-form">
        <input
          type="text"
          placeholder="Enter food (e.g. 2 eggs)"
          value={foodName}
          onChange={(e) => {
            setFoodName(e.target.value);
            setError("");
          }}
          required
          className="food-input"
        />
         <button type="submit" className="btn blue"> Log Food</button>
      </form>

      {/* Entries */}
      <div className="card">
        <h3>Today's Latest Entries</h3>
        <ul>
          {latestEntries.length > 0 ? (
            latestEntries.map((item) => (
              <li key={item.id}>
                <strong>{item.user_input}</strong> {item.name} —{" "}
                {item.calories.toFixed(1)} kcal ({item.weight_g}g)
              </li>
            ))
          ) : (
            <p>No food items found.</p>
          )}
        </ul>

        {foodItems.length > 4 && (
          <p onClick={() => navigate("/entries")} className="see-more">
            See All...
          </p>
        )}
      </div>

      {/* Summary + Chart */}
      {todaySummary && (
        <div className="card">
          <h3>Today's Summary</h3>
          <p>Calories: {todaySummary.total_calories.toFixed(1)} kcal</p>
          <p>Carbs: {todaySummary.total_carbs_g.toFixed(1)} g</p>
          <p>Protein: {todaySummary.total_protein_g.toFixed(1)} g</p>
          <p>Fat: {todaySummary.total_fat_g.toFixed(1)} g</p>

          {chartData && <Pie data={chartData} options={chartOptions} />}
        </div>
      )}

      {/* Logout Modal */}
      {showLogoutModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Are you sure?</h3>
            <p>You will be logged out of your account.</p>
            <div className="modal-actions">
              <button onClick={confirmLogout} className="btn red">
                Yes, Logout
              </button>
              <button
                onClick={() => setShowLogoutModal(false)}
                className="btn gray"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
