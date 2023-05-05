const form = document.getElementById("summarize-form");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const text = formData.get("text");
  const response = await fetch("/summary", {
    method: "POST",
    body: new URLSearchParams({ text }),
  });
  const data = await response.json();
  const summary = data.summary;
  const summarySection = document.getElementById("summary-section");
  const summaryText = document.getElementById("summary-text");
  summaryText.innerText = summary;
  summarySection.style.display = "block";
});