<?php
/**
 * Plugin Name:       SOS Runtime Connector
 * Plugin URI:        https://pro-mediations.com/
 * Description:       Bridges the WordPress operator surface to the SOS_V1 Cloud Run service. Exposes /wp-json/sos/v1/{engage,elins,continuity,state}; authenticates Cloud Run with a service-account-signed ID token.
 * Version:           1.0.0
 * Requires at least: 6.4
 * Requires PHP:      7.4
 * Author:            ClarityOS
 * License:           Proprietary
 * Text Domain:       sos-connector
 *
 * @package SOS_Connector
 */

declare( strict_types = 1 );

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------
define( 'SOS_CONNECTOR_VERSION',     '1.0.0' );
define( 'SOS_CONNECTOR_FILE',        __FILE__ );
define( 'SOS_CONNECTOR_DIR',         plugin_dir_path( __FILE__ ) );
define( 'SOS_CONNECTOR_URL',         plugin_dir_url( __FILE__ ) );
define( 'SOS_CONNECTOR_OPTION_KEY',  'sos_runtime_settings' );
define( 'SOS_CONNECTOR_TOKEN_TRANSIENT', 'sos_runtime_id_token' );

// REST namespace used by every endpoint this plugin registers.
define( 'SOS_CONNECTOR_REST_NS', 'sos/v1' );

// --------------------------------------------------------------------------
// Autoloader for the four classes shipped under namespace SOS_Connector\.
// Lightweight enough that a full PSR-4 autoloader is overkill; one file per
// class with deterministic naming.
// --------------------------------------------------------------------------
spl_autoload_register(
	function ( $class ) {
		if ( strpos( $class, 'SOS_Connector\\' ) !== 0 ) {
			return;
		}
		$short = substr( $class, strlen( 'SOS_Connector\\' ) );
		$file  = SOS_CONNECTOR_DIR
			. 'includes/class-sos-'
			. strtolower( $short )
			. '.php';
		if ( file_exists( $file ) ) {
			require_once $file;
		}
	}
);

// --------------------------------------------------------------------------
// Boot
// --------------------------------------------------------------------------
add_action(
	'plugins_loaded',
	function () {
		// Admin settings page.
		if ( is_admin() ) {
			$settings = new SOS_Connector\Settings();
			$settings->register_hooks();
		}

		// REST routes — always registered, even on the front-end, so
		// the JS in /cockpit can call them.
		$rest = new SOS_Connector\Rest();
		$rest->register_hooks();
	}
);

// --------------------------------------------------------------------------
// Lifecycle — best-effort cleanup on uninstall.
// --------------------------------------------------------------------------
register_uninstall_hook(
	__FILE__,
	'sos_connector_uninstall'
);

/**
 * Drop the stored settings + any cached ID token. Called by WordPress when
 * the plugin is uninstalled (NOT on deactivation).
 *
 * @return void
 */
function sos_connector_uninstall() {
	delete_option( SOS_CONNECTOR_OPTION_KEY );
	delete_transient( SOS_CONNECTOR_TOKEN_TRANSIENT );
}
