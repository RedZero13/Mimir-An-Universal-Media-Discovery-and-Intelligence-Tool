<?php
/**
 * Plugin Name: Mimir Vault
 * Plugin URI:  https://mimir.terratalesmedia.world/
 * Description: Server side of Mimir accounts. Stores one encrypted, opaque vault per recovery key. The browser encrypts everything; this plugin never sees keys or readable data.
 * Version:     0.2.0
 * Requires PHP: 8.0
 * Author:      Terratales Media Entertainment Private Limited
 * License:     GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: mimir-vault
 *
 * Works as a normal plugin (upload the zip) or pasted whole into a code-snippets plugin: it is one file, loads once,
 * and creates its tables on first use.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! class_exists( 'Mimir_Vault' ) ) {

	final class Mimir_Vault {

		const VERSION    = '0.2.0';
		const DB_VERSION = '2';
		const NS         = 'mimir/v1';
		const MAX_BLOB   = 2097152; // 2 MB of base64 text.

		/**
		 * First PHP release per branch that carries the October 2026 emergency fixes for CVE-2026-109618 and CVE-2026-109619
		 * (unauthenticated remote code execution and memory disclosure in PHP itself, CVSS 9.2). Older branches get no fix.
		 */
		const PHP_PATCHED = array( '8.5' => '8.5.12', '8.4' => '8.4.27', '8.3' => '8.3.36', '8.2' => '8.2.35' );

		/** Origins that may call the API from a browser. Filter: mimir_vault_origins. */
		const ORIGINS = array( 'https://mimir.terratalesmedia.world' );

		private static bool $installed = false;

		public static function boot(): void {
			add_action( 'rest_api_init', array( __CLASS__, 'routes' ) );
			add_filter( 'allowed_http_origins', array( __CLASS__, 'origins' ) );
			add_action( 'mimir_vault_housekeeping', array( __CLASS__, 'housekeeping' ) );
			add_action( 'admin_menu', array( __CLASS__, 'admin_menu' ) );
			add_action( 'admin_init', array( __CLASS__, 'privacy_text' ) );
			add_action( 'admin_notices', array( __CLASS__, 'php_notice' ) );
			if ( ! wp_next_scheduled( 'mimir_vault_housekeeping' ) ) {
				wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'mimir_vault_housekeeping' );
			}
		}

		// ------------------------------------------------------------------ storage
		private static function accounts(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_accounts';
		}

		private static function vaults(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_vaults';
		}

		private static function metrics(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_metrics';
		}

		private static function active(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_active';
		}

		private static function visitors(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_visitors';
		}

		private static function errors(): string {
			global $wpdb;
			return $wpdb->prefix . 'mimir_errors';
		}

		/** Creates or upgrades the tables, once per request and only when the stored version is old. */
		public static function install(): void {
			if ( self::$installed ) {
				return;
			}
			self::$installed = true;
			if ( get_option( 'mimir_vault_db_version' ) === self::DB_VERSION ) {
				return;
			}
			global $wpdb;
			require_once ABSPATH . 'wp-admin/includes/upgrade.php';
			$charset = $wpdb->get_charset_collate();
			$a       = self::accounts();
			$v       = self::vaults();
			dbDelta(
				"CREATE TABLE $a (
  id char(32) NOT NULL,
  auth_hash char(64) NOT NULL,
  created datetime NOT NULL,
  last_seen datetime NOT NULL,
  consent_version varchar(16) NOT NULL DEFAULT '',
  consent_analytics tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY  (id),
  KEY last_seen (last_seen)
) $charset;"
			);
			dbDelta(
				"CREATE TABLE $v (
  account_id char(32) NOT NULL,
  ciphertext longtext NOT NULL,
  version int(10) unsigned NOT NULL DEFAULT 1,
  size int(10) unsigned NOT NULL DEFAULT 0,
  updated datetime NOT NULL,
  PRIMARY KEY  (account_id)
) $charset;"
			);
			$m  = self::metrics();
			$ac = self::active();
			$vs = self::visitors();
			$er = self::errors();
			dbDelta(
				"CREATE TABLE $m (
  day date NOT NULL,
  k varchar(24) NOT NULL,
  v varchar(64) NOT NULL,
  n int(10) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY  (day,k,v)
) $charset;"
			);
			dbDelta(
				"CREATE TABLE $ac (
  day date NOT NULL,
  vid char(16) NOT NULL,
  PRIMARY KEY  (day,vid)
) $charset;"
			);
			dbDelta(
				"CREATE TABLE $vs (
  vid char(16) NOT NULL,
  first_day date NOT NULL,
  last_day date NOT NULL,
  PRIMARY KEY  (vid)
) $charset;"
			);
			dbDelta(
				"CREATE TABLE $er (
  id char(16) NOT NULL,
  msg varchar(200) NOT NULL,
  route varchar(32) NOT NULL,
  ver varchar(12) NOT NULL,
  n int(10) unsigned NOT NULL DEFAULT 0,
  first_seen date NOT NULL,
  last_seen date NOT NULL,
  PRIMARY KEY  (id)
) $charset;"
			);
			update_option( 'mimir_vault_db_version', self::DB_VERSION, false );
		}

		private static function pepper(): string {
			$p = get_option( 'mimir_vault_pepper' );
			if ( ! is_string( $p ) || strlen( $p ) < 32 ) {
				$p = wp_generate_password( 64, true, true );
				update_option( 'mimir_vault_pepper', $p, false );
			}
			return $p;
		}

		private static function now(): string {
			return gmdate( 'Y-m-d H:i:s' );
		}

		// ------------------------------------------------------------------ routes
		public static function origins( array $allowed ): array {
			return array_values( array_unique( array_merge( $allowed, (array) apply_filters( 'mimir_vault_origins', self::ORIGINS ) ) ) );
		}

		public static function routes(): void {
			$id   = array( 'required' => true, 'type' => 'string', 'validate_callback' => fn( $v ) => is_string( $v ) && 1 === preg_match( '/^[0-9a-f]{32}$/', $v ) );
			$auth = array( 'required' => true, 'type' => 'string', 'validate_callback' => fn( $v ) => is_string( $v ) && 1 === preg_match( '/^[A-Za-z0-9_-]{43}$/', $v ) );
			$blob = array( 'required' => true, 'type' => 'string', 'validate_callback' => fn( $v ) => is_string( $v ) && strlen( $v ) >= 29 && strlen( $v ) <= self::MAX_BLOB && 1 === preg_match( '/^[A-Za-z0-9_-]+$/', $v ) );
			$open = '__return_true'; // Public on purpose: every call proves itself with the key-derived secret in its body.

			register_rest_route( self::NS, '/health', array( 'methods' => 'GET', 'callback' => array( __CLASS__, 'health' ), 'permission_callback' => $open ) );
			register_rest_route( self::NS, '/vault/create', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'create' ), 'permission_callback' => $open,
				'args' => array( 'id' => $id, 'auth' => $auth, 'blob' => $blob,
					'consent_version' => array( 'type' => 'string', 'default' => '', 'sanitize_callback' => fn( $v ) => substr( preg_replace( '/[^0-9A-Za-z._-]/', '', (string) $v ), 0, 16 ) ),
					'analytics' => array( 'type' => 'boolean', 'default' => false ) ) ) );
			register_rest_route( self::NS, '/vault/open', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'open' ), 'permission_callback' => $open, 'args' => array( 'id' => $id, 'auth' => $auth ) ) );
			register_rest_route( self::NS, '/vault/save', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'save' ), 'permission_callback' => $open,
				'args' => array( 'id' => $id, 'auth' => $auth, 'blob' => $blob, 'if_match' => array( 'required' => true, 'type' => 'integer', 'minimum' => 1 ) ) ) );
			register_rest_route( self::NS, '/vault/rotate', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'rotate' ), 'permission_callback' => $open,
				'args' => array( 'id' => $id, 'auth' => $auth, 'blob' => $blob,
					'new_id' => array_merge( $id, array() ), 'new_auth' => array_merge( $auth, array() ) ) ) );
			register_rest_route( self::NS, '/vault/consent', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'consent' ), 'permission_callback' => $open,
				'args' => array( 'id' => $id, 'auth' => $auth,
					'consent_version' => array( 'required' => true, 'type' => 'string', 'sanitize_callback' => fn( $v ) => substr( preg_replace( '/[^0-9A-Za-z._-]/', '', (string) $v ), 0, 16 ) ),
					'analytics' => array( 'required' => true, 'type' => 'boolean' ) ) ) );
			register_rest_route( self::NS, '/telemetry', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'telemetry' ), 'permission_callback' => $open ) );
			register_rest_route( self::NS, '/vault/delete', array( 'methods' => 'POST', 'callback' => array( __CLASS__, 'delete' ), 'permission_callback' => $open, 'args' => array( 'id' => $id, 'auth' => $auth ) ) );
		}

		private static function err( string $code, string $message, int $status, array $extra = array() ): WP_Error {
			return new WP_Error( $code, $message, array_merge( array( 'status' => $status ), $extra ) );
		}

		/** Counts a call against a limit; false once the limit is reached. The counters are transients that expire on their own. */
		private static function allow( string $bucket, int $limit, int $window ): bool {
			$key = 'mv_' . md5( $bucket );
			$n   = (int) get_transient( $key );
			if ( $n >= $limit ) {
				return false;
			}
			set_transient( $key, $n + 1, $window );
			return true;
		}

		private static function who(): string {
			$ip = isset( $_SERVER['REMOTE_ADDR'] ) ? (string) $_SERVER['REMOTE_ADDR'] : '';
			return hash_hmac( 'sha256', $ip, self::pepper() ); // Only ever used as a transient key; the address itself is never stored.
		}

		private static function hash_auth( string $auth ): string {
			return hash_hmac( 'sha256', $auth, self::pepper() );
		}

		/** Checks the key-derived secret. Unknown ids and wrong secrets look the same and take the same time. */
		private static function authenticate( string $id, string $auth ): bool|WP_Error {
			global $wpdb;
			self::install();
			if ( ! self::allow( 'bad:' . self::who(), 20, 15 * MINUTE_IN_SECONDS ) || ! self::allow( 'bad-id:' . $id, 20, 15 * MINUTE_IN_SECONDS ) ) {
				return self::err( 'rate_limited', 'Too many attempts. Wait a few minutes and try again.', 429 );
			}
			$row   = $wpdb->get_row( $wpdb->prepare( 'SELECT auth_hash FROM ' . self::accounts() . ' WHERE id = %s', $id ), ARRAY_A );
			$known = $row ? (string) $row['auth_hash'] : str_repeat( '0', 64 );
			$ok    = hash_equals( $known, self::hash_auth( $auth ) ) && $row;
			if ( ! $ok ) {
				return self::err( 'bad_key', 'No vault opens with that key.', 401 );
			}
			// A good sign-in does not count against the limits.
			delete_transient( 'mv_' . md5( 'bad:' . self::who() ) );
			delete_transient( 'mv_' . md5( 'bad-id:' . $id ) );
			return true;
		}

		public static function health(): WP_REST_Response {
			return new WP_REST_Response( array( 'ok' => true, 'service' => 'mimir-vault', 'version' => self::VERSION, 'max_blob' => self::MAX_BLOB ), 200 );
		}

		public static function create( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			self::install();
			if ( ! self::allow( 'create:' . self::who(), 10, HOUR_IN_SECONDS ) ) {
				return self::err( 'rate_limited', 'Too many new vaults from this connection. Try again later.', 429 );
			}
			$id = (string) $r['id'];
			if ( $wpdb->get_var( $wpdb->prepare( 'SELECT COUNT(*) FROM ' . self::accounts() . ' WHERE id = %s', $id ) ) ) {
				return self::err( 'exists', 'A vault with that key already exists.', 409 );
			}
			$now  = self::now();
			$blob = (string) $r['blob'];
			$wpdb->insert( self::accounts(), array( 'id' => $id, 'auth_hash' => self::hash_auth( (string) $r['auth'] ), 'created' => $now, 'last_seen' => $now,
				'consent_version' => (string) $r['consent_version'], 'consent_analytics' => $r['analytics'] ? 1 : 0 ), array( '%s', '%s', '%s', '%s', '%s', '%d' ) );
			$wpdb->insert( self::vaults(), array( 'account_id' => $id, 'ciphertext' => $blob, 'version' => 1, 'size' => strlen( $blob ), 'updated' => $now ), array( '%s', '%s', '%d', '%d', '%s' ) );
			return new WP_REST_Response( array( 'version' => 1, 'updated' => $now ), 201 );
		}

		private static function touch( string $id ): void {
			global $wpdb;
			$wpdb->update( self::accounts(), array( 'last_seen' => self::now() ), array( 'id' => $id ), array( '%s' ), array( '%s' ) );
		}

		public static function open( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			$id   = (string) $r['id'];
			$auth = self::authenticate( $id, (string) $r['auth'] );
			if ( is_wp_error( $auth ) ) {
				return $auth;
			}
			self::touch( $id );
			$row = $wpdb->get_row( $wpdb->prepare( 'SELECT ciphertext, version, updated FROM ' . self::vaults() . ' WHERE account_id = %s', $id ), ARRAY_A );
			if ( ! $row ) {
				return self::err( 'missing', 'This vault has no contents.', 404 );
			}
			return new WP_REST_Response( array( 'blob' => $row['ciphertext'], 'version' => (int) $row['version'], 'updated' => $row['updated'] ), 200 );
		}

		public static function save( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			$id   = (string) $r['id'];
			$auth = self::authenticate( $id, (string) $r['auth'] );
			if ( is_wp_error( $auth ) ) {
				return $auth;
			}
			if ( ! self::allow( 'save:' . $id, 240, HOUR_IN_SECONDS ) ) {
				return self::err( 'rate_limited', 'Syncing too often. Try again in a few minutes.', 429 );
			}
			$blob = (string) $r['blob'];
			$now  = self::now();
			$n    = $wpdb->query( $wpdb->prepare(
				'UPDATE ' . self::vaults() . ' SET ciphertext = %s, version = version + 1, size = %d, updated = %s WHERE account_id = %s AND version = %d',
				$blob, strlen( $blob ), $now, $id, (int) $r['if_match']
			) );
			if ( ! $n ) { // Someone saved from another device first: hand back their copy so the browser can merge.
				$row = $wpdb->get_row( $wpdb->prepare( 'SELECT ciphertext, version, updated FROM ' . self::vaults() . ' WHERE account_id = %s', $id ), ARRAY_A );
				return self::err( 'conflict', 'The vault changed on another device.', 409, $row ? array( 'blob' => $row['ciphertext'], 'version' => (int) $row['version'], 'updated' => $row['updated'] ) : array() );
			}
			self::touch( $id );
			return new WP_REST_Response( array( 'version' => (int) $r['if_match'] + 1, 'updated' => $now ), 200 );
		}

		public static function rotate( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			$id   = (string) $r['id'];
			$auth = self::authenticate( $id, (string) $r['auth'] );
			if ( is_wp_error( $auth ) ) {
				return $auth;
			}
			$new = (string) $r['new_id'];
			if ( $new === $id || $wpdb->get_var( $wpdb->prepare( 'SELECT COUNT(*) FROM ' . self::accounts() . ' WHERE id = %s', $new ) ) ) {
				return self::err( 'exists', 'Choose a different new key.', 409 );
			}
			$blob = (string) $r['blob'];
			$now  = self::now();
			$wpdb->update( self::accounts(), array( 'id' => $new, 'auth_hash' => self::hash_auth( (string) $r['new_auth'] ), 'last_seen' => $now ), array( 'id' => $id ), array( '%s', '%s', '%s' ), array( '%s' ) );
			$wpdb->query( $wpdb->prepare(
				'UPDATE ' . self::vaults() . ' SET account_id = %s, ciphertext = %s, version = version + 1, size = %d, updated = %s WHERE account_id = %s',
				$new, $blob, strlen( $blob ), $now, $id
			) );
			$version = (int) $wpdb->get_var( $wpdb->prepare( 'SELECT version FROM ' . self::vaults() . ' WHERE account_id = %s', $new ) );
			return new WP_REST_Response( array( 'version' => $version, 'updated' => $now ), 200 );
		}

		public static function delete( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			$id   = (string) $r['id'];
			$auth = self::authenticate( $id, (string) $r['auth'] );
			if ( is_wp_error( $auth ) ) {
				return $auth;
			}
			$wpdb->delete( self::vaults(), array( 'account_id' => $id ), array( '%s' ) );
			$wpdb->delete( self::accounts(), array( 'id' => $id ), array( '%s' ) );
			return new WP_REST_Response( array( 'deleted' => true ), 200 );
		}

		public static function consent( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			$id   = (string) $r['id'];
			$auth = self::authenticate( $id, (string) $r['auth'] );
			if ( is_wp_error( $auth ) ) {
				return $auth;
			}
			$wpdb->update( self::accounts(), array( 'consent_version' => (string) $r['consent_version'], 'consent_analytics' => $r['analytics'] ? 1 : 0 ), array( 'id' => $id ), array( '%s', '%d' ), array( '%s' ) );
			return new WP_REST_Response( array( 'saved' => true ), 200 );
		}

		// ------------------------------------------------------------------ telemetry
		// Counts only. No address is stored, no cookie is set, and nothing about what a person looks at or saves is accepted:
		// route names (never titles), feature names, coarse device classes and error text. A pseudonymous visitor id, sent only
		// after the person opts in, is stored as a keyed hash so active users can be counted; it expires with everything else
		// after 13 months. Errors are accepted without an id.
		const DEVICES  = array( 'mobile', 'tablet', 'desktop' );
		const BROWSERS = array( 'chrome', 'safari', 'firefox', 'edge', 'samsung', 'opera', 'other' );
		const SYSTEMS  = array( 'android', 'ios', 'windows', 'macos', 'linux', 'chromeos', 'other' );
		const SCREENS  = array( 'xs', 'sm', 'md', 'lg', 'xl' );
		const RETAIN_DAYS = 395;

		private static function bump( string $k, string $v, string $day ): void {
			global $wpdb;
			$wpdb->query( $wpdb->prepare( 'INSERT INTO ' . self::metrics() . ' (day, k, v, n) VALUES (%s, %s, %s, 1) ON DUPLICATE KEY UPDATE n = n + 1', $day, $k, $v ) );
		}

		private static function word( $v, int $max = 32 ): ?string {
			return is_string( $v ) && 1 === preg_match( '/^[a-z0-9][a-z0-9_:-]{0,' . ( $max - 1 ) . '}$/', $v ) ? $v : null;
		}

		public static function telemetry( WP_REST_Request $r ): WP_REST_Response|WP_Error {
			global $wpdb;
			self::install();
			if ( ! self::allow( 'tel:' . self::who(), 240, HOUR_IN_SECONDS ) ) {
				return self::err( 'rate_limited', 'Too many reports.', 429 );
			}
			$body = $r->get_json_params();
			$body = is_array( $body ) ? $body : array();
			if ( strlen( (string) wp_json_encode( $body ) ) > 8192 ) {
				return self::err( 'too_large', 'That report is too large.', 413 );
			}
			$events = isset( $body['events'] ) && is_array( $body['events'] ) ? array_slice( $body['events'], 0, 60 ) : array();
			$day    = gmdate( 'Y-m-d' );
			$vid    = isset( $body['vid'] ) && is_string( $body['vid'] ) && 1 === preg_match( '/^[0-9a-f]{32}$/', $body['vid'] ) ? substr( hash_hmac( 'sha256', $body['vid'], self::pepper() ), 0, 16 ) : null;
			$ver    = isset( $body['ver'] ) && is_string( $body['ver'] ) && 1 === preg_match( '/^[0-9a-f]{6,12}$/', $body['ver'] ) ? $body['ver'] : '';
			$kept   = 0;
			foreach ( $events as $e ) {
				if ( ! is_array( $e ) || ! isset( $e['n'] ) ) {
					continue;
				}
				if ( 'er' === $e['n'] ) {
					$msg   = isset( $e['m'] ) && is_string( $e['m'] ) ? substr( trim( preg_replace( '/[^\x20-\x7E]+/', ' ', $e['m'] ) ), 0, 200 ) : '';
					$route = self::word( $e['r'] ?? null ) ?? 'unknown';
					if ( '' === $msg ) {
						continue;
					}
					$eid = substr( hash( 'sha256', $msg . '|' . $route . '|' . $ver ), 0, 16 );
					$wpdb->query( $wpdb->prepare(
						'INSERT INTO ' . self::errors() . ' (id, msg, route, ver, n, first_seen, last_seen) VALUES (%s, %s, %s, %s, 1, %s, %s) ON DUPLICATE KEY UPDATE n = n + 1, last_seen = %s',
						$eid, $msg, $route, $ver, $day, $day, $day
					) );
					self::bump( 'error', 'all', $day );
					++$kept;
					continue;
				}
				if ( null === $vid ) { // Everything except errors needs the person's opt-in, which is what the visitor id stands for.
					continue;
				}
				if ( 'pv' === $e['n'] && null !== self::word( $e['r'] ?? null ) ) {
					self::bump( 'route', $e['r'], $day );
					++$kept;
				} elseif ( 'ft' === $e['n'] && null !== self::word( $e['f'] ?? null ) ) {
					self::bump( 'feature', $e['f'], $day );
					++$kept;
				} elseif ( 'pf' === $e['n'] && isset( $e['lcp'] ) && is_int( $e['lcp'] ) && $e['lcp'] >= 0 && $e['lcp'] < 600000 ) {
					self::bump( 'lcp', $e['lcp'] < 1000 ? 'under 1s' : ( $e['lcp'] < 2500 ? '1 to 2.5s' : ( $e['lcp'] < 4000 ? '2.5 to 4s' : 'over 4s' ) ), $day );
					++$kept;
				}
			}
			if ( null !== $vid ) {
				$wpdb->query( $wpdb->prepare( 'INSERT IGNORE INTO ' . self::active() . ' (day, vid) VALUES (%s, %s)', $day, $vid ) );
				$wpdb->query( $wpdb->prepare( 'INSERT IGNORE INTO ' . self::visitors() . ' (vid, first_day, last_day) VALUES (%s, %s, %s)', $vid, $day, $day ) );
				$wpdb->query( $wpdb->prepare( 'UPDATE ' . self::visitors() . ' SET last_day = %s WHERE vid = %s', $day, $vid ) );
				if ( ! empty( $body['start'] ) ) { // Once per visit: what kind of device it was.
					$dims = array( 'device' => self::DEVICES, 'browser' => self::BROWSERS, 'os' => self::SYSTEMS, 'screen' => self::SCREENS );
					foreach ( $dims as $k => $allowed ) {
						if ( isset( $body[ $k ] ) && in_array( $body[ $k ], $allowed, true ) ) {
							self::bump( $k, $body[ $k ], $day );
						}
					}
					if ( isset( $body['lang'] ) && is_string( $body['lang'] ) && 1 === preg_match( '/^[a-z]{2,3}$/', $body['lang'] ) ) {
						self::bump( 'lang', $body['lang'], $day );
					}
					if ( '' !== $ver ) {
						self::bump( 'version', $ver, $day );
					}
					self::bump( 'visit', 'all', $day );
				}
			}
			return new WP_REST_Response( array( 'kept' => $kept ), 202 );
		}

		/** Totals for the admin screen: active users, new visitors, retention, device mix, routes, features and errors. */
		public static function usage(): array {
			global $wpdb;
			self::install();
			$ac = self::active();
			$d  = fn( int $back ) => gmdate( 'Y-m-d', time() - $back * DAY_IN_SECONDS );
			$distinct = fn( int $days ) => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(DISTINCT vid) FROM $ac WHERE day >= %s", $d( $days - 1 ) ) );
			$mix = function ( string $k, int $days = 30 ) use ( $wpdb, $d ) {
				return $wpdb->get_results( $wpdb->prepare( 'SELECT v, SUM(n) AS n FROM ' . self::metrics() . ' WHERE k = %s AND day >= %s GROUP BY v ORDER BY n DESC LIMIT 15', $k, $d( $days - 1 ) ), ARRAY_A );
			};
			$retained = function ( int $n ) use ( $wpdb, $d ) { // Of visitors first seen N days ago, how many have come back at least once since.
				$vs = self::visitors();
				return array(
					'cohort'   => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM $vs WHERE first_day = %s", $d( $n ) ) ),
					'returned' => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM $vs WHERE first_day = %s AND last_day > first_day", $d( $n ) ) ),
				);
			};
			$daily = $wpdb->get_results( $wpdb->prepare( "SELECT day, COUNT(*) AS n FROM $ac WHERE day >= %s GROUP BY day ORDER BY day", $d( 13 ) ), ARRAY_A );
			return array(
				'dau'      => $distinct( 1 ), 'wau' => $distinct( 7 ), 'mau' => $distinct( 30 ),
				'daily'    => $daily,
				'new_30'   => (int) $wpdb->get_var( $wpdb->prepare( 'SELECT COUNT(*) FROM ' . self::visitors() . ' WHERE first_day >= %s', $d( 29 ) ) ),
				'device'   => $mix( 'device' ), 'browser' => $mix( 'browser' ), 'os' => $mix( 'os' ), 'screen' => $mix( 'screen' ), 'lang' => $mix( 'lang' ),
				'route'    => $mix( 'route' ), 'feature' => $mix( 'feature' ), 'lcp' => $mix( 'lcp' ), 'version' => $mix( 'version' ),
				'errors'   => $wpdb->get_results( $wpdb->prepare( 'SELECT msg, route, ver, n, last_seen FROM ' . self::errors() . ' WHERE last_seen >= %s ORDER BY n DESC LIMIT 15', $d( 29 ) ), ARRAY_A ),
				'error_n'  => (int) $wpdb->get_var( $wpdb->prepare( 'SELECT COALESCE(SUM(n),0) FROM ' . self::metrics() . ' WHERE k = %s AND day >= %s', 'error', $d( 29 ) ) ),
				'visits'   => (int) $wpdb->get_var( $wpdb->prepare( 'SELECT COALESCE(SUM(n),0) FROM ' . self::metrics() . ' WHERE k = %s AND day >= %s', 'visit', $d( 29 ) ) ),
				'retained' => array( 'd1' => $retained( 1 ), 'd7' => $retained( 7 ), 'd30' => $retained( 30 ) ),
			);
		}

		/** Removes every usage row older than the retention period. */
		public static function purge_usage(): void {
			global $wpdb;
			$cut = gmdate( 'Y-m-d', time() - self::RETAIN_DAYS * DAY_IN_SECONDS );
			$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . self::metrics() . ' WHERE day < %s', $cut ) );
			$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . self::active() . ' WHERE day < %s', $cut ) );
			$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . self::visitors() . ' WHERE last_day < %s', $cut ) );
			$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . self::errors() . ' WHERE last_seen < %s', $cut ) );
		}

		// ------------------------------------------------------------------ PHP runtime check
		/**
		 * Is the PHP this site runs on patched? 'ok', 'update' (a patched release exists for this branch) or 'eol' (the branch gets
		 * no fixes). Advice only: the plugin cannot patch PHP, and distribution builds may carry fixes under older version numbers,
		 * so the message says to confirm with the host. Never shown to visitors.
		 */
		public static function php_advisory( ?string $version = null ): array {
			$v      = $version ?? PHP_VERSION;
			$branch = implode( '.', array_slice( explode( '.', $v ), 0, 2 ) );
			if ( version_compare( $branch, '8.2', '<' ) ) {
				return array( 'level' => 'eol', 'message' => sprintf( 'This site runs PHP %s, which no longer receives security fixes, including the October 2026 emergency fixes for CVE-2026-109618 and CVE-2026-109619 (critical, remote code execution). Ask your host to move it to PHP 8.2.35 or newer (8.3.36, 8.4.27 or 8.5.12 recommended).', $v ) );
			}
			$fixed = self::PHP_PATCHED[ $branch ] ?? null;
			if ( null !== $fixed && version_compare( $v, $fixed, '<' ) ) {
				return array( 'level' => 'update', 'message' => sprintf( 'This site runs PHP %1$s. PHP %2$s fixes two critical vulnerabilities (CVE-2026-109618 and CVE-2026-109619, remote code execution). Ask your host to apply it, or confirm that your build already carries the fix.', $v, $fixed ) );
			}
			return array( 'level' => 'ok', 'message' => sprintf( 'PHP %s includes the October 2026 security fixes.', $v ) );
		}

		public static function php_notice(): void {
			$a = self::php_advisory();
			if ( 'ok' !== $a['level'] && current_user_can( 'manage_options' ) ) {
				echo '<div class="notice notice-error"><p><strong>Mimir Vault:</strong> ' . esc_html( $a['message'] ) . '</p></div>';
			}
		}

		// ------------------------------------------------------------------ housekeeping and admin
		/** Daily: removes accounts unused for the number of days set under Settings, Mimir Vault (0 keeps them). */
		public static function housekeeping(): void {
			global $wpdb;
			self::install();
			self::purge_usage();
			$days = (int) get_option( 'mimir_vault_purge_inactive_days', 0 );
			if ( $days >= 90 ) {
				$cut = gmdate( 'Y-m-d H:i:s', time() - $days * DAY_IN_SECONDS );
				$ids = $wpdb->get_col( $wpdb->prepare( 'SELECT id FROM ' . self::accounts() . ' WHERE last_seen < %s', $cut ) );
				foreach ( (array) $ids as $id ) {
					$wpdb->delete( self::vaults(), array( 'account_id' => $id ), array( '%s' ) );
					$wpdb->delete( self::accounts(), array( 'id' => $id ), array( '%s' ) );
				}
			}
		}

		public static function admin_menu(): void {
			add_options_page( 'Mimir Vault', 'Mimir Vault', 'manage_options', 'mimir-vault', array( __CLASS__, 'admin_page' ) );
		}

		/** Aggregate numbers only: how many vaults, how recently used, how much space. Nothing about any one person. */
		public static function stats(): array {
			global $wpdb;
			self::install();
			$a  = self::accounts();
			$c  = fn( string $col, int $days ) => (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM $a WHERE $col >= %s", gmdate( 'Y-m-d H:i:s', time() - $days * DAY_IN_SECONDS ) ) );
			return array(
				'accounts'  => (int) $wpdb->get_var( "SELECT COUNT(*) FROM $a" ),
				'new_7'     => $c( 'created', 7 ),
				'new_30'    => $c( 'created', 30 ),
				'active_1'  => $c( 'last_seen', 1 ),
				'active_7'  => $c( 'last_seen', 7 ),
				'active_30' => $c( 'last_seen', 30 ),
				'bytes'     => (int) $wpdb->get_var( 'SELECT COALESCE(SUM(size),0) FROM ' . self::vaults() ),
			);
		}

		public static function admin_page(): void {
			if ( ! current_user_can( 'manage_options' ) ) {
				return;
			}
			if ( isset( $_POST['mimir_vault_days'] ) && check_admin_referer( 'mimir_vault_settings' ) ) {
				update_option( 'mimir_vault_purge_inactive_days', max( 0, (int) $_POST['mimir_vault_days'] ), false );
			}
			$s   = self::stats();
			$php = self::php_advisory();
			echo '<div class="wrap"><h1>Mimir Vault</h1>';
			echo '<p><strong>PHP:</strong> ' . esc_html( $php['message'] ) . '</p>';
			echo '<p>Vaults are encrypted in the visitor\'s browser. This screen shows totals only; nothing here can identify or read a person\'s data.</p>';
			echo '<table class="widefat striped" style="max-width:480px"><tbody>';
			$rows = array( 'Vaults' => $s['accounts'], 'New in the last 7 days' => $s['new_7'], 'New in the last 30 days' => $s['new_30'], 'Used in the last day' => $s['active_1'],
				'Used in the last 7 days' => $s['active_7'], 'Used in the last 30 days' => $s['active_30'], 'Space used (KB)' => round( $s['bytes'] / 1024 ) );
			foreach ( $rows as $label => $n ) {
				echo '<tr><th>' . esc_html( $label ) . '</th><td>' . esc_html( (string) $n ) . '</td></tr>';
			}
			echo '</tbody></table>';
			self::usage_tables();
			echo '<h2>Endpoint</h2><p><code>' . esc_html( rest_url( self::NS ) ) . '</code> (set this as MIMIR_VAULT_URL when building the site)</p>';
			echo '<h2>Retention</h2><form method="post">';
			wp_nonce_field( 'mimir_vault_settings' );
			echo '<p><label>Delete vaults unused for <input type="number" name="mimir_vault_days" min="0" step="30" value="' . esc_attr( (string) (int) get_option( 'mimir_vault_purge_inactive_days', 0 ) ) . '" style="width:90px"> days (0 keeps them; the minimum is 90). Say so in your privacy notice before turning this on.</label></p>';
			submit_button( 'Save', 'primary', 'submit', false );
			echo '</form></div>';
		}

		/** Usage numbers for the admin screen. Counts only: nothing here is about one person or what they looked at. */
		private static function usage_tables(): void {
			$u = self::usage();
			$table = function ( string $title, array $rows, array $cols ) {
				echo '<h3>' . esc_html( $title ) . '</h3>';
				if ( ! $rows ) {
					echo '<p><em>Nothing yet.</em></p>';
					return;
				}
				echo '<table class="widefat striped" style="max-width:640px"><thead><tr>';
				foreach ( $cols as $label ) {
					echo '<th>' . esc_html( $label ) . '</th>';
				}
				echo '</tr></thead><tbody>';
				foreach ( $rows as $row ) {
					echo '<tr>';
					foreach ( array_keys( $cols ) as $k ) {
						echo '<td>' . esc_html( (string) ( $row[ $k ] ?? '' ) ) . '</td>';
					}
					echo '</tr>';
				}
				echo '</tbody></table>';
			};
			echo '<h2>Usage (only from visitors who opted in; errors need no opt-in)</h2>';
			echo '<p>Active visitors: <strong>' . esc_html( (string) $u['dau'] ) . '</strong> today, <strong>' . esc_html( (string) $u['wau'] ) . '</strong> in 7 days, <strong>' . esc_html( (string) $u['mau'] ) . '</strong> in 30 days. New in 30 days: ' . esc_html( (string) $u['new_30'] ) . '. Visits in 30 days: ' . esc_html( (string) $u['visits'] ) . '. Errors in 30 days: ' . esc_html( (string) $u['error_n'] ) . '.</p>';
			$table( 'Active visitors per day (last 14 days)', $u['daily'], array( 'day' => 'Day', 'n' => 'Visitors' ) );
			$ret = array();
			foreach ( array( 'd1' => 'First seen 1 day ago', 'd7' => 'First seen 7 days ago', 'd30' => 'First seen 30 days ago' ) as $k => $label ) {
				$ret[] = array( 'label' => $label, 'cohort' => $u['retained'][ $k ]['cohort'], 'returned' => $u['retained'][ $k ]['returned'] );
			}
			$table( 'Came back at least once', $ret, array( 'label' => 'Cohort', 'cohort' => 'Visitors', 'returned' => 'Returned' ) );
			foreach ( array( 'device' => 'Device', 'browser' => 'Browser', 'os' => 'System', 'screen' => 'Screen size', 'lang' => 'Language', 'version' => 'Site version', 'route' => 'Pages (30 days)', 'feature' => 'Features used (30 days)', 'lcp' => 'Time to main content (30 days)' ) as $k => $title ) {
				$table( $title, $u[ $k ], array( 'v' => $title, 'n' => 'Count' ) );
			}
			$table( 'Errors (30 days)', $u['errors'], array( 'msg' => 'Message', 'route' => 'Page', 'ver' => 'Version', 'n' => 'Times', 'last_seen' => 'Last seen' ) );
		}

		public static function privacy_text(): void {
			if ( function_exists( 'wp_add_privacy_policy_content' ) ) {
				wp_add_privacy_policy_content( 'Mimir Vault', wp_kses_post( '<p>Mimir accounts store one encrypted file per recovery key. It is encrypted in the visitor\'s browser before it is sent, so the site cannot read it. The site also keeps a key-derived identifier, a keyed hash of a key-derived secret, and the creation and last-use dates. There are no emails, names or cookies. Visitors can export or delete their vault from the Mimir account page at any time.</p>' ) );
			}
		}
	}

	Mimir_Vault::boot();
}
