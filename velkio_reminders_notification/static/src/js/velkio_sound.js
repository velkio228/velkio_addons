/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

/**
 * A short chime generated with the Web Audio API, so the module ships no
 * audio files and nothing has to be downloaded before the first sound.
 */
class VelkioSoundService {
    constructor() {
        this._ctx = null;
    }

    _context() {
        if (!this._ctx) {
            const Ctx = browser.AudioContext || window.webkitAudioContext;
            if (!Ctx) {
                return null;
            }
            this._ctx = new Ctx();
        }
        return this._ctx;
    }

    /** @param {string} level info | warning | urgent */
    play(level) {
        const ctx = this._context();
        if (!ctx) {
            return;
        }
        // Browsers suspend audio until the person interacts with the page.
        if (ctx.state === "suspended") {
            ctx.resume().catch(() => {});
        }
        const tones = {
            info: [[880, 0, 0.28]],
            warning: [[660, 0, 0.22], [880, 0.16, 0.3]],
            urgent: [[740, 0, 0.18], [740, 0.22, 0.18], [740, 0.44, 0.26]],
        }[level] || [[880, 0, 0.28]];

        for (const [frequency, delay, decay] of tones) {
            try {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "sine";
                osc.frequency.setValueAtTime(frequency, ctx.currentTime + delay);
                gain.gain.setValueAtTime(0.0001, ctx.currentTime + delay);
                gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + delay + 0.02);
                gain.gain.exponentialRampToValueAtTime(
                    0.0001, ctx.currentTime + delay + decay
                );
                osc.start(ctx.currentTime + delay);
                osc.stop(ctx.currentTime + delay + decay + 0.05);
            } catch (e) {
                // Never let a sound problem interfere with the popup itself.
                return;
            }
        }
    }
}

registry.category("services").add("velkio_sound", {
    start() {
        return new VelkioSoundService();
    },
});
