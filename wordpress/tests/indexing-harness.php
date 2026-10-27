<?php
/**
 * Checks the Terratales Indexing Fixes plugin against a small stand-in for WordPress.   php wordpress/tests/indexing-harness.php
 */
declare(strict_types=1);
define( 'ABSPATH', '/tmp/' );
$GLOBALS['hooks'] = array(); $GLOBALS['ctx'] = array(); $GLOBALS['sent'] = array(); $GLOBALS['redirect'] = null;
function add_action( $h, $cb, $p = 10 ) { $GLOBALS['hooks'][ $h ][] = $cb; }
function is_attachment() { return ! empty( $GLOBALS['ctx']['attachment'] ); }
function is_feed() { return ! empty( $GLOBALS['ctx']['feed'] ); }
function is_front_page() { return ! empty( $GLOBALS['ctx']['front'] ); }
function get_queried_object_id() { return 16; }
function wp_get_attachment_url( $id ) { return $GLOBALS['ctx']['file'] ?? false; }
function wp_safe_redirect( $url, $status, $by ) { $GLOBALS['redirect'] = array( $url, $status ); throw new RuntimeException( 'exit' ); }
function home_url( $p = '' ) { return 'https://terratalesmedia.world' . $p; }
function esc_url( $u ) { return $u; }
function get_site_icon_url( $s ) { return 'https://terratalesmedia.world/icon-512.png'; }
function wp_json_encode( $v, $f = 0 ) { return json_encode( $v, $f ); }
require __DIR__ . '/../terratales-indexing/terratales-indexing.php';

$fails = 0;
function check( string $n, bool $ok, $d = '' ): void { global $fails; echo ( $ok ? 'ok   ' : 'FAIL ' ) . $n . ( $ok ? '' : ' ' . json_encode( $d ) ) . "\n"; if ( ! $ok ) { $fails++; } }
function run( string $hook ): string { ob_start(); try { foreach ( $GLOBALS['hooks'][ $hook ] ?? array() as $cb ) { $cb(); } } catch ( RuntimeException $e ) { } return (string) ob_get_clean(); }

$GLOBALS['ctx'] = array( 'attachment' => true, 'file' => 'https://terratalesmedia.world/wp-content/uploads/a.png' ); $GLOBALS['redirect'] = null;
run( 'template_redirect' );
check( 'an attachment page redirects permanently to its file', $GLOBALS['redirect'] === array( 'https://terratalesmedia.world/wp-content/uploads/a.png', 301 ), $GLOBALS['redirect'] );
$GLOBALS['ctx'] = array( 'attachment' => true ); $GLOBALS['redirect'] = null; run( 'template_redirect' );
check( 'an attachment with no file is left alone', null === $GLOBALS['redirect'] );
$GLOBALS['ctx'] = array(); $GLOBALS['redirect'] = null; run( 'template_redirect' );
check( 'ordinary pages are not redirected', null === $GLOBALS['redirect'] );

$GLOBALS['ctx'] = array( 'front' => true ); $out = run( 'wp_head' );
check( 'the home page gets a canonical link', str_contains( $out, '<link rel="canonical" href="https://terratalesmedia.world/" />' ), $out );
preg_match( '#<script type="application/ld\+json">(.*)</script>#s', $out, $m ); $j = json_decode( $m[1] ?? 'null', true );
check( 'Organization data is valid JSON with the id Mimir refers to', is_array( $j ) && 'https://terratalesmedia.world/#org' === $j['@graph'][0]['@id'] && 'IN' === $j['@graph'][0]['address']['addressCountry'], $m );
check( 'WebSite names the organization as publisher', 'https://terratalesmedia.world/#org' === ( $j['@graph'][1]['publisher']['@id'] ?? '' ) );
$GLOBALS['ctx'] = array( 'front' => false ); check( 'other pages get nothing extra in the head', '' === run( 'wp_head' ) );

check( 'feeds are marked noindex with a header', str_contains( file_get_contents( __DIR__ . '/../terratales-indexing/terratales-indexing.php' ), "X-Robots-Tag: noindex, follow" ) && in_array( array( 'Terratales_Indexing', 'feeds' ), $GLOBALS['hooks']['template_redirect'], true ) );
check( 'the plugin touches no cookies, options or database', ! preg_match( '/setcookie|update_option|\$wpdb|file_put_contents/', file_get_contents( __DIR__ . '/../terratales-indexing/terratales-indexing.php' ) ) );
echo $fails ? "\n$fails failed\n" : "\nall passed\n"; exit( $fails ? 1 : 0 );
