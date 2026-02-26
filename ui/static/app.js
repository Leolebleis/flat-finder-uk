/* Flat Finder - app.js */

(function () {
  "use strict";

  const API_BASE = "/flat/api";

  // --- State API ---

  async function updateState(listingId, payload) {
    const resp = await fetch(`${API_BASE}/state/${listingId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      console.error("Failed to update state:", resp.status);
      return null;
    }
    return resp.json();
  }

  // --- Toggle Seen ---

  function initSeenButtons() {
    document.querySelectorAll("[data-action='toggle-seen']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const currentlySeen = btn.dataset.seen === "true";
        const newSeen = !currentlySeen;

        const result = await updateState(id, { seen: newSeen });
        if (!result) return;

        btn.dataset.seen = String(newSeen);
        btn.classList.toggle("btn--seen-active", newSeen);
        btn.textContent = newSeen ? "Seen" : "Mark seen";

        // Update card visual state
        const card = btn.closest(".card");
        if (card) {
          card.dataset.seen = String(newSeen);
          card.classList.toggle("card--seen", newSeen);
        }

        // Update detail page data attribute if on detail page
        const detail = btn.closest("[data-listing-id]");
        if (detail && !card) {
          detail.dataset.seen = String(newSeen);
        }

        applyCurrentFilter();
      });
    });
  }

  // --- Toggle Favourite ---

  function initFavButtons() {
    document.querySelectorAll("[data-action='toggle-fav']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const currentlyFav = btn.dataset.favourite === "true";
        const newFav = !currentlyFav;

        const result = await updateState(id, { favourite: newFav });
        if (!result) return;

        btn.dataset.favourite = String(newFav);
        btn.classList.toggle("btn--fav--active", newFav);

        // Update card data attribute
        const card = btn.closest(".card");
        if (card) {
          card.dataset.favourite = String(newFav);
        }

        // Update detail page data attribute if on detail page
        const detail = btn.closest("[data-listing-id]");
        if (detail && !card) {
          detail.dataset.favourite = String(newFav);
        }

        applyCurrentFilter();
      });
    });
  }

  // --- Notes auto-save ---

  function initNotes() {
    document.querySelectorAll("[data-action='save-notes']").forEach((textarea) => {
      textarea.addEventListener("blur", async () => {
        const id = textarea.dataset.id;
        const notes = textarea.value;
        await updateState(id, { notes: notes });
      });
    });
  }

  // --- Filter buttons ---

  let currentFilter = "all";

  function applyCurrentFilter() {
    document.querySelectorAll(".card").forEach((card) => {
      const seen = card.dataset.seen === "true";
      const fav = card.dataset.favourite === "true";
      let show = true;

      if (currentFilter === "unseen") {
        show = !seen;
      } else if (currentFilter === "favourites") {
        show = fav;
      }

      card.classList.toggle("card--hidden", !show);
    });
  }

  function initFilters() {
    document.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        // Update active button
        document.querySelectorAll("[data-filter]").forEach((b) => {
          b.classList.remove("filter-btn--active");
        });
        btn.classList.add("filter-btn--active");

        currentFilter = btn.dataset.filter;
        applyCurrentFilter();
      });
    });
  }

  // --- Init ---

  document.addEventListener("DOMContentLoaded", () => {
    initSeenButtons();
    initFavButtons();
    initNotes();
    initFilters();
  });
})();
