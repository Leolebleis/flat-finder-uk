/* Flat Finder v2 - app.js */

(function () {
  "use strict";

  var API_BASE = "/flat/api";

  // --- State API ---

  async function updateState(listingId, payload) {
    var resp = await fetch(API_BASE + "/state/" + listingId, {
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
    document.querySelectorAll("[data-action='toggle-seen']").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.dataset.id;
        var currentlySeen = btn.dataset.seen === "true";
        var newSeen = !currentlySeen;

        var result = await updateState(id, { seen: newSeen });
        if (!result) return;

        btn.dataset.seen = String(newSeen);
        btn.classList.toggle("btn-seen--active", newSeen);
        btn.classList.toggle("btn-action--active", newSeen);

        // Update button text on detail page
        var textNode = btn.childNodes[btn.childNodes.length - 1];
        if (textNode && textNode.nodeType === 3) {
          textNode.textContent = newSeen ? " Seen" : " Mark seen";
        }
        btn.title = newSeen ? "Seen" : "Mark as seen";

        // Update card visual state
        var card = btn.closest(".listing-card");
        if (card) {
          card.dataset.seen = String(newSeen);
          card.classList.toggle("listing-card--seen", newSeen);
        }

        // Update detail page data attribute
        var detail = btn.closest("[data-listing-id]");
        if (detail && !card) {
          detail.dataset.seen = String(newSeen);
        }

        applyCurrentFilter();
      });
    });
  }

  // --- Toggle Favourite ---

  function initFavButtons() {
    document.querySelectorAll("[data-action='toggle-fav']").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.dataset.id;
        var currentlyFav = btn.dataset.favourite === "true";
        var newFav = !currentlyFav;

        var result = await updateState(id, { favourite: newFav });
        if (!result) return;

        btn.dataset.favourite = String(newFav);

        // Feed card fav button
        btn.classList.toggle("listing-card__fav--active", newFav);
        // Detail page fav button
        btn.classList.toggle("btn-action--fav-active", newFav);

        // Update button text on detail page
        var textNode = btn.childNodes[btn.childNodes.length - 1];
        if (textNode && textNode.nodeType === 3) {
          textNode.textContent = newFav ? " Saved" : " Save";
        }

        // Update card data attribute
        var card = btn.closest(".listing-card");
        if (card) {
          card.dataset.favourite = String(newFav);
        }

        // Update detail page data attribute
        var detail = btn.closest("[data-listing-id]");
        if (detail && !card) {
          detail.dataset.favourite = String(newFav);
        }

        applyCurrentFilter();
      });
    });
  }

  // --- Notes auto-save ---

  function initNotes() {
    document.querySelectorAll("[data-action='save-notes']").forEach(function (textarea) {
      textarea.addEventListener("blur", async function () {
        var id = textarea.dataset.id;
        var notes = textarea.value;
        await updateState(id, { notes: notes });
      });
    });
  }

  // --- Filter buttons ---

  var currentFilter = "all";

  function applyCurrentFilter() {
    document.querySelectorAll(".listing-card").forEach(function (card) {
      var seen = card.dataset.seen === "true";
      var fav = card.dataset.favourite === "true";
      var show = true;

      if (currentFilter === "unseen") {
        show = !seen;
      } else if (currentFilter === "favourites") {
        show = fav;
      }

      card.classList.toggle("listing-card--hidden", !show);
    });
  }

  function initFilters() {
    document.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll("[data-filter]").forEach(function (b) {
          b.classList.remove("seg-control__btn--active");
        });
        btn.classList.add("seg-control__btn--active");

        currentFilter = btn.dataset.filter;
        applyCurrentFilter();
      });
    });
  }

  // --- Weight sliders & scoring ---

  function initWeightSliders() {
    var sliders = document.querySelectorAll(".poi-weight-slider");
    if (!sliders.length) return;

    sliders.forEach(function (slider) {
      var valEl = document.getElementById(slider.id + "-val");
      slider.addEventListener("input", function () {
        if (valEl) valEl.textContent = slider.value + "%";
        recalcScores();
      });
    });
  }

  function recalcScores() {
    var sliders = document.querySelectorAll(".poi-weight-slider");
    if (!sliders.length) return;

    var weights = {};
    var totalWeight = 0;
    sliders.forEach(function (s) {
      var w = parseInt(s.value, 10);
      weights[s.dataset.poiId] = w;
      totalWeight += w;
    });
    if (totalWeight === 0) totalWeight = 1;

    var cards = Array.from(document.querySelectorAll(".listing-card"));
    if (!cards.length) return;

    // Collect min/max per POI across all cards
    var stats = {};
    Object.keys(weights).forEach(function (pid) {
      var vals = [];
      cards.forEach(function (c) {
        var v = c.dataset["poi" + pid];
        if (v !== undefined && v !== "") vals.push(parseFloat(v));
      });
      if (vals.length) {
        var mn = Math.min.apply(null, vals);
        var mx = Math.max.apply(null, vals);
        stats[pid] = { min: mn, max: mx, range: mx !== mn ? mx - mn : 1 };
      }
    });

    cards.forEach(function (c) {
      var score = 0;
      Object.keys(weights).forEach(function (pid) {
        var v = c.dataset["poi" + pid];
        if (v !== undefined && v !== "" && stats[pid]) {
          var s = stats[pid];
          var normalized = 100 * (1 - (parseFloat(v) - s.min) / s.range);
          score += (weights[pid] / totalWeight) * normalized;
        }
      });
      score = Math.round(score);
      c.dataset.matchScore = score;
      var badge = c.querySelector(".metric--score");
      if (badge) badge.textContent = score;
    });

    // Re-sort cards by score
    var grid = document.querySelector(".listing-grid");
    if (!grid) return;
    cards.sort(function (a, b) {
      return parseInt(b.dataset.matchScore, 10) - parseInt(a.dataset.matchScore, 10);
    });
    cards.forEach(function (c) { grid.appendChild(c); });
  }

  // --- Delete POI ---

  function initDeletePoi() {
    document.querySelectorAll("[data-action='delete-poi']").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.dataset.id;
        var resp = await fetch("/flat/settings/poi/" + id, {
          method: "DELETE",
        });
        if (resp.ok) {
          btn.closest(".settings__poi").remove();
        }
      });
    });
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
          pill.className = "pill pill--" + original;
          pill.textContent = PILL_LABELS[field][original];
        } else {
          var next = PILL_CYCLE[idx + 1];
          var payload = {};
          payload[field] = next;
          var result = await updateState(id, payload);
          if (!result) return;
          pill.dataset.value = next;
          pill.className = "pill pill--" + next + " pill--overridden";
          pill.textContent = PILL_LABELS[field][next];
        }
      });
    });
  }

  // --- Init ---

  document.addEventListener("DOMContentLoaded", function () {
    initSeenButtons();
    initFavButtons();
    initNotes();
    initFilters();
    initWeightSliders();
    initPillCycling();
    initDeletePoi();
  });
})();
