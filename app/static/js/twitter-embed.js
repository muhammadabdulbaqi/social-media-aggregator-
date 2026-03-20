/**
 * Initialize Twitter/X embeds after DOM is ready.
 * Load this only on pages that render Twitter oEmbed HTML.
 */
(function () {
    function init() {
        if (window.twttr && window.twttr.widgets && typeof window.twttr.widgets.load === 'function') {
            window.twttr.widgets.load();
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
