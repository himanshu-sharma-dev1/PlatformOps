/* ============================================================
 * theme.js — light/dark theme toggle for Iktara / YantrAI pages
 *
 * Two responsibilities:
 *   1. Apply the correct theme as early as possible to avoid FOUC.
 *      The inline init snippet (see theme-README.md) does this in the
 *      <head> before stylesheets load.
 *   2. Wire up any .theme-toggle button(s) on the page so clicking
 *      flips the theme, persists the choice, and animates smoothly.
 *
 * State resolution (first match wins):
 *   1. localStorage 'iktara-theme' if set ('light' or 'dark')
 *   2. window.matchMedia('(prefers-color-scheme: dark)')
 *   3. light
 *
 * Storage key is namespaced so it doesn't collide with other apps on
 * the same domain in dev.
 * ============================================================ */

/* global localStorage, CustomEvent, window, document */
(function () {
    'use strict';

    const STORAGE_KEY = 'iktara-theme';
    const VALID_THEMES = ['light', 'dark'];

    function getStoredTheme () {
        try {
            const v = localStorage.getItem(STORAGE_KEY);
            return VALID_THEMES.includes(v) ? v : null;
        } catch {
            return null;
        }
    }

    function setStoredTheme (theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch {
            /* noop */
        }
    }

    function systemPrefersDark () {
        return (
            typeof window.matchMedia === 'function' &&
            window.matchMedia('(prefers-color-scheme: dark)').matches
        );
    }

    function applyTheme (theme, animate) {
        const root = document.documentElement;
        if (animate) {
            root.classList.add('theme-transitioning');
            window.setTimeout(
                () => root.classList.remove('theme-transitioning'),
                220,
            );
        }
        root.setAttribute('data-theme', theme);

        document.querySelectorAll('.theme-toggle').forEach((btn) => {
            const next = theme === 'dark' ? 'light' : 'dark';
            btn.setAttribute('aria-label', `Switch to ${next} theme`);
            btn.setAttribute('title', `Switch to ${next} theme`);
        });

        window.dispatchEvent(
            new CustomEvent('iktara:themechange', {
                detail: { theme },
            }),
        );
    }

    function toggleTheme () {
        const current =
            document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        setStoredTheme(next);
        applyTheme(next, true);
    }

    function wireToggleButtons () {
        document.querySelectorAll('.theme-toggle').forEach((btn) => {
            if (btn.dataset.themeWired === '1') return;
            btn.dataset.themeWired = '1';
            btn.addEventListener('click', toggleTheme);
        });
    }

    function watchSystemPreference () {
        if (typeof window.matchMedia !== 'function') return;
        const mql = window.matchMedia('(prefers-color-scheme: dark)');
        const handler = (e) => {
            if (getStoredTheme()) return;
            applyTheme(e.matches ? 'dark' : 'light', true);
        };
        if (mql.addEventListener) mql.addEventListener('change', handler);
        else if (mql.addListener) mql.addListener(handler);
    }

    function init () {
        wireToggleButtons();
        watchSystemPreference();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.IktaraTheme = {
        get current () {
            return (
                document.documentElement.getAttribute('data-theme') || 'light'
            );
        },
        set (theme) {
            if (!VALID_THEMES.includes(theme)) return;
            setStoredTheme(theme);
            applyTheme(theme, true);
        },
        toggle: toggleTheme,
        reset () {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch {}
            applyTheme(systemPrefersDark() ? 'dark' : 'light', true);
        },
    };
})();
