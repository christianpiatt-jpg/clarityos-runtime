<?php
/**
 * Plugin Name:       ClarityOS Embed
 * Plugin URI:        https://pro-mediations.com/
 * Description:       Embeds the ClarityOS operator surface inside this WordPress site. Provides a [clarityos] shortcode and a "ClarityOS Embed" page template that mounts the React app on a blank canvas.
 * Version:           0.1.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            ClarityOS
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       clarityos-embed
 *
 * External to ClarityOS runtime — this plugin lives outside the
 * backend / web / phone / desktop tree and consumes the same built
 * assets the cockpit ships. See ../../README.md.
 */

// Prevent direct access — standard WP plugin hardening.
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'CLARITYOS_EMBED_VERSION', '0.1.0' );
define( 'CLARITYOS_EMBED_PATH', plugin_dir_path( __FILE__ ) );
define( 'CLARITYOS_EMBED_URL', plugin_dir_url( __FILE__ ) );
define( 'CLARITYOS_EMBED_TEMPLATE_KEY', 'clarityos-embed-page.php' );
define( 'CLARITYOS_EMBED_TEMPLATE_LABEL', 'ClarityOS Embed' );
define( 'CLARITYOS_EMBED_OPTION_API_BASE', 'clarityos_embed_api_base' );

/* -----------------------------------------------------------------
 * Asset enqueue
 *
 * Drops one JS + one CSS into the page. The build output of
 *   cd web && npm run build:embed
 * produces dist-embed/app.js and dist-embed/app.css with predictable
 * (un-hashed) filenames — copy or symlink those into ./assets/.
 *
 * Cache busting: we use the file mtime so a fresh build invalidates
 * the browser cache without bumping CLARITYOS_EMBED_VERSION.
 * ----------------------------------------------------------------- */

function clarityos_embed_enqueue_assets() {
    $js_path  = CLARITYOS_EMBED_PATH . 'assets/app.js';
    $css_path = CLARITYOS_EMBED_PATH . 'assets/app.css';

    // Inline config — runs before app.js so resolveBase() picks it up.
    // See web/src/lib/config.ts (window.CLARITYOS_API_BASE branch).
    $api_base = trim( (string) get_option( CLARITYOS_EMBED_OPTION_API_BASE, '' ) );
    if ( $api_base !== '' ) {
        wp_register_script( 'clarityos-embed-config', false, array(), CLARITYOS_EMBED_VERSION, false );
        wp_enqueue_script( 'clarityos-embed-config' );
        wp_add_inline_script(
            'clarityos-embed-config',
            'window.CLARITYOS_API_BASE=' . wp_json_encode( $api_base ) . ';',
            'before'
        );
    }

    if ( file_exists( $css_path ) ) {
        wp_enqueue_style(
            'clarityos-embed-app',
            CLARITYOS_EMBED_URL . 'assets/app.css',
            array(),
            (string) filemtime( $css_path )
        );
    }

    if ( file_exists( $js_path ) ) {
        wp_enqueue_script(
            'clarityos-embed-app',
            CLARITYOS_EMBED_URL . 'assets/app.js',
            array(),
            (string) filemtime( $js_path ),
            true // load in footer, after the mount div is in the DOM
        );
        // Vite outputs an ES module — WP needs the script tag to say type="module".
        add_filter( 'script_loader_tag', 'clarityos_embed_module_tag', 10, 3 );
    }
}

function clarityos_embed_module_tag( $tag, $handle, $src ) {
    if ( $handle !== 'clarityos-embed-app' ) {
        return $tag;
    }
    // Replace the default <script src="..."></script> with a module tag.
    return sprintf( '<script type="module" src="%s"></script>', esc_url( $src ) );
}

/* -----------------------------------------------------------------
 * [clarityos] shortcode
 *
 * Drops the mount div anywhere on a normal WP page or post. Use this
 * when the host page should keep its theme header/footer/sidebar
 * (e.g. ClarityOS inside an existing site layout).
 *
 * For a full-bleed cockpit experience, use the page template instead.
 * ----------------------------------------------------------------- */

function clarityos_embed_shortcode( $atts ) {
    clarityos_embed_enqueue_assets();
    return '<div id="clarityos-root" style="min-height:600px;"></div>';
}
add_shortcode( 'clarityos', 'clarityos_embed_shortcode' );

/* -----------------------------------------------------------------
 * "ClarityOS Embed" page template
 *
 * Registers a custom template the user can pick under Page Attributes →
 * Template when editing a Page. When selected, template_include swaps
 * in our blank canvas (templates/embed-page.php) which strips theme
 * chrome and renders only the mount div.
 * ----------------------------------------------------------------- */

function clarityos_embed_register_template( $templates ) {
    $templates[ CLARITYOS_EMBED_TEMPLATE_KEY ] = CLARITYOS_EMBED_TEMPLATE_LABEL;
    return $templates;
}
add_filter( 'theme_page_templates', 'clarityos_embed_register_template' );

function clarityos_embed_load_template( $template ) {
    if ( ! is_singular( 'page' ) ) {
        return $template;
    }
    $assigned = (string) get_page_template_slug( get_queried_object_id() );
    if ( $assigned !== CLARITYOS_EMBED_TEMPLATE_KEY ) {
        return $template;
    }
    $candidate = CLARITYOS_EMBED_PATH . 'templates/embed-page.php';
    if ( file_exists( $candidate ) ) {
        return $candidate;
    }
    return $template;
}
add_filter( 'template_include', 'clarityos_embed_load_template' );

/* -----------------------------------------------------------------
 * Settings page — minimal: just the backend API base URL.
 *
 * Lives under Settings → ClarityOS Embed. No surface for tokens or
 * cohorts because those resolve through the operator UI itself; the
 * plugin only needs to know where the backend lives.
 * ----------------------------------------------------------------- */

function clarityos_embed_register_settings() {
    register_setting(
        'clarityos_embed_settings',
        CLARITYOS_EMBED_OPTION_API_BASE,
        array(
            'type'              => 'string',
            'sanitize_callback' => 'clarityos_embed_sanitize_api_base',
            'default'           => '',
        )
    );
}
add_action( 'admin_init', 'clarityos_embed_register_settings' );

function clarityos_embed_sanitize_api_base( $value ) {
    $value = trim( (string) $value );
    if ( $value === '' ) {
        return '';
    }
    $url = esc_url_raw( $value );
    // Strip trailing slashes — the JS side does the same on resolve.
    return rtrim( $url, '/' );
}

function clarityos_embed_add_settings_page() {
    add_options_page(
        'ClarityOS Embed',
        'ClarityOS Embed',
        'manage_options',
        'clarityos-embed',
        'clarityos_embed_render_settings_page'
    );
}
add_action( 'admin_menu', 'clarityos_embed_add_settings_page' );

function clarityos_embed_render_settings_page() {
    if ( ! current_user_can( 'manage_options' ) ) {
        return;
    }
    $current = (string) get_option( CLARITYOS_EMBED_OPTION_API_BASE, '' );
    ?>
    <div class="wrap">
        <h1>ClarityOS Embed</h1>
        <p>Point this WordPress install at your ClarityOS backend. Leave blank to use whatever the bundled <code>app.js</code> defaults to.</p>
        <form method="post" action="options.php">
            <?php settings_fields( 'clarityos_embed_settings' ); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label for="clarityos_embed_api_base">Backend URL</label></th>
                    <td>
                        <input
                            type="url"
                            id="clarityos_embed_api_base"
                            name="<?php echo esc_attr( CLARITYOS_EMBED_OPTION_API_BASE ); ?>"
                            value="<?php echo esc_attr( $current ); ?>"
                            class="regular-text code"
                            placeholder="https://clarity-engine-xxxxx.run.app"
                        />
                        <p class="description">Injected at runtime as <code>window.CLARITYOS_API_BASE</code> before <code>app.js</code> loads.</p>
                    </td>
                </tr>
            </table>
            <?php submit_button(); ?>
        </form>

        <hr>
        <h2>How to embed</h2>
        <ol>
            <li>Build the React bundle: <code>cd web &amp;&amp; npm run build:embed</code>.</li>
            <li>Copy <code>web/dist-embed/app.js</code> and <code>web/dist-embed/app.css</code> into this plugin's <code>assets/</code> directory.</li>
            <li>Either:
                <ul style="list-style: disc; margin-left: 24px;">
                    <li>Create a Page and pick "<strong>ClarityOS Embed</strong>" under Page Attributes → Template (full-bleed cockpit), or</li>
                    <li>Drop the shortcode <code>[clarityos]</code> into any page or post (keeps theme chrome).</li>
                </ul>
            </li>
        </ol>
    </div>
    <?php
}

/* -----------------------------------------------------------------
 * Settings link on the Plugins screen — small ergonomic touch.
 * ----------------------------------------------------------------- */

function clarityos_embed_plugin_action_links( $links ) {
    $url = admin_url( 'options-general.php?page=clarityos-embed' );
    array_unshift( $links, '<a href="' . esc_url( $url ) . '">Settings</a>' );
    return $links;
}
add_filter( 'plugin_action_links_' . plugin_basename( __FILE__ ), 'clarityos_embed_plugin_action_links' );
