<?php
/**
 * ClarityOS Minimal Theme Functions
 * Removes all sidebars, widgets, patterns, and block CSS.
 */

/* Disable block patterns */
remove_theme_support('core-block-patterns');

/* Disable widgets and sidebars */
function clarityos_unregister_widgets() {
    unregister_sidebar('sidebar-1');
}
add_action('widgets_init', 'clarityos_unregister_widgets', 11);

/* Remove block editor styles */
function clarityos_remove_block_styles() {
    wp_dequeue_style('wp-block-library');
    wp_dequeue_style('wp-block-library-theme');
    wp_dequeue_style('global-styles');
}
add_action('wp_enqueue_scripts', 'clarityos_remove_block_styles', 100);

/* Remove theme supports */
function clarityos_minimal_setup() {
    remove_theme_support('post-thumbnails');
    remove_theme_support('custom-header');
    remove_theme_support('custom-background');
    remove_theme_support('custom-logo');
    remove_theme_support('automatic-feed-links');
    remove_theme_support('editor-styles');
}
add_action('after_setup_theme', 'clarityos_minimal_setup');