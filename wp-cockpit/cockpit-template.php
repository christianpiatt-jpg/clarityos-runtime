<?php
/**
 * Template Name: SOS Cockpit
 *
 * WordPress page template that renders the SOS cockpit surface.
 * Drop this file into the active theme (or a child theme) and assign
 * the template to a page (e.g. ``/cockpit``) via the WordPress page
 * editor's Template selector.
 *
 * The template:
 *   * Requires the visitor to be logged in (redirects to wp-login.php
 *     otherwise, returning here post-login).
 *   * Enqueues vanilla cockpit JS + CSS — no React, no framework.
 *   * Localises a small bootstrap object (REST root + nonce + cockpit
 *     identity) so the JS can call /wp-json/sos/v1/engage with the
 *     correct X-WP-Nonce header.
 *
 * The plugin (sos-runtime-connector) owns the REST endpoints this
 * template calls. The template itself contains no business logic.
 *
 * @package WP_Cockpit
 */

declare( strict_types = 1 );

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// Force login. ``auth_redirect()`` returns control once the visitor is
// authenticated; otherwise it redirects to wp-login.php and exits.
auth_redirect();

// ----------------------------------------------------------------------
// Enqueue cockpit assets. Lives inline-in-the-template so the cockpit
// page is self-contained: dropping this file into a theme + assigning
// it to a page is the only step required.
// ----------------------------------------------------------------------
add_action(
	'wp_enqueue_scripts',
	function () {
		$asset_dir_url  = trailingslashit( dirname( get_stylesheet_directory_uri() ) )
			. basename( dirname( __FILE__ ) )
			. '/assets/';
		// When the template lives inside the theme (recommended), the
		// assets resolve via theme URL. The README documents the layout.
		$css_url = $asset_dir_url . 'cockpit.css';
		$js_url  = $asset_dir_url . 'cockpit.js';

		// If the resolved URLs don't exist on disk (assets live elsewhere),
		// the README explains how to override via a child theme.
		wp_enqueue_style(
			'sos-cockpit',
			$css_url,
			array(),
			'1.0.0'
		);
		wp_enqueue_script(
			'sos-cockpit',
			$js_url,
			array(),
			'1.0.0',
			true
		);
		wp_localize_script(
			'sos-cockpit',
			'sosCockpit',
			array(
				'restRoot' => esc_url_raw( rest_url( 'sos/v1' ) ),
				'nonce'    => wp_create_nonce( 'wp_rest' ),
				'user'     => array(
					'id'           => (int) get_current_user_id(),
					'display_name' => (string) wp_get_current_user()->display_name,
				),
			)
		);
	},
	20
);

get_header();
?>
<main id="sos-cockpit-page" class="sos-cockpit-page">
	<header class="sos-cockpit-header">
		<h1><?php echo esc_html__( 'SOS Cockpit', 'sos-cockpit' ); ?></h1>
		<p class="sos-cockpit-subtitle">
			<?php echo esc_html__( 'Operator surface — sends messages through the SOS runtime.', 'sos-cockpit' ); ?>
		</p>
	</header>

	<section id="sos-cockpit" class="sos-cockpit">
		<div id="sos-banner" class="sos-banner" hidden role="alert"></div>

		<div id="sos-log" class="sos-log" aria-live="polite" aria-label="<?php echo esc_attr__( 'Conversation log', 'sos-cockpit' ); ?>"></div>

		<form id="sos-form" class="sos-form" autocomplete="off">
			<label for="sos-input" class="sos-label">
				<?php echo esc_html__( 'Message', 'sos-cockpit' ); ?>
			</label>
			<textarea
				id="sos-input"
				class="sos-input"
				rows="4"
				maxlength="32000"
				placeholder="<?php echo esc_attr__( 'Type a message and press Send (Cmd/Ctrl+Enter also sends).', 'sos-cockpit' ); ?>"
				required
			></textarea>
			<div class="sos-form-actions">
				<button type="submit" id="sos-send" class="sos-send">
					<?php echo esc_html__( 'Send', 'sos-cockpit' ); ?>
				</button>
				<span id="sos-status" class="sos-status" aria-live="polite"></span>
			</div>
		</form>

		<aside class="sos-panels">
			<section class="sos-panel" aria-labelledby="sos-elins-title">
				<h2 id="sos-elins-title" class="sos-panel-title">
					<?php echo esc_html__( 'ELINS', 'sos-cockpit' ); ?>
				</h2>
				<pre id="sos-elins" class="sos-panel-body"><?php echo esc_html__( '(no signal yet)', 'sos-cockpit' ); ?></pre>
			</section>

			<section class="sos-panel" aria-labelledby="sos-state-title">
				<h2 id="sos-state-title" class="sos-panel-title">
					<?php echo esc_html__( 'State', 'sos-cockpit' ); ?>
				</h2>
				<pre id="sos-state" class="sos-panel-body"><?php echo esc_html__( '(no state yet)', 'sos-cockpit' ); ?></pre>
			</section>
		</aside>
	</section>
</main>
<?php
get_footer();
