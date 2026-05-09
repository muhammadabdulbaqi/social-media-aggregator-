/**
 * Feed UI: layout/density (localStorage), section order (localStorage),
 * view mode + unified sort (cookies + reload).
 * Sortable lists run only while settings are open so hidden fallback layers cannot cover the feed.
 */
(function () {
    var STORAGE_LAYOUT = "aggregator.layout";
    var STORAGE_DENSITY = "aggregator.density";
    var STORAGE_SECTIONS = "aggregator.sectionOrder";
    var COOKIE_VIEW = "aggregator_view";
    var COOKIE_UNIFIED_SORT = "aggregator_unified_sort";
    var COOKIE_MAX_AGE = 31536000;

    var linkSortables = [];
    var sectionSortableInstance = null;

    function setCookie(name, value) {
        document.cookie =
            encodeURIComponent(name) +
            "=" +
            encodeURIComponent(value) +
            ";path=/;max-age=" +
            COOKIE_MAX_AGE +
            ";SameSite=Lax";
    }

    function getJSON(key, fallback) {
        try {
            var raw = localStorage.getItem(key);
            if (!raw) return fallback;
            return JSON.parse(raw);
        } catch (e) {
            return fallback;
        }
    }

    function destroySortables() {
        linkSortables.forEach(function (s) {
            try {
                s.destroy();
            } catch (e) {
                /* noop */
            }
        });
        linkSortables = [];
        if (sectionSortableInstance) {
            try {
                sectionSortableInstance.destroy();
            } catch (e) {
                /* noop */
            }
            sectionSortableInstance = null;
        }
    }

    function ensureSortables(root) {
        if (typeof Sortable === "undefined") return;
        destroySortables();

        document.querySelectorAll(".sortable-link-list").forEach(function (ul) {
            var platform = ul.dataset.platform;
            if (!platform || platform === "__unified__") return;
            var instance = new Sortable(ul, {
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
            linkSortables.push(instance);
        });

        if (root.dataset.viewMode === "unified") return;

        var container = document.getElementById("platform-sections");
        if (!container || container.children.length < 2) return;

        sectionSortableInstance = new Sortable(container, {
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

    function syncViewModeButtons(root) {
        var mode = root.dataset.viewMode || "platform";
        var sort = root.dataset.unifiedSort || "recent";
        root.querySelectorAll("[data-view-set]").forEach(function (btn) {
            var v = btn.getAttribute("data-view-set");
            btn.setAttribute("aria-pressed", v === mode ? "true" : "false");
            btn.classList.toggle("ring-2", v === mode);
            btn.classList.toggle("ring-amber-500/60", v === mode);
        });
        root.querySelectorAll("[data-unified-sort-set]").forEach(function (btn) {
            var v = btn.getAttribute("data-unified-sort-set");
            btn.setAttribute("aria-pressed", v === sort ? "true" : "false");
            btn.classList.toggle("ring-2", v === sort);
            btn.classList.toggle("ring-amber-500/60", v === sort);
        });

        var uf = root.querySelector(".unified-sort-fieldset");
        if (uf) {
            uf.classList.toggle("opacity-50", mode !== "unified");
        }
    }

    function applySectionOrder() {
        var root = document.getElementById("feed-root");
        if (root && root.dataset.viewMode === "unified") return;

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

    function initFeedSettingsToggle(root) {
        var btn = document.getElementById("feed-settings-toggle");
        if (!btn) return;

        function apply(open) {
            root.classList.toggle("feed-settings-visible", open);
            btn.setAttribute("aria-expanded", open ? "true" : "false");
            if (open) {
                requestAnimationFrame(function () {
                    ensureSortables(root);
                });
            } else {
                destroySortables();
            }
        }

        btn.addEventListener("click", function () {
            apply(!root.classList.contains("feed-settings-visible"));
        });

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && root.classList.contains("feed-settings-visible")) {
                apply(false);
                btn.focus();
            }
        });
    }

    function initViewCookieControls(root) {
        root.querySelectorAll("[data-view-set]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var v = btn.getAttribute("data-view-set");
                if (!v || v === root.dataset.viewMode) return;
                setCookie(COOKIE_VIEW, v);
                window.location.reload();
            });
        });
        root.querySelectorAll("[data-unified-sort-set]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var v = btn.getAttribute("data-unified-sort-set");
                if (!v || v === root.dataset.unifiedSort) return;
                setCookie(COOKIE_UNIFIED_SORT, v);
                window.location.reload();
            });
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

    function init() {
        var root = document.getElementById("feed-root");
        if (!root) return;
        setLayoutDensity(root);
        syncLayoutButtons(root);
        syncViewModeButtons(root);
        applySectionOrder();
        initFeedSettingsToggle(root);
        initViewCookieControls(root);
        initLayoutControls(root);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
