<?php
/**
 * Runs the Mimir Vault plugin against the WordPress stand-in in wp-stubs.php and checks its REST contract. Not a
 * substitute for trying it on a real site, but it runs the real plugin code.
 *
 *   php wordpress/tests/harness.php
 */
declare(strict_types=1);
require __DIR__ . '/wp-stubs.php';

$fails = 0;
function check( string $name, bool $ok, $detail = '' ): void { global $fails; echo ( $ok ? 'ok   ' : 'FAIL ' ) . $name . ( $ok ? '' : ' ' . json_encode( $detail ) ) . "\n"; if ( ! $ok ) { $fails++; } }

$id = str_repeat( 'a1', 16 ); $auth = str_repeat( 'Q', 43 ); $blob = str_repeat( 'A', 60 );

[ $s, $d ] = call( '/health', array() ); check( 'health', 200 === $s && true === $d['ok'] );
[ $s, $d ] = call( '/vault/create', array( 'id' => $id, 'auth' => $auth, 'blob' => $blob, 'consent_version' => '2026-10', 'analytics' => false ) ); check( 'create', 201 === $s && 1 === $d['version'], $d );
[ $s ] = call( '/vault/create', array( 'id' => $id, 'auth' => $auth, 'blob' => $blob ) ); check( 'create twice is refused', 409 === $s );
[ $s ] = call( '/vault/create', array( 'id' => 'short', 'auth' => $auth, 'blob' => $blob ) ); check( 'bad id format is refused', 400 === $s );
[ $s ] = call( '/vault/create', array( 'id' => str_repeat( 'b2', 16 ), 'auth' => $auth, 'blob' => str_repeat( 'A', Mimir_Vault::MAX_BLOB + 1 ) ) ); check( 'oversize blob is refused', 400 === $s );
[ $s ] = call( '/vault/create', array( 'id' => str_repeat( 'b2', 16 ), 'auth' => $auth, 'blob' => 'not base64url!!' . $blob ) ); check( 'non base64url blob is refused', 400 === $s );

$row = $wpdb->get_row( "SELECT * FROM wp_mimir_accounts WHERE id = '$id'" );
check( 'the stored secret is a keyed hash, not the secret', 64 === strlen( $row['auth_hash'] ) && $row['auth_hash'] !== $auth && ! str_contains( json_encode( $row ), $auth ), $row );

[ $s, $d ] = call( '/vault/open', array( 'id' => $id, 'auth' => $auth ) ); check( 'open with the key', 200 === $s && $d['blob'] === $blob && 1 === $d['version'], $d );
[ $s1, $d1 ] = call( '/vault/open', array( 'id' => $id, 'auth' => str_repeat( 'R', 43 ) ) );
[ $s2, $d2 ] = call( '/vault/open', array( 'id' => str_repeat( 'c3', 16 ), 'auth' => $auth ) );
check( 'wrong secret and unknown id answer identically', 401 === $s1 && $s1 === $s2 && $d1 === $d2, array( $d1, $d2 ) );

$blob2 = str_repeat( 'B', 80 );
[ $s, $d ] = call( '/vault/save', array( 'id' => $id, 'auth' => $auth, 'blob' => $blob2, 'if_match' => 1 ) ); check( 'save with the current version', 200 === $s && 2 === $d['version'], $d );
[ $s, $d ] = call( '/vault/save', array( 'id' => $id, 'auth' => $auth, 'blob' => str_repeat( 'C', 90 ), 'if_match' => 1 ) );
check( 'a stale save conflicts and returns the newer copy', 409 === $s && 'conflict' === $d['code'] && $d['blob'] === $blob2 && 2 === $d['version'], $d );
[ $s, $d ] = call( '/vault/open', array( 'id' => $id, 'auth' => $auth ) ); check( 'the conflict did not overwrite', $d['blob'] === $blob2 );

$nid = str_repeat( 'd4', 16 ); $nauth = str_repeat( 'S', 43 ); $blob3 = str_repeat( 'D', 70 );
[ $s, $d ] = call( '/vault/rotate', array( 'id' => $id, 'auth' => $auth, 'blob' => $blob3, 'new_id' => $nid, 'new_auth' => $nauth ) ); check( 'rotate', 200 === $s && 3 === $d['version'], $d );
[ $s ] = call( '/vault/open', array( 'id' => $id, 'auth' => $auth ) ); check( 'the old key no longer opens it', 401 === $s );
[ $s, $d ] = call( '/vault/open', array( 'id' => $nid, 'auth' => $nauth ) ); check( 'the new key opens the re-encrypted vault', 200 === $s && $d['blob'] === $blob3 );

$st = Mimir_Vault::stats(); check( 'stats are totals only', 1 === $st['accounts'] && 1 === $st['active_1'] && $st['bytes'] === strlen( $blob3 ), $st );

[ $s ] = call( '/vault/delete', array( 'id' => $nid, 'auth' => $nauth ) ); check( 'delete', 200 === $s );
[ $s ] = call( '/vault/open', array( 'id' => $nid, 'auth' => $nauth ) ); check( 'a deleted vault is gone', 401 === $s );
check( 'no rows remain', 0 === (int) $wpdb->get_var( 'SELECT COUNT(*) FROM wp_mimir_vaults' ) + (int) $wpdb->get_var( 'SELECT COUNT(*) FROM wp_mimir_accounts' ) );

$last = 0;
for ( $i = 0; $i < 25; $i++ ) { [ $last ] = call( '/vault/open', array( 'id' => str_repeat( 'e5', 16 ), 'auth' => str_repeat( 'T', 43 ) ), '198.51.100.9' ); }
check( 'repeated wrong keys are rate limited', 429 === $last, $last );
[ $s ] = call( '/vault/open', array( 'id' => str_repeat( 'e5', 16 ), 'auth' => str_repeat( 'T', 43 ) ), '198.51.100.10' ); check( 'a vault under attack stays locked from other connections too', 429 === $s );
[ $s ] = call( '/vault/open', array( 'id' => str_repeat( 'f6', 16 ), 'auth' => str_repeat( 'T', 43 ) ), '198.51.100.10' ); check( 'a different vault from another connection is not affected', 401 === $s );
for ( $i = 0; $i < 11; $i++ ) { [ $last ] = call( '/vault/create', array( 'id' => sprintf( '%032x', $i + 99 ), 'auth' => $auth, 'blob' => $blob ), '192.0.2.1' ); }
check( 'creating vaults is rate limited per connection', 429 === $last, $last );

// ---- consent and telemetry
$cid = str_repeat( 'ab', 16 );
call( '/vault/create', array( 'id' => $cid, 'auth' => $auth, 'blob' => $blob ), '192.0.2.50' );
[ $s ] = call( '/vault/consent', array( 'id' => $cid, 'auth' => $auth, 'consent_version' => '2026-10', 'analytics' => true ), '192.0.2.50' );
$crow = $wpdb->get_row( "SELECT consent_version, consent_analytics FROM wp_mimir_accounts WHERE id = '$cid'" );
check( 'consent is recorded for an account', 200 === $s && '2026-10' === $crow['consent_version'] && 1 === (int) $crow['consent_analytics'], $crow );

$vid = str_repeat( '1f', 16 );
$report = array( 'vid' => $vid, 'ver' => 'abc123def456', 'start' => true, 'device' => 'mobile', 'browser' => 'chrome', 'os' => 'android', 'screen' => 'xs', 'lang' => 'en',
	'events' => array( array( 'n' => 'pv', 'r' => 'for-you' ), array( 'n' => 'pv', 'r' => 'Bad Route!' ), array( 'n' => 'ft', 'f' => 'swipe' ), array( 'n' => 'pf', 'lcp' => 1800 ), array( 'n' => 'xx' ) ) );
[ $s, $d ] = call( '/telemetry', $report, '192.0.2.60' ); check( 'a consented report is accepted and only valid events are kept', 202 === $s && 3 === $d['kept'], $d );
$us = Mimir_Vault::usage();
check( 'active visitors are counted', 1 === $us['dau'] && 1 === $us['mau'] && 1 === $us['new_30'], $us );
check( 'device, route, feature and speed are counted', 'mobile' === $us['device'][0]['v'] && 'for-you' === $us['route'][0]['v'] && 'swipe' === $us['feature'][0]['v'] && '1 to 2.5s' === $us['lcp'][0]['v'], $us );
check( 'a made-up route is not stored', 1 === count( $us['route'] ), $us['route'] );
$report['device'] = 'toaster'; $report['vid'] = str_repeat( '2e', 16 );
call( '/telemetry', $report, '192.0.2.60' );
check( 'a device class outside the list is dropped', ! in_array( 'toaster', array_column( Mimir_Vault::usage()['device'], 'v' ), true ) );

[ $s, $d ] = call( '/telemetry', array( 'events' => array( array( 'n' => 'pv', 'r' => 'home' ), array( 'n' => 'er', 'm' => 'TypeError: x is undefined', 'r' => 'home' ) ), 'ver' => 'abc123def456' ), '192.0.2.61' );
check( 'without an opt-in only errors are kept', 202 === $s && 1 === $d['kept'], $d );
call( '/telemetry', array( 'events' => array( array( 'n' => 'er', 'm' => 'TypeError: x is undefined', 'r' => 'home' ) ), 'ver' => 'abc123def456' ), '192.0.2.61' );
$us = Mimir_Vault::usage(); check( 'the same error is counted, not duplicated', 1 === count( $us['errors'] ) && 2 === (int) $us['errors'][0]['n'] && 2 === $us['error_n'], $us['errors'] );
[ $s ] = call( '/telemetry', array( 'events' => array( array( 'n' => 'er', 'm' => str_repeat( 'x', 9000 ) ) ) ), '192.0.2.62' ); check( 'an oversize report is refused', 413 === $s, $s );

$wpdb->query( "INSERT INTO wp_mimir_metrics (day, k, v, n) VALUES ('2020-01-01', 'route', 'old', 5)" );
$wpdb->query( "INSERT INTO wp_mimir_active (day, vid) VALUES ('2020-01-01', 'deadbeefdeadbeef')" );
Mimir_Vault::purge_usage();
check( 'usage older than 13 months is purged', 0 === (int) $wpdb->get_var( "SELECT COUNT(*) FROM wp_mimir_metrics WHERE day = '2020-01-01'" ) + (int) $wpdb->get_var( "SELECT COUNT(*) FROM wp_mimir_active WHERE day = '2020-01-01'" ) );
$dump = '';
foreach ( array( 'wp_mimir_metrics', 'wp_mimir_active', 'wp_mimir_visitors', 'wp_mimir_errors', 'wp_mimir_accounts' ) as $t ) { $dump .= json_encode( $wpdb->get_results( "SELECT * FROM $t" ) ); }
check( 'no address and no raw visitor id is stored', ! str_contains( $dump, '192.0.2.' ) && ! str_contains( $dump, $vid ), '' );

Mimir_Vault::housekeeping();
$origins = Mimir_Vault::origins( array() ); check( 'the Mimir origin is allowed for browsers', in_array( 'https://mimir.terratalesmedia.world', $origins, true ) );
$src = file_get_contents( __DIR__ . '/../mimir-vault/mimir-vault.php' );
check( 'the plugin sets no cookies', ! preg_match( '/setcookie|session_start|wp_set_auth_cookie/', $src ) );
check( 'the plugin never logs', ! preg_match( '/error_log|var_dump|print_r/', $src ) );

echo $fails ? "\n$fails failed\n" : "\nall passed\n";
exit( $fails ? 1 : 0 );
