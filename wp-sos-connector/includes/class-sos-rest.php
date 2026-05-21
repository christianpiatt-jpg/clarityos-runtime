<?php
/**
 * REST controller — exposes /wp-json/sos/v1/{engage,elins,continuity,state}.
 *
 * Every endpoint:
 *   * Requires a logged-in user (capability ``read``).
 *   * Membership gate: stubbed to ``true`` for V2 — flips to a real
 *     WooCommerce Memberships check (Founding 500 plan slug) in V3.
 *   * Forwards to the SOS_V1 Cloud Run service via ``Client::request``.
 *   * Returns the Cloud Run JSON unchanged on 2xx.
 *   * Maps ``WP_Error`` from the client into HTTP 502 ``upstream_error``
 *     responses so the JS in the cockpit gets a stable error envelope.
 *
 * @package SOS_Connector
 */

declare( strict_types = 1 );

namespace SOS_Connector;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class Rest {

	const MEMBERSHIP_PLAN_SLUG = 'founding-500';

	/** @var Client */
	private $client;

	public function __construct( ?Client $client = null ) {
		$this->client = $client ?: new Client();
	}

	/**
	 * Register REST hooks.
	 *
	 * @return void
	 */
	public function register_hooks() : void {
		add_action( 'rest_api_init', array( $this, 'register_routes' ) );
	}

	/**
	 * Register all four routes under sos/v1.
	 *
	 * @return void
	 */
	public function register_routes() : void {
		$base = array(
			'methods'             => 'POST',
			'permission_callback' => array( $this, 'check_perms' ),
		);
		register_rest_route(
			SOS_CONNECTOR_REST_NS,
			'/engage',
			array_merge(
				$base,
				array(
					'callback' => array( $this, 'engage' ),
					'args'     => array(
						'message' => array(
							'type'              => 'string',
							'required'          => true,
							'sanitize_callback' => 'sanitize_textarea_field',
						),
						'context' => array(
							'type'              => 'object',
							'required'          => false,
							'sanitize_callback' => array( $this, 'sanitize_context' ),
						),
					),
				)
			)
		);
		register_rest_route(
			SOS_CONNECTOR_REST_NS,
			'/elins',
			array_merge(
				$base,
				array(
					'callback' => array( $this, 'elins' ),
					'args'     => array(
						'signal' => array(
							'type'     => 'object',
							'required' => false,
						),
					),
				)
			)
		);
		register_rest_route(
			SOS_CONNECTOR_REST_NS,
			'/continuity',
			array_merge(
				$base,
				array(
					'callback' => array( $this, 'continuity' ),
					'args'     => array(
						'markers' => array(
							'type'     => 'object',
							'required' => false,
						),
					),
				)
			)
		);
		register_rest_route(
			SOS_CONNECTOR_REST_NS,
			'/state',
			array_merge(
				$base,
				array(
					'callback' => array( $this, 'state' ),
					'args'     => array(
						'current_state' => array(
							'required' => false,
						),
					),
				)
			)
		);
	}

	// ----------------------------------------------------------------------
	// Permissions
	// ----------------------------------------------------------------------

	/**
	 * Logged-in + capability check + membership stub.
	 *
	 * V2 always returns true for any logged-in user; the membership stub
	 * is a marker for V3 to enforce.
	 *
	 * @return bool|\WP_Error
	 */
	public function check_perms() {
		if ( ! is_user_logged_in() ) {
			return new \WP_Error(
				'rest_forbidden',
				__( 'You must be logged in to call SOS.', 'sos-connector' ),
				array( 'status' => 401 )
			);
		}
		if ( ! current_user_can( 'read' ) ) {
			return new \WP_Error(
				'rest_forbidden',
				__( 'Insufficient capability.', 'sos-connector' ),
				array( 'status' => 403 )
			);
		}
		// Membership gate — V3 flips this to a real WooCommerce check.
		if ( ! $this->user_has_active_membership( get_current_user_id() ) ) {
			return new \WP_Error(
				'sos_no_membership',
				__( 'Founding 500 membership required.', 'sos-connector' ),
				array( 'status' => 403 )
			);
		}
		return true;
	}

	/**
	 * Membership stub. V3 will replace this with a real WC Memberships call.
	 *
	 * @param int $user_id
	 * @return bool
	 */
	private function user_has_active_membership( int $user_id ) : bool {
		// TODO(V3): when wc_memberships is installed, replace with:
		//   if ( function_exists( 'wc_memberships_is_user_active_member' ) ) {
		//       return (bool) wc_memberships_is_user_active_member(
		//           $user_id, self::MEMBERSHIP_PLAN_SLUG
		//       );
		//   }
		unset( $user_id );
		return true;
	}

	/**
	 * Sanitize the free-form context dict the cockpit sends. We accept
	 * any JSON-serialisable shape but strip control characters from
	 * string values and cap nesting + size.
	 *
	 * @param mixed $value
	 * @return array
	 */
	public function sanitize_context( $value ) : array {
		if ( ! is_array( $value ) ) {
			return array();
		}
		// Shallow-clean: drop non-scalar / non-array values, trim strings.
		$out = array();
		foreach ( $value as $k => $v ) {
			if ( ! is_string( $k ) ) {
				continue;
			}
			$k = sanitize_key( $k );
			if ( $k === '' ) {
				continue;
			}
			if ( is_string( $v ) ) {
				$v = sanitize_text_field( $v );
			} elseif ( is_scalar( $v ) ) {
				// keep ints / floats / bools as-is
			} elseif ( is_array( $v ) ) {
				$v = $this->sanitize_context( $v );
			} else {
				continue;
			}
			$out[ $k ] = $v;
		}
		return $out;
	}

	// ----------------------------------------------------------------------
	// Endpoint callbacks
	// ----------------------------------------------------------------------

	public function engage( \WP_REST_Request $request ) {
		$payload = $this->base_payload();
		$payload['message'] = (string) $request->get_param( 'message' );
		$payload['context'] = $this->merge_context( (array) ( $request->get_param( 'context' ) ?: array() ) );
		return $this->forward( '/engage', $payload );
	}

	public function elins( \WP_REST_Request $request ) {
		$payload = $this->base_payload();
		$payload['signal'] = (array) ( $request->get_param( 'signal' ) ?: array() );
		return $this->forward( '/elins', $payload );
	}

	public function continuity( \WP_REST_Request $request ) {
		$payload = $this->base_payload();
		$payload['markers'] = (array) ( $request->get_param( 'markers' ) ?: array() );
		return $this->forward( '/continuity', $payload );
	}

	public function state( \WP_REST_Request $request ) {
		$payload = $this->base_payload();
		$cs      = $request->get_param( 'current_state' );
		// Only forward current_state when explicitly sent (reads omit it).
		if ( $cs !== null ) {
			$payload['current_state'] = $cs;
		}
		return $this->forward( '/state', $payload );
	}

	// ----------------------------------------------------------------------
	// Payload assembly + forwarding
	// ----------------------------------------------------------------------

	/**
	 * Base envelope: user_id + session_id derived from the WP session.
	 *
	 * @return array<string,mixed>
	 */
	private function base_payload() : array {
		$user_id    = (string) get_current_user_id();
		$session_id = (string) wp_get_session_token();
		if ( $session_id === '' ) {
			// Fall back to a stable per-user identifier so SOS_V1 still
			// groups events into a single session.
			$session_id = 'wp_' . $user_id;
		}
		return array(
			'user_id'    => $user_id,
			'session_id' => $session_id,
		);
	}

	/**
	 * Build the context the cockpit + plugin contribute, merging with
	 * whatever the request body supplied.
	 *
	 * @param array $caller_context
	 * @return array
	 */
	private function merge_context( array $caller_context ) : array {
		$user    = wp_get_current_user();
		$default = array(
			'site_url'       => get_site_url(),
			'wp_user_login'  => $user ? (string) $user->user_login  : '',
			'wp_display_name' => $user ? (string) $user->display_name : '',
			'wp_user_roles'  => $user ? (array) $user->roles : array(),
			'plan_slug'      => self::MEMBERSHIP_PLAN_SLUG, // TODO(V3): pull from WC Memberships
		);
		return array_replace( $default, $caller_context );
	}

	/**
	 * Forward to Cloud Run and shape the WP REST response.
	 *
	 * @param string $path
	 * @param array  $payload
	 * @return \WP_REST_Response|\WP_Error
	 */
	private function forward( string $path, array $payload ) {
		$res = $this->client->request( $path, 'POST', $payload );
		if ( is_wp_error( $res ) ) {
			$status = (int) ( $res->get_error_data()['status'] ?? 502 );
			return new \WP_REST_Response(
				array(
					'error'   => 'upstream_error',
					'code'    => $res->get_error_code(),
					'message' => $res->get_error_message(),
					'detail'  => $res->get_error_data(),
				),
				$status
			);
		}
		return new \WP_REST_Response( $res, 200 );
	}
}
