const byId = (id) => document.getElementById(id);

async function apiCall(url, method = "GET", body = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(url, options);
  const json = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(json));
  return json;
}

function render(id, data) {
  byId(id).textContent = JSON.stringify(data, null, 2);
}

byId("loadPortfolio").onclick = async () => {
  try {
    render("portfolioOutput", await apiCall("/api/portfolio/summary"));
  } catch (err) {
    render("portfolioOutput", { error: err.message });
  }
};

byId("analyzeStock").onclick = async () => {
  const symbol = byId("symbolInput").value || "TCS";
  try {
    render("stockOutput", await apiCall(`/api/stocks/${symbol}/analysis`));
  } catch (err) {
    render("stockOutput", { error: err.message });
  }
};

byId("sendChat").onclick = async () => {
  const query = byId("chatInput").value || "Summarize my portfolio risk";
  try {
    render("chatOutput", await apiCall("/api/chat", "POST", { query }));
  } catch (err) {
    render("chatOutput", { error: err.message });
  }
};

byId("registerDevice").onclick = async () => {
  const payload = {
    user_id: byId("regUserId").value,
    platform: byId("regPlatform").value,
    token: byId("regToken").value,
  };
  try {
    render("registerOutput", await apiCall("/api/notifications/register", "POST", payload));
  } catch (err) {
    render("registerOutput", { error: err.message });
  }
};

byId("sendNotification").onclick = async () => {
  const payload = {
    user_id: byId("notifyUserId").value,
    title: byId("notifyTitle").value || "Portfolio Alert",
    body: byId("notifyBody").value || "Risk threshold reached.",
    data: { source: "web-ui" },
  };
  try {
    render("notifyOutput", await apiCall("/api/notifications/send", "POST", payload));
  } catch (err) {
    render("notifyOutput", { error: err.message });
  }
};
