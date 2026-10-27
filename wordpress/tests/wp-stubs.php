<?php
/**
 * A small stand-in for WordPress (sqlite for $wpdb, arrays for options and transients) that loads the real Mimir Vault
 * plugin file. Used by harness.php (contract tests) and serve.php (an HTTP server for browser tests).
 */
declare(strict_types=1);
error_reporting( E_ALL );
set_error_handler( function ( $no, $str, $file, $line ) { throw new ErrorException( $str, 0, $no, $file, $line ); } );

define( 'ABSPATH', sys_get_temp_dir() . '/mimir-wp-' . getmypid() . '/' );
is_dir( ABSPATH . 'wp-admin/includes' ) || mkdir( ABSPATH . 'wp-admin/includes', 0777, true );
file_put_contents( ABSPATH . 'wp-admin/includes/upgrade.php', '<?php' );
const HOUR_IN_SECONDS = 3600; const MINUTE_IN_SECONDS = 60; const DAY_IN_SECONDS = 86400; const ARRAY_A = 'ARRAY_A';

$GLOBALS['opts'] = array(); $GLOBALS['trans'] = array();
// With MIMIR_TEST_STATE set (serve.php), options, transients and the database survive between requests.
$state = getenv( 'MIMIR_TEST_STATE' );
if ( $state && is_file( "$state.json" ) ) { [ $GLOBALS['opts'], $GLOBALS['trans'] ] = json_decode( (string) file_get_contents( "$state.json" ), true ); }
if ( $state ) { register_shutdown_function( fn() => file_put_contents( "$state.json", json_encode( array( $GLOBALS['opts'], $GLOBALS['trans'] ) ) ) ); } $GLOBALS['routes'] = array(); $GLOBALS['hooks'] = array(); $GLOBALS['server_ip'] = '203.0.113.7';
function get_option( $k, $d = false ) { return $GLOBALS['opts'][ $k ] ?? $d; }
function update_option( $k, $v, $a = null ) { $GLOBALS['opts'][ $k ] = $v; return true; }
function get_transient( $k ) { return $GLOBALS['trans'][ $k ] ?? false; }
function set_transient( $k, $v, $e = 0 ) { $GLOBALS['trans'][ $k ] = $v; return true; }
function delete_transient( $k ) { unset( $GLOBALS['trans'][ $k ] ); return true; }
function wp_generate_password( $n = 12 ) { return substr( bin2hex( random_bytes( $n ) ), 0, $n ); }
function add_action( $h, $cb ) { $GLOBALS['hooks'][ $h ][] = $cb; }
function add_filter( $h, $cb ) { $GLOBALS['hooks'][ $h ][] = $cb; }
function apply_filters( $h, $v ) { return $v; }
function wp_next_scheduled( $h ) { return false; }
function wp_schedule_event() { return true; }
function wp_add_privacy_policy_content() {}
function wp_kses_post( $s ) { return $s; }
function add_options_page() {}
function wp_json_encode( $v ) { return json_encode( $v ); }
function esc_html( $s ) { return htmlspecialchars( (string) $s ); }
function current_user_can( $c ) { return true; }
function is_wp_error( $x ) { return $x instanceof WP_Error; }
function rest_url( $p = '' ) { return 'https://example.test/wp-json/' . $p; }
function register_rest_route( $ns, $route, $args ) { $GLOBALS['routes'][ "/$ns$route" ] = $args; }

class WP_Error { public function __construct( public string $code = '', public string $message = '', public array $data = array() ) {} }
class WP_REST_Response { public function __construct( public $data = null, public int $status = 200 ) {} }
class WP_REST_Request implements ArrayAccess {
	public function __construct( public array $p ) {}
	public function get_json_params() { return $this->p; }
	public function offsetExists( mixed $o ): bool { return isset( $this->p[ $o ] ); }
	public function offsetGet( mixed $o ): mixed { return $this->p[ $o ] ?? null; }
	public function offsetSet( mixed $o, mixed $v ): void { $this->p[ $o ] = $v; }
	public function offsetUnset( mixed $o ): void { unset( $this->p[ $o ] ); }
}

/** sqlite behind the few $wpdb methods the plugin uses. */
class Fake_Wpdb {
	public string $prefix = 'wp_';
	public PDO $pdo;
	public function __construct() { $this->pdo = new PDO( getenv( 'MIMIR_TEST_STATE' ) ? 'sqlite:' . getenv( 'MIMIR_TEST_STATE' ) . '.db' : 'sqlite::memory:' ); $this->pdo->setAttribute( PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION ); }
	public function get_charset_collate() { return ''; }
	public function prepare( $q, ...$a ) {
		$i = 0;
		return preg_replace_callback( '/%[sd]/', function ( $m ) use ( &$i, $a ) { $v = $a[ $i++ ]; return '%d' === $m[0] ? (string) (int) $v : $this->pdo->quote( (string) $v ); }, $q );
	}
	public function get_results( $q, $o = null ) { return $this->pdo->query( $q )->fetchAll( PDO::FETCH_ASSOC ); }
	public function get_row( $q, $o = null ) { $r = $this->pdo->query( $q )->fetch( PDO::FETCH_ASSOC ); return $r ?: null; }
	public function get_var( $q ) { $r = $this->pdo->query( $q )->fetch( PDO::FETCH_NUM ); return $r ? $r[0] : null; }
	public function get_col( $q ) { return $this->pdo->query( $q )->fetchAll( PDO::FETCH_COLUMN ); }
	public function query( $q ) {
		// MySQL upserts, translated for sqlite.
		$q = preg_replace( '/^INSERT IGNORE/', 'INSERT OR IGNORE', $q );
		if ( preg_match( '/^INSERT INTO (\S+) \(([^)]*)\) VALUES \((.*)\) ON DUPLICATE KEY UPDATE (.*)$/s', $q, $m ) ) {
			$key = array( 'wp_mimir_metrics' => 'day, k, v', 'wp_mimir_errors' => 'id' )[ $m[1] ] ?? 'id';
			$q   = "INSERT INTO {$m[1]} ({$m[2]}) VALUES ({$m[3]}) ON CONFLICT($key) DO UPDATE SET " . preg_replace( '/\bn = n \+ 1/', 'n = n + 1', $m[4] );
		}
		return $this->pdo->exec( $q );
	}
	public function insert( $t, $d, $f = null ) { $c = implode( ',', array_keys( $d ) ); $p = implode( ',', array_fill( 0, count( $d ), '?' ) ); $s = $this->pdo->prepare( "INSERT INTO $t ($c) VALUES ($p)" ); $s->execute( array_values( $d ) ); return 1; }
	public function update( $t, $d, $w, $f = null, $wf = null ) { $set = implode( ',', array_map( fn( $k ) => "$k = ?", array_keys( $d ) ) ); $wh = implode( ' AND ', array_map( fn( $k ) => "$k = ?", array_keys( $w ) ) ); $s = $this->pdo->prepare( "UPDATE $t SET $set WHERE $wh" ); $s->execute( array_merge( array_values( $d ), array_values( $w ) ) ); return $s->rowCount(); }
	public function delete( $t, $w, $f = null ) { $wh = implode( ' AND ', array_map( fn( $k ) => "$k = ?", array_keys( $w ) ) ); $s = $this->pdo->prepare( "DELETE FROM $t WHERE $wh" ); $s->execute( array_values( $w ) ); return $s->rowCount(); }
}
$wpdb = new Fake_Wpdb();
function dbDelta( $sql ) {
	global $wpdb;
	$sql = preg_replace( '/^\s*KEY .*$/m', '', $sql );
	$sql = preg_replace( '/,\s*\n\s*\)/', "\n)", $sql );
	$sql = str_replace( array( 'unsigned', 'PRIMARY KEY  (' ), array( '', 'PRIMARY KEY (' ), $sql );
	$wpdb->pdo->exec( preg_replace( '/\)\s*;?\s*$/', ')', trim( $sql ) ) );
}

require __DIR__ . '/../mimir-vault/mimir-vault.php';

/** What WordPress does before a callback: required, default, validate, sanitize; then the callback. */
function call( string $route, array $params, string $ip = '203.0.113.7' ): array {
	$_SERVER['REMOTE_ADDR'] = $ip;
	Mimir_Vault::routes();
	$def = $GLOBALS['routes'][ "/mimir/v1$route" ] ?? null;
	if ( ! $def ) { return array( 404, array() ); }
	foreach ( $def['args'] ?? array() as $name => $spec ) {
		if ( ! array_key_exists( $name, $params ) ) {
			if ( ! empty( $spec['required'] ) ) { return array( 400, array( 'code' => 'rest_missing_callback_param' ) ); }
			if ( array_key_exists( 'default', $spec ) ) { $params[ $name ] = $spec['default']; }
			continue;
		}
		if ( isset( $spec['validate_callback'] ) && ! ( $spec['validate_callback'] )( $params[ $name ] ) ) { return array( 400, array( 'code' => 'rest_invalid_param', 'param' => $name ) ); }
		if ( isset( $spec['sanitize_callback'] ) ) { $params[ $name ] = ( $spec['sanitize_callback'] )( $params[ $name ] ); }
	}
	$res = ( $def['callback'] )( new WP_REST_Request( $params ) );
	if ( $res instanceof WP_Error ) { return array( $res->data['status'], array_merge( array( 'code' => $res->code, 'message' => $res->message ), array_diff_key( $res->data, array( 'status' => 1 ) ) ) ); }
	return array( $res->status, (array) $res->data );
}

