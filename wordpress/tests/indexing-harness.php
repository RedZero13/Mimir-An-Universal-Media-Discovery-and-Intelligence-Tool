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
function is_singular() { return ! empty( $GLOBALS['ctx']['post'] ); }
function get_permalink( $id ) { return 'https://terratalesmedia.world/' . $GLOBALS['ctx']['post']['slug'] . '/'; }
function get_the_title( $id ) { return $GLOBALS['ctx']['post']['title']; }
function get_post_field( $f, $id ) { return $GLOBALS['ctx']['post']['slug']; }
function get_the_excerpt( $id ) { return $GLOBALS['ctx']['post']['excerpt'] ?? ''; }
function get_post_type( $id ) { return $GLOBALS['ctx']['post']['type'] ?? 'page'; }
function get_the_modified_date( $f, $id ) { return '2026-10-01T00:00:00+00:00'; }
function get_the_date( $f, $id ) { return '2026-09-01T00:00:00+00:00'; }
function wp_strip_all_tags( $t ) { return strip_tags( $t ); }
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
check( 'the home page also gets a WebPage node', 'WebPage' === ( $j['@graph'][2]['@type'] ?? '' ) );
$GLOBALS['ctx'] = array( 'front' => false ); check( 'archives and other non-page views get nothing extra in the head', '' === run( 'wp_head' ) );

function schema_for( array $post ): array { $GLOBALS['ctx'] = array( 'post' => $post ); $o = run( 'wp_head' ); preg_match( '#<script type="application/ld\+json">(.*)</script>#s', $o, $m ); return json_decode( $m[1] ?? 'null', true ) ?? array(); }
$g = schema_for( array( 'slug' => 'about', 'title' => 'About Us' ) )['@graph'] ?? array();
check( 'About is an AboutPage with breadcrumbs', 'AboutPage' === ( $g[0]['@type'] ?? '' ) && 'BreadcrumbList' === ( $g[1]['@type'] ?? '' ) && 2 === count( $g[1]['itemListElement'] ), $g );
check( 'pages tie to the site and organization by id', 'https://terratalesmedia.world/#site' === ( $g[0]['isPartOf']['@id'] ?? '' ) && 'https://terratalesmedia.world/#org' === ( $g[0]['publisher']['@id'] ?? '' ) );
check( 'a page with no excerpt gets no invented description', ! isset( $g[0]['description'] ) );
$g = schema_for( array( 'slug' => 'contact', 'title' => 'Contact' ) )['@graph'] ?? array();
check( 'Contact is a ContactPage about the organization', 'ContactPage' === ( $g[0]['@type'] ?? '' ) && '#org' === substr( $g[0]['mainEntity']['@id'] ?? '', -4 ) );
$g = schema_for( array( 'slug' => 'cinema', 'title' => 'Cinema', 'excerpt' => '<p>Films we make.</p>' ) )['@graph'] ?? array();
check( 'a realm page names its Service, provided by the organization', 'Service' === ( $g[2]['@type'] ?? '' ) && 'Films we make.' === ( $g[2]['description'] ?? '' ) && '#org' === substr( $g[2]['provider']['@id'] ?? '', -4 ) && 'https://terratalesmedia.world/cinema/#service' === ( $g[0]['mainEntity']['@id'] ?? '' ), $g );
$g = schema_for( array( 'slug' => 'hello', 'title' => 'Hello', 'type' => 'post' ) )['@graph'] ?? array();
check( 'posts are Articles with dates', 'Article' === ( $g[0]['@type'] ?? '' ) && isset( $g[0]['datePublished'], $g[0]['headline'] ) );
$g = schema_for( array( 'slug' => 'privacy-policy', 'title' => 'Privacy <b>Policy</b>' ) )['@graph'] ?? array();
check( 'other pages are plain WebPages with tags stripped from the name', 'WebPage' === ( $g[0]['@type'] ?? '' ) && 'Privacy Policy' === ( $g[0]['name'] ?? '' ) );

check( 'feeds are marked noindex with a header', str_contains( file_get_contents( __DIR__ . '/../terratales-indexing/terratales-indexing.php' ), "X-Robots-Tag: noindex, follow" ) && in_array( array( 'Terratales_Indexing', 'feeds' ), $GLOBALS['hooks']['template_redirect'], true ) );
check( 'the plugin touches no cookies, options or database', ! preg_match( '/setcookie|update_option|\$wpdb|file_put_contents/', file_get_contents( __DIR__ . '/../terratales-indexing/terratales-indexing.php' ) ) );
echo $fails ? "\n$fails failed\n" : "\nall passed\n"; exit( $fails ? 1 : 0 );
