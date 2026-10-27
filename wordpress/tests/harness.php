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

Mimir_Vault::housekeeping();
$origins = Mimir_Vault::origins( array() ); check( 'the Mimir origin is allowed for browsers', in_array( 'https://mimir.terratalesmedia.world', $origins, true ) );
$src = file_get_contents( __DIR__ . '/../mimir-vault/mimir-vault.php' );
check( 'the plugin sets no cookies', ! preg_match( '/setcookie|session_start|wp_set_auth_cookie/', $src ) );
check( 'the plugin never logs', ! preg_match( '/error_log|var_dump|print_r/', $src ) );

echo $fails ? "\n$fails failed\n" : "\nall passed\n";
exit( $fails ? 1 : 0 );
