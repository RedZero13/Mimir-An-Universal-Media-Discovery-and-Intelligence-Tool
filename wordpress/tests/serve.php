<?php
/**
 * An HTTP front for the stand-in, for browser tests:  php -S 127.0.0.1:8099 wordpress/tests/serve.php
 * Routes /wp-json/mimir/v1/... to the real plugin code; state lives in memory for the life of the server process only.
 */
declare(strict_types=1);
require __DIR__ . '/wp-stubs.php';

header( 'Access-Control-Allow-Origin: *' );
header( 'Access-Control-Allow-Headers: content-type' );
header( 'Content-Type: application/json' );
if ( 'OPTIONS' === $_SERVER['REQUEST_METHOD'] ) { http_response_code( 204 ); exit; }
$route = preg_replace( '#^/wp-json/mimir/v1#', '', parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH ) );
$body  = 'POST' === $_SERVER['REQUEST_METHOD'] ? ( json_decode( file_get_contents( 'php://input' ), true ) ?: array() ) : array();
[ $status, $data ] = call( $route, $body, $_SERVER['REMOTE_ADDR'] );
http_response_code( $status );
echo json_encode( isset( $data['code'] ) && $status >= 400 ? array( 'code' => $data['code'], 'message' => $data['message'] ?? '', 'data' => array_merge( array( 'status' => $status ), array_diff_key( $data, array( 'code' => 1, 'message' => 1 ) ) ) ) : $data );
