/**
 * Layout (grid/list), density, section order (localStorage), and Sortable link lists.
 * Requires Sortable (global Sortable) loaded before this script.
 */
(function () {
    var STORAGE_LAYOUT = "aggregator.layout";
    var STORAGE_DENSITY = "aggregator.density";
    var STORAGE_SECTIONS = "aggregator.sectionOrder";

    function getJSON(key, fallback) {
        try {
            var raw = localStorage.getItem(key);
            if (!raw) return fallback;
            return JSON.parse(raw);
        } catch (e) {
            return fallback;
        }
    }

    function setLayoutDensity(root) {
        var layout = localStorage.getItem(STORAGE_LAYOUT) || "grid";
        var density = localStorage.getItem(STORAGE_DENSITY) || "comfortable";
        if (layout !== "grid" && layout !== "list") layout = "grid";
        if (["compact", "comfortable", "spacious"].indexOf(density) === -1) {
            density = "comfortable";
        }
        root.dataset.layout = layout;
        root.dataset.density = density;
    }

    function syncLayoutButtons(root) {
        var layout = root.dataset.layout || "grid";
        var density = root.dataset.density || "comfortable";
        root.querySelectorAll("[data-layout-set]").forEach(function (btn) {
            var v = btn.getAttribute("data-layout-set");
            btn.setAttribute("aria-pressed", v === layout ? "true" : "false");
            btn.classList.toggle("ring-2", v === layout);
            btn.classList.toggle("ring-amber-500/60", v === layout);
        });
        root.querySelectorAll("[data-density-set]").forEach(function (btn) {
            var v = btn.getAttribute("data-density-set");
            btn.setAttribute("aria-pressed", v === density ? "true" : "false");
            btn.classList.toggle("ring-2", v === density);
            btn.classList.toggle("ring-amber-500/60", v === density);
        });
    }

    function applySectionOrder() {
        var container = document.getElementById("platform-sections");
        if (!container) return;
        var order = getJSON(STORAGE_SECTIONS, []);
        if (!order.length) return;
        var sections = Array.from(container.children).filter(function (el) {
            return el.classList && el.classList.contains("platform-section");
        });
        var byPlat = {};
        sections.forEach(function (s) {
            byPlat[s.dataset.platform] = s;
        });
        var seen = new Set();
        order.forEach(function (p) {
            if (byPlat[p]) {
                container.appendChild(byPlat[p]);
                seen.add(p);
            }
        });
        sections.forEach(function (s) {
            if (!seen.has(s.dataset.platform)) {
                container.appendChild(s);
            }
        });
    }

    function initLayoutControls(root) {
        root.addEventListener("click", function (e) {
            var t = e.target;
            if (!(t instanceof Element)) return;
            var layoutBtn = t.closest("[data-layout-set]");
            if (layoutBtn) {
                localStorage.setItem(STORAGE_LAYOUT, layoutBtn.getAttribute("data-layout-set") || "grid");
                setLayoutDensity(root);
                syncLayoutButtons(root);
                return;
            }
            var densityBtn = t.closest("[data-density-set]");
            if (densityBtn) {
                localStorage.setItem(STORAGE_DENSITY, densityBtn.getAttribute("data-density-set") || "comfortable");
                setLayoutDensity(root);
                syncLayoutButtons(root);
            }
        });
    }

    function initLinkSortables() {
        if (typeof Sortable === "undefined") return;
        document.querySelectorAll(".sortable-link-list").forEach(function (ul) {
            var platform = ul.dataset.platform;
            if (!platform) return;
            new Sortable(ul, {
                animation: 160,
                delay: 180,
                delayOnTouchOnly: true,
                touchStartThreshold: 6,
                handle: ".drag-handle",
                draggable: ".link-card-item",
                forceFallback: true,
                fallbackTolerance: 4,
                onEnd: function () {
                    var ids = Array.from(ul.querySelectorAll(".link-card-item")).map(function (li) {
                        return parseInt(li.getAttribute("data-link-id"), 10);
                    });
                    fetch("/links/reorder", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            Accept: "application/json",
                        },
                        body: JSON.stringify({ platform: platform, ids: ids }),
                    })
                        .then(function (r) {
                            if (!r.ok) {
                                return r.text().then(function (t) {
                                    throw new Error(t || r.statusText);
                                });
                            }
                        })
                        .catch(function (err) {
                            console.error(err);
                            window.location.reload();
                        });
                },
            });
        });
    }

    function initSectionSortable() {
        if (typeof Sortable === "undefined") return;
        var container = document.getElementById("platform-sections");
        if (!container || container.children.length < 2) return;
        new Sortable(container, {
            animation: 160,
            delay: 220,
            delayOnTouchOnly: true,
            touchStartThreshold: 6,
            handle: ".section-drag-handle",
            draggable: ".platform-section",
            forceFallback: true,
            onEnd: function () {
                var order = Array.from(container.querySelectorAll(".platform-section")).map(function (s) {
                    return s.dataset.platform;
                });
                localStorage.setItem(STORAGE_SECTIONS, JSON.stringify(order));
            },
        });
    }

    function init() {
        var root = document.getElementById("feed-root");
        if (!root) return;
        setLayoutDensity(root);
        syncLayoutButtons(root);
        applySectionOrder();
        initLayoutControls(root);
        initLinkSortables();
        initSectionSortable();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
