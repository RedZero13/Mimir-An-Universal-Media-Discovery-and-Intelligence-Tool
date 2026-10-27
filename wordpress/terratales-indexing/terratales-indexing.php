<?php
/**
 * Plugin Name: Terratales Indexing Fixes
 * Description: Keeps search engines on the pages that matter: sends media attachment pages to their files, marks feeds noindex, and adds a canonical link and Organization data to the home page.
 * Version:     0.1.0
 * Requires PHP: 8.0
 * Author:      Terratales Media Entertainment Private Limited
 * License:     GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain: terratales-indexing
 *
 * Works as a normal plugin or pasted whole into a code-snippets plugin: one file, loads once, no settings, no database.
 *
 * Why: Google Search Console listed WordPress's automatic "attachment pages" (one thin page per uploaded image, such as
 * /terratales-media-entertainment-6a2ee4dfc0765/) as duplicates and as crawled but not indexed, and the feed as crawled but not
 * indexed. The home page also had no canonical link.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! class_exists( 'Terratales_Indexing' ) ) {

	final class Terratales_Indexing {

		const SITE_ID = 'https://terratalesmedia.world/';

		public static function boot(): void {
			add_action( 'template_redirect', array( __CLASS__, 'attachments' ), 1 );
			add_action( 'template_redirect', array( __CLASS__, 'feeds' ), 1 );
			add_action( 'wp_head', array( __CLASS__, 'head' ), 1 );
		}

		/** An attachment page is a thin duplicate of the file it shows: send people and crawlers to the file itself, permanently. */
		public static function attachments(): void {
			if ( ! is_attachment() ) {
				return;
			}
			$url = wp_get_attachment_url( get_queried_object_id() );
			if ( $url ) {
				wp_safe_redirect( $url, 301, 'Terratales Indexing Fixes' );
				exit;
			}
		}

		/** Feeds are for readers, not search results. */
		public static function feeds(): void {
			if ( is_feed() && ! headers_sent() ) {
				header( 'X-Robots-Tag: noindex, follow', true );
			}
		}

		/** The home page's canonical link, and the Organization the Mimir pages already point to ("#org"). */
		public static function head(): void {
			if ( ! is_front_page() ) {
				return;
			}
			$home = home_url( '/' );
			echo '<link rel="canonical" href="' . esc_url( $home ) . '" />' . "\n";
			$logo  = function_exists( 'get_site_icon_url' ) ? get_site_icon_url( 512 ) : '';
			$graph = array(
				array(
					'@type'   => 'Organization',
					'@id'     => self::SITE_ID . '#org',
					'name'    => 'Terratales Media Entertainment',
					'legalName' => 'Terratales Media Entertainment Private Limited',
					'url'     => $home,
					'email'   => 'hello@terratalesmedia.world',
					'address' => array( '@type' => 'PostalAddress', 'addressLocality' => 'New Delhi', 'postalCode' => '110030', 'addressCountry' => 'IN' ),
					'owns'    => array( array( '@type' => 'WebApplication', 'name' => 'Mimir', 'url' => 'https://mimir.terratalesmedia.world/' ) ),
				),
				array(
					'@type'     => 'WebSite',
					'@id'       => self::SITE_ID . '#site',
					'url'       => $home,
					'name'      => 'Terratales',
					'inLanguage' => 'en',
					'publisher' => array( '@id' => self::SITE_ID . '#org' ),
				),
			);
			if ( $logo ) {
				$graph[0]['logo'] = $logo;
			}
			echo '<script type="application/ld+json">' . wp_json_encode( array( '@context' => 'https://schema.org', '@graph' => $graph ), JSON_UNESCAPED_SLASHES | JSON_HEX_TAG ) . "</script>\n";
		}
	}

	Terratales_Indexing::boot();
}
