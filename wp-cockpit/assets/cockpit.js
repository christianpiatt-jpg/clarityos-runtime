/*
 * SOS Cockpit — operator surface JS.
 *
 * Vanilla. No framework. Loaded with `defer` (the_template enqueues it
 * with the in_footer=true flag). Drives /wp-json/sos/v1/engage and
 * renders the response into the log + ELINS + state panels.
 *
 * Localized globals (set by cockpit-template.php via wp_localize_script):
 *   sosCockpit.restRoot — e.g. "https://pro-mediations.com/wp-json/sos/v1"
 *   sosCockpit.nonce    — WP REST nonce for X-WP-Nonce header
 *   sosCockpit.user     — { id, display_name }
 */
(function () {
	"use strict";

	if (typeof window.sosCockpit !== "object" || !window.sosCockpit.restRoot) {
		// Template misconfigured (assets enqueued without localize).
		console.warn("[sos-cockpit] sosCockpit bootstrap missing; aborting.");
		return;
	}

	var log    = document.getElementById("sos-log");
	var form   = document.getElementById("sos-form");
	var input  = document.getElementById("sos-input");
	var send   = document.getElementById("sos-send");
	var status = document.getElementById("sos-status");
	var banner = document.getElementById("sos-banner");
	var elinsBox = document.getElementById("sos-elins");
	var stateBox = document.getElementById("sos-state");

	if (!form || !input || !log) {
		console.warn("[sos-cockpit] required DOM nodes not found; aborting.");
		return;
	}

	// ----------------------------------------------------------------------
	// Banner + status
	// ----------------------------------------------------------------------
	function showBanner(text) {
		if (!banner) return;
		banner.textContent = text;
		banner.hidden = false;
	}
	function clearBanner() {
		if (!banner) return;
		banner.hidden = true;
		banner.textContent = "";
	}
	function setStatus(text) {
		if (status) {
			status.textContent = text || "";
		}
	}

	// ----------------------------------------------------------------------
	// Log rendering
	// ----------------------------------------------------------------------
	function appendBubble(role, text) {
		var row = document.createElement("div");
		row.className = "sos-bubble sos-bubble-" + role;

		var tag = document.createElement("span");
		tag.className = "sos-bubble-tag";
		tag.textContent = role === "operator" ? "You" : "SOS";
		row.appendChild(tag);

		var body = document.createElement("span");
		body.className = "sos-bubble-body";
		body.textContent = text;
		row.appendChild(body);

		log.appendChild(row);
		log.scrollTop = log.scrollHeight;
	}

	function setPanel(node, obj) {
		if (!node) return;
		if (obj === null || obj === undefined) {
			node.textContent = "(no data)";
			return;
		}
		try {
			node.textContent = JSON.stringify(obj, null, 2);
		} catch (e) {
			node.textContent = String(obj);
		}
	}

	// ----------------------------------------------------------------------
	// Network
	// ----------------------------------------------------------------------
	function postEngage(message) {
		return fetch(window.sosCockpit.restRoot + "/engage", {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				"X-WP-Nonce":   window.sosCockpit.nonce
			},
			body: JSON.stringify({ message: message })
		}).then(function (res) {
			return res.json().then(function (body) {
				return { status: res.status, ok: res.ok, body: body };
			}).catch(function () {
				return { status: res.status, ok: res.ok, body: null };
			});
		});
	}

	// ----------------------------------------------------------------------
	// Submit handler
	// ----------------------------------------------------------------------
	function submit() {
		var message = (input.value || "").trim();
		if (!message) {
			input.focus();
			return;
		}
		clearBanner();
		setStatus("Sending…");
		send.disabled = true;
		input.disabled = true;

		appendBubble("operator", message);

		postEngage(message).then(function (result) {
			send.disabled  = false;
			input.disabled = false;

			if (!result.ok) {
				var msg = (result.body && (result.body.message || result.body.error))
					? (result.body.message || result.body.error)
					: ("HTTP " + result.status);
				showBanner("Send failed: " + msg);
				setStatus("");
				input.focus();
				return;
			}

			var data = result.body || {};
			var reply = typeof data.reply === "string" ? data.reply : "(empty reply)";
			appendBubble("sos", reply);
			setPanel(elinsBox, data.elins || {});
			setPanel(stateBox, data.state || {});
			setStatus("");
			input.value = "";
			input.focus();
		}).catch(function (err) {
			send.disabled  = false;
			input.disabled = false;
			showBanner("Network error: " + (err && err.message ? err.message : String(err)));
			setStatus("");
		});
	}

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		submit();
	});

	// Cmd/Ctrl+Enter also submits.
	input.addEventListener("keydown", function (e) {
		if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			submit();
		}
	});
})();
