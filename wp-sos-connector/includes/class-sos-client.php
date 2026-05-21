<?php
/**
 * Cloud Run client + ID-token minter.
 *
 * Auth flow (Cloud Run IAM):
 *   1. Build a signed JWT with target_audience = configured ``audience``.
 *      Audience of the JWT itself is ``https://oauth2.googleapis.com/token``
 *      (NOT the Cloud Run URL — that lives in target_audience).
 *   2. POST the JWT to Google's token endpoint with grant_type
 *      ``urn:ietf:params:oauth:grant-type:jwt-bearer``.
 *   3. Receive an ID token (NOT an OAuth access token). SOS_V1 verifies
 *      this via Google tokeninfo + audience match.
 *   4. Send ``Authorization: Bearer <id_token>`` to the Cloud Run service.
 *
 * The spec's mention of ``scope`` and ``access_token`` was wording-level;
 * Cloud Run IAM requires the ID-token / target_audience flow, which is
 * what SOS_V1's ``auth.py`` already expects (tokeninfo + ``aud`` check).
 * README documents the divergence.
 *
 * Tokens are cached in a transient for 55 minutes — Google issues tokens
 * with a 1-hour TTL; the 5-minute buffer protects against clock skew and
 * gives in-flight calls room to complete before the cache rotates.
 *
 * @package SOS_Connector
 */

declare( strict_types = 1 );

namespace SOS_Connector;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Client {

	const GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token';
	const JWT_TTL_SECONDS       = 3600;
	const CACHE_TTL_SECONDS     = 55 * 60;
	const HTTP_TIMEOUT_SECONDS  = 15;

	/**
	 * Send an authenticated HTTP request to the configured Cloud Run service.
	 *
	 * @param string      $path   Endpoint path (must start with /).
	 * @param string      $method HTTP method. GET / POST.
	 * @param array|null  $body   Body to JSON-encode for POST. Null for GET.
	 * @return array|\WP_Error Decoded JSON on 2xx; WP_Error on any failure.
	 */
	public function request( string $path, string $method, $body = null ) {
		$settings = Settings::get_settings();
		$base     = $settings['cloud_run_url'];
		if ( $base === '' ) {
			return new \WP_Error(
				'sos_runtime_not_configured',
				__( 'Cloud Run URL is not configured in Settings → SOS Runtime.', 'sos-connector' )
			);
		}
		if ( strpos( $path, '/' ) !== 0 ) {
			$path = '/' . $path;
		}

		$token = $this->get_bearer_token();
		if ( is_wp_error( $token ) ) {
			return $token;
		}

		$args = array(
			'method'  => strtoupper( $method ),
			'timeout' => self::HTTP_TIMEOUT_SECONDS,
			'headers' => array(
				'Authorization' => 'Bearer ' . $token,
				'Content-Type'  => 'application/json',
				'Accept'        => 'application/json',
			),
		);
		if ( $body !== null ) {
			$args['body'] = wp_json_encode( $body );
		}

		$response = wp_remote_request( rtrim( $base, '/' ) . $path, $args );
		if ( is_wp_error( $response ) ) {
			return $response;
		}

		$status = (int) wp_remote_retrieve_response_code( $response );
		$raw    = (string) wp_remote_retrieve_body( $response );
		$decoded = json_decode( $raw, true );

		// Surface Cloud Run errors faithfully — 4xx/5xx pass through.
		if ( $status >= 400 ) {
			return new \WP_Error(
				'sos_runtime_http_' . $status,
				sprintf(
					/* translators: 1: status code, 2: response body. */
					__( 'Cloud Run returned %1$d: %2$s', 'sos-connector' ),
					$status,
					$this->truncate_for_error( $raw )
				),
				array( 'status' => $status, 'body' => $decoded ?: $raw )
			);
		}

		if ( ! is_array( $decoded ) ) {
			return new \WP_Error(
				'sos_runtime_bad_response',
				__( 'Cloud Run returned a non-JSON body.', 'sos-connector' ),
				array( 'status' => $status, 'body' => $raw )
			);
		}
		return $decoded;
	}

	// ----------------------------------------------------------------------
	// ID-token minting
	// ----------------------------------------------------------------------

	/**
	 * Return a usable bearer (ID token) for Cloud Run. Cached for ~55 min.
	 *
	 * @return string|\WP_Error
	 */
	public function get_bearer_token() {
		$cached = get_transient( SOS_CONNECTOR_TOKEN_TRANSIENT );
		if ( is_string( $cached ) && $cached !== '' ) {
			return $cached;
		}
		$fresh = $this->mint_id_token();
		if ( is_wp_error( $fresh ) ) {
			return $fresh;
		}
		set_transient( SOS_CONNECTOR_TOKEN_TRANSIENT, $fresh, self::CACHE_TTL_SECONDS );
		return $fresh;
	}

	/**
	 * Build a signed JWT, exchange it at Google's token endpoint, and
	 * return the resulting ID token. Returns WP_Error on any failure.
	 *
	 * @return string|\WP_Error
	 */
	private function mint_id_token() {
		$settings = Settings::get_settings();
		$sa_raw   = $settings['service_account_json'];
		$audience = $settings['audience'] !== '' ? $settings['audience'] : $settings['cloud_run_url'];

		if ( $sa_raw === '' ) {
			return new \WP_Error(
				'sos_runtime_no_sa',
				__( 'Service account JSON is not configured.', 'sos-connector' )
			);
		}
		if ( $audience === '' ) {
			return new \WP_Error(
				'sos_runtime_no_aud',
				__( 'Audience is not configured (set Cloud Run URL).', 'sos-connector' )
			);
		}
		$sa = json_decode( $sa_raw, true );
		if ( ! is_array( $sa ) || empty( $sa['client_email'] ) || empty( $sa['private_key'] ) ) {
			return new \WP_Error(
				'sos_runtime_bad_sa',
				__( 'Service account JSON missing client_email or private_key.', 'sos-connector' )
			);
		}

		// Build JWT.
		$now    = time();
		$header = array(
			'alg' => 'RS256',
			'typ' => 'JWT',
		);
		if ( ! empty( $sa['private_key_id'] ) ) {
			$header['kid'] = (string) $sa['private_key_id'];
		}
		$payload = array(
			'iss'             => (string) $sa['client_email'],
			'sub'             => (string) $sa['client_email'],
			'aud'             => self::GOOGLE_TOKEN_ENDPOINT,
			'iat'             => $now,
			'exp'             => $now + self::JWT_TTL_SECONDS,
			'target_audience' => (string) $audience,
		);

		$header_b64  = $this->base64url_encode( (string) wp_json_encode( $header ) );
		$payload_b64 = $this->base64url_encode( (string) wp_json_encode( $payload ) );
		$message     = $header_b64 . '.' . $payload_b64;

		$signature = '';
		$ok        = openssl_sign( $message, $signature, (string) $sa['private_key'], OPENSSL_ALGO_SHA256 );
		if ( ! $ok || $signature === '' ) {
			return new \WP_Error(
				'sos_runtime_sign_failed',
				__( 'openssl_sign() failed — check the private_key in the service account JSON.', 'sos-connector' )
			);
		}
		$assertion = $message . '.' . $this->base64url_encode( $signature );

		// Exchange with Google.
		$response = wp_remote_post(
			self::GOOGLE_TOKEN_ENDPOINT,
			array(
				'timeout' => self::HTTP_TIMEOUT_SECONDS,
				'headers' => array(
					'Content-Type' => 'application/x-www-form-urlencoded',
				),
				'body'    => array(
					'grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer',
					'assertion'  => $assertion,
				),
			)
		);
		if ( is_wp_error( $response ) ) {
			return $response;
		}
		$status = (int) wp_remote_retrieve_response_code( $response );
		$raw    = (string) wp_remote_retrieve_body( $response );
		$body   = json_decode( $raw, true );

		if ( $status >= 400 || ! is_array( $body ) ) {
			return new \WP_Error(
				'sos_runtime_token_exchange_failed',
				sprintf(
					/* translators: 1: status code, 2: response body. */
					__( 'Google token endpoint returned %1$d: %2$s', 'sos-connector' ),
					$status,
					$this->truncate_for_error( $raw )
				)
			);
		}
		$id_token = isset( $body['id_token'] ) ? (string) $body['id_token'] : '';
		if ( $id_token === '' ) {
			return new \WP_Error(
				'sos_runtime_no_id_token',
				__( 'Google token response had no id_token. Confirm the service account has roles/run.invoker on the SOS_V1 service.', 'sos-connector' )
			);
		}
		return $id_token;
	}

	// ----------------------------------------------------------------------
	// Helpers
	// ----------------------------------------------------------------------

	/**
	 * Base64-url encode (no padding) — required for JWT segments.
	 *
	 * @param string $data
	 * @return string
	 */
	private function base64url_encode( string $data ) : string {
		return rtrim( strtr( base64_encode( $data ), '+/', '-_' ), '=' );
	}

	/**
	 * Shorten an upstream body so we don't log entire keys into PHP errors.
	 *
	 * @param string $s
	 * @return string
	 */
	private function truncate_for_error( string $s ) : string {
		if ( strlen( $s ) <= 240 ) {
			return $s;
		}
		return substr( $s, 0, 240 ) . '…';
	}
}
