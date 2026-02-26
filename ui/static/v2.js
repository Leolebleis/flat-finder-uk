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
    var cards = Array.from(document.querySelectorAll(".listing-card[data-commute-mins]"));
    var commutes = [];
    var gyms = [];

    cards.forEach(function (c) {
      var cm = c.dataset.commuteMins;
      var gd = c.dataset.gymCommute;
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
      var gd = c.dataset.gymCommute;
      var cScore = cm !== "" ? 100 * (1 - (parseFloat(cm) - cMin) / cRange) : 0;
      var gScore = gd !== "" ? 100 * (1 - (parseFloat(gd) - gMin) / gRange) : 0;
      var score = Math.round(wCommute * cScore + wGym * gScore);
      c.dataset.matchScore = score;
      var badge = c.querySelector(".metric--score");
      if (badge) badge.textContent = score;
    });

    // Re-sort cards in DOM
    var grid = document.querySelector(".listing-grid");
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
  });
})();
