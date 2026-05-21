<?php
/**
 * ClarityOS Embed — blank page template.
 *
 * Loaded by clarityos-embed.php via the `template_include` filter when
 * a Page has the "ClarityOS Embed" template selected. Strips theme
 * header / footer / sidebar / Gutenberg block wrappers and renders
 * only the React mount div.
 *
 * This file is NOT a standard WP page template (no Template Name
 * header) — it's loaded by filter, not by the WP theme template
 * hierarchy. That's deliberate: it keeps the template out of the
 * theme's editor and means switching themes does not break the embed.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// Make sure our enqueue ran — when the page is reached via template_include
// directly (some hosts skip the_content), the shortcode hook may not fire.
if ( function_exists( 'clarityos_embed_enqueue_assets' ) ) {
    clarityos_embed_enqueue_assets();
}

// Title — use the WP page title so the browser tab still reads something
// meaningful. Fall back to the bloginfo name.
$clarityos_embed_title = '';
if ( have_posts() ) {
    while ( have_posts() ) {
        the_post();
        $clarityos_embed_title = (string) get_the_title();
        break;
    }
    rewind_posts();
}
if ( $clarityos_embed_title === '' ) {
    $clarityos_embed_title = (string) get_bloginfo( 'name' );
}
?><!doctype html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo( 'charset' ); ?>" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title><?php echo esc_html( $clarityos_embed_title ); ?></title>

    <?php /* Match index.html — Inter + JetBrains Mono so the cockpit renders
             with the same typography it uses in standalone mode. */ ?>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

    <style>
        /* Reset only what conflicts with the cockpit. We deliberately do NOT
           pull in a full reset — the React app ships its own globals via
           styles/v1-globals.css. */
        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            background: #000;
            color: #fff;
        }
        #clarityos-root {
            min-height: 100vh;
        }
    </style>

    <?php
    // Emits enqueued styles + scripts registered with $in_footer=false. The
    // app.js script is enqueued $in_footer=true so it lands in wp_footer().
    wp_head();
    ?>
</head>
<body <?php body_class( 'clarityos-embed-body' ); ?>>

    <div id="clarityos-root"></div>

    <?php wp_footer(); ?>
</body>
</html>
