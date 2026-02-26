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

  // --- Weight sliders & scoring ---

  function initWeightSliders() {
    var commuteSlider = document.getElementById("w-commute");
    var gymSlider = document.getElementById("w-gym");
    if (!commuteSlider || !gymSlider) return;

    var commuteVal = document.getElementById("w-commute-val");
    var gymVal = document.getElementById("w-gym-val");

    function syncSliders(source) {
      var v = parseInt(source.value, 10);
      if (source === commuteSlider) {
        gymSlider.value = 100 - v;
      } else {
        commuteSlider.value = 100 - v;
      }
      commuteVal.textContent = commuteSlider.value + "%";
      gymVal.textContent = gymSlider.value + "%";
      recalcScores(parseInt(commuteSlider.value, 10) / 100, parseInt(gymSlider.value, 10) / 100);
    }

    commuteSlider.addEventListener("input", function () { syncSliders(commuteSlider); });
    gymSlider.addEventListener("input", function () { syncSliders(gymSlider); });
  }

  function recalcScores(wCommute, wGym) {
    var cards = Array.from(document.querySelectorAll(".card[data-commute-mins]"));
    var commutes = [];
    var gyms = [];

    cards.forEach(function (c) {
      var cm = c.dataset.commuteMins;
      var gd = c.dataset.gymDistance;
      if (cm !== "") commutes.push(parseFloat(cm));
      if (gd !== "") gyms.push(parseFloat(gd));
    });

    if (commutes.length === 0 && gyms.length === 0) return;

    var cMin = Math.min.apply(null, commutes), cMax = Math.max.apply(null, commutes);
    var gMin = Math.min.apply(null, gyms), gMax = Math.max.apply(null, gyms);
    var cRange = cMax !== cMin ? cMax - cMin : 1;
    var gRange = gMax !== gMin ? gMax - gMin : 1;

    cards.forEach(function (c) {
      var cm = c.dataset.commuteMins;
      var gd = c.dataset.gymDistance;
      var cScore = cm !== "" ? 100 * (1 - (parseFloat(cm) - cMin) / cRange) : 0;
      var gScore = gd !== "" ? 100 * (1 - (parseFloat(gd) - gMin) / gRange) : 0;
      var score = Math.round(wCommute * cScore + wGym * gScore);
      c.dataset.matchScore = score;
      var badge = c.querySelector(".meta-badge--score");
      if (badge) badge.textContent = score + " score";
    });

    // Re-sort cards in DOM
    var grid = document.querySelector(".card-grid");
    if (!grid) return;
    cards.sort(function (a, b) {
      return parseInt(b.dataset.matchScore, 10) - parseInt(a.dataset.matchScore, 10);
    });
    cards.forEach(function (c) { grid.appendChild(c); });
  }

  // --- Clickable feature pills ---

  var PILL_CYCLE = ["yes", "no", "unknown"];
  var PILL_LABELS = {
    override_dishwasher: { yes: "Dishwasher", no: "No dishwasher", unknown: "Dishwasher?" },
    override_washer: { yes: "Washer", no: "No washer", unknown: "Washer?" },
    override_outdoor: { yes: "Outdoor", no: "No outdoor", unknown: "Outdoor?" },
  };

  function initPillCycling() {
    document.querySelectorAll("[data-action='cycle-pill']").forEach(function (pill) {
      pill.style.cursor = "pointer";
      pill.addEventListener("click", async function () {
        var current = pill.dataset.value;
        var idx = PILL_CYCLE.indexOf(current);
        var field = pill.dataset.field;
        var id = pill.dataset.id;

        // 4-state cycle: yes -> no -> unknown -> revert (clear override)
        var isLastState = idx === PILL_CYCLE.length - 1;
        if (isLastState) {
          // Clear override, revert to scraped value
          var payload = {};
          payload[field] = null;
          var result = await updateState(id, payload);
          if (!result) return;
          var original = pill.dataset.original;
          pill.dataset.value = original;
          pill.className = "feature-pill feature-pill--" + original;
          pill.textContent = PILL_LABELS[field][original];
        } else {
          var next = PILL_CYCLE[idx + 1];
          var payload = {};
          payload[field] = next;
          var result = await updateState(id, payload);
          if (!result) return;
          pill.dataset.value = next;
          pill.className = "feature-pill feature-pill--" + next + " feature-pill--overridden";
          pill.textContent = PILL_LABELS[field][next];
        }
      });
    });
  }

  // --- Init ---

  document.addEventListener("DOMContentLoaded", () => {
    initSeenButtons();
    initFavButtons();
    initNotes();
    initFilters();
    initWeightSliders();
    initPillCycling();
  });
})();
