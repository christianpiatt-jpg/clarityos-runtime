<?php
/**
 * Settings → SOS Runtime admin page.
 *
 * Three fields, stored as a single nested option ``sos_runtime_settings``:
 *   * ``cloud_run_url``        — base URL of the Cloud Run service.
 *   * ``service_account_json`` — full SA JSON (private key bearing).
 *   * ``audience``             — expected ``aud`` claim. Default: cloud_run_url.
 *
 * Storing the SA JSON in wp_options is intentionally explicit. The DB row
 * is sensitive and the README documents that it must be excluded from any
 * database export that leaves the host.
 *
 * @package SOS_Connector
 */

declare( strict_types = 1 );

namespace SOS_Connector;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Settings {

	const PAGE_SLUG    = 'sos-runtime-settings';
	const SECTION_SLUG = 'sos_runtime_main';

	/**
	 * Register WP hooks.
	 *
	 * @return void
	 */
	public function register_hooks() : void {
		add_action( 'admin_menu',          array( $this, 'add_menu' ) );
		add_action( 'admin_init',          array( $this, 'register_settings' ) );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_admin_assets' ) );
		add_action( 'admin_post_sos_test_connection', array( $this, 'handle_test_connection' ) );
	}

	/**
	 * Resolve the currently-stored settings dict. Always returns the full
	 * shape, even when nothing has been saved yet.
	 *
	 * @return array<string,string>
	 */
	public static function get_settings() : array {
		$raw = get_option( SOS_CONNECTOR_OPTION_KEY, array() );
		if ( ! is_array( $raw ) ) {
			$raw = array();
		}
		return array(
			'cloud_run_url'        => isset( $raw['cloud_run_url'] )        ? (string) $raw['cloud_run_url']        : '',
			'service_account_json' => isset( $raw['service_account_json'] ) ? (string) $raw['service_account_json'] : '',
			'audience'             => isset( $raw['audience'] )             ? (string) $raw['audience']             : '',
		);
	}

	/**
	 * Add the Settings menu entry.
	 *
	 * @return void
	 */
	public function add_menu() : void {
		add_options_page(
			__( 'SOS Runtime', 'sos-connector' ),
			__( 'SOS Runtime', 'sos-connector' ),
			'manage_options',
			self::PAGE_SLUG,
			array( $this, 'render_page' )
		);
	}

	/**
	 * Register Settings API fields + sanitization callback.
	 *
	 * @return void
	 */
	public function register_settings() : void {
		register_setting(
			'sos_runtime_group',
			SOS_CONNECTOR_OPTION_KEY,
			array(
				'type'              => 'array',
				'sanitize_callback' => array( $this, 'sanitize' ),
				'default'           => array(),
			)
		);

		add_settings_section(
			self::SECTION_SLUG,
			__( 'Cloud Run target', 'sos-connector' ),
			function () {
				echo '<p>' . esc_html__(
					'Configure the SOS_V1 Cloud Run service endpoint and the service account used to mint ID tokens.',
					'sos-connector'
				) . '</p>';
			},
			self::PAGE_SLUG
		);

		add_settings_field(
			'cloud_run_url',
			__( 'Cloud Run URL', 'sos-connector' ),
			array( $this, 'field_url' ),
			self::PAGE_SLUG,
			self::SECTION_SLUG
		);

		add_settings_field(
			'service_account_json',
			__( 'Service account JSON', 'sos-connector' ),
			array( $this, 'field_sa_json' ),
			self::PAGE_SLUG,
			self::SECTION_SLUG
		);

		add_settings_field(
			'audience',
			__( 'Audience (aud claim)', 'sos-connector' ),
			array( $this, 'field_audience' ),
			self::PAGE_SLUG,
			self::SECTION_SLUG
		);
	}

	/**
	 * Sanitize the submitted form before persisting to wp_options.
	 *
	 * @param array $input Raw POST values.
	 * @return array<string,string>
	 */
	public function sanitize( $input ) : array {
		if ( ! is_array( $input ) ) {
			return array();
		}
		$url = isset( $input['cloud_run_url'] ) ? trim( (string) $input['cloud_run_url'] ) : '';
		$sa  = isset( $input['service_account_json'] ) ? trim( (string) $input['service_account_json'] ) : '';
		$aud = isset( $input['audience'] ) ? trim( (string) $input['audience'] ) : '';

		// URL — basic shape check. Accept https:// only (Cloud Run is TLS-only).
		if ( $url !== '' && ! preg_match( '#^https://[^\s]+$#i', $url ) ) {
			add_settings_error(
				SOS_CONNECTOR_OPTION_KEY,
				'cloud_run_url',
				__( 'Cloud Run URL must be an https:// URL.', 'sos-connector' )
			);
			$url = '';
		}

		// SA JSON — must parse + include client_email + private_key when
		// non-empty. Empty is fine on first save.
		if ( $sa !== '' ) {
			$parsed = json_decode( $sa, true );
			if ( ! is_array( $parsed ) || empty( $parsed['client_email'] ) || empty( $parsed['private_key'] ) ) {
				add_settings_error(
					SOS_CONNECTOR_OPTION_KEY,
					'service_account_json',
					__( 'Service account JSON must include client_email and private_key.', 'sos-connector' )
				);
				$sa = '';
			}
		}

		// Audience defaults to the Cloud Run URL.
		if ( $aud === '' ) {
			$aud = $url;
		}

		// Any settings change invalidates the cached ID token.
		delete_transient( SOS_CONNECTOR_TOKEN_TRANSIENT );

		return array(
			'cloud_run_url'        => $url,
			'service_account_json' => $sa,
			'audience'             => $aud,
		);
	}

	// ----------------------------------------------------------------------
	// Field renderers
	// ----------------------------------------------------------------------
	public function field_url() : void {
		$settings = self::get_settings();
		printf(
			'<input type="url" name="%1$s[cloud_run_url]" value="%2$s" class="regular-text" placeholder="https://os-runtime-xxxxxx.run.app">',
			esc_attr( SOS_CONNECTOR_OPTION_KEY ),
			esc_attr( $settings['cloud_run_url'] )
		);
		echo '<p class="description">' . esc_html__(
			'Base URL of the SOS_V1 Cloud Run service. No trailing slash.',
			'sos-connector'
		) . '</p>';
	}

	public function field_sa_json() : void {
		$settings = self::get_settings();
		printf(
			'<textarea name="%1$s[service_account_json]" rows="10" cols="80" class="large-text code" spellcheck="false" placeholder="{ \"type\": \"service_account\", ... }">%2$s</textarea>',
			esc_attr( SOS_CONNECTOR_OPTION_KEY ),
			esc_textarea( $settings['service_account_json'] )
		);
		echo '<p class="description">' . esc_html__(
			'Full JSON for a GCP service account with the roles/run.invoker role on the SOS_V1 service. Stored in wp_options — exclude this row from any DB export.',
			'sos-connector'
		) . '</p>';
	}

	public function field_audience() : void {
		$settings = self::get_settings();
		printf(
			'<input type="text" name="%1$s[audience]" value="%2$s" class="regular-text" placeholder="(defaults to Cloud Run URL)">',
			esc_attr( SOS_CONNECTOR_OPTION_KEY ),
			esc_attr( $settings['audience'] )
		);
		echo '<p class="description">' . esc_html__(
			'Expected aud claim for the minted ID token. Leave blank to mirror the Cloud Run URL.',
			'sos-connector'
		) . '</p>';
	}

	/**
	 * Render the full settings page (form + test-connection button).
	 *
	 * @return void
	 */
	public function render_page() : void {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap sos-runtime-settings">
			<h1><?php echo esc_html__( 'SOS Runtime', 'sos-connector' ); ?></h1>

			<form method="post" action="options.php">
				<?php
				settings_fields( 'sos_runtime_group' );
				do_settings_sections( self::PAGE_SLUG );
				submit_button();
				?>
			</form>

			<hr>

			<h2><?php echo esc_html__( 'Test connection', 'sos-connector' ); ?></h2>
			<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<input type="hidden" name="action" value="sos_test_connection">
				<?php wp_nonce_field( 'sos_test_connection' ); ?>
				<p>
					<?php echo esc_html__(
						'Calls GET /health on the configured Cloud Run service. Tests URL + IAM principal in one round trip.',
						'sos-connector'
					); ?>
				</p>
				<?php submit_button( __( 'Test /health', 'sos-connector' ), 'secondary', 'submit', false ); ?>
			</form>

			<?php $this->render_last_test_result(); ?>
		</div>
		<?php
	}

	/**
	 * Render the most recent /health test result, if any (one-shot
	 * transient — cleared after display).
	 *
	 * @return void
	 */
	private function render_last_test_result() : void {
		$result = get_transient( 'sos_runtime_last_test' );
		if ( ! $result ) {
			return;
		}
		delete_transient( 'sos_runtime_last_test' );
		$ok = ! empty( $result['ok'] );
		printf(
			'<div class="notice %1$s"><p><strong>%2$s</strong> %3$s</p></div>',
			$ok ? 'notice-success' : 'notice-error',
			esc_html(
				$ok
					? __( 'Connection OK.', 'sos-connector' )
					: __( 'Connection failed:', 'sos-connector' )
			),
			esc_html( (string) ( $result['detail'] ?? '' ) )
		);
	}

	/**
	 * admin-post handler for the "Test /health" button.
	 *
	 * @return void
	 */
	public function handle_test_connection() : void {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'Forbidden.', 'sos-connector' ), 403 );
		}
		check_admin_referer( 'sos_test_connection' );

		$client = new Client();
		$res    = $client->request( '/health', 'GET', null );

		if ( is_wp_error( $res ) ) {
			set_transient(
				'sos_runtime_last_test',
				array( 'ok' => false, 'detail' => $res->get_error_message() ),
				60
			);
		} else {
			$detail = sprintf( 'service=%s version=%s', $res['service'] ?? '?', $res['version'] ?? '?' );
			set_transient(
				'sos_runtime_last_test',
				array( 'ok' => true, 'detail' => $detail ),
				60
			);
		}

		wp_safe_redirect(
			admin_url( 'options-general.php?page=' . self::PAGE_SLUG )
		);
		exit;
	}

	/**
	 * Enqueue admin CSS on the settings page only.
	 *
	 * @param string $hook current admin page hook.
	 * @return void
	 */
	public function enqueue_admin_assets( $hook ) : void {
		if ( $hook !== 'settings_page_' . self::PAGE_SLUG ) {
			return;
		}
		wp_enqueue_style(
			'sos-connector-admin',
			SOS_CONNECTOR_URL . 'assets/admin.css',
			array(),
			SOS_CONNECTOR_VERSION
		);
	}
}
