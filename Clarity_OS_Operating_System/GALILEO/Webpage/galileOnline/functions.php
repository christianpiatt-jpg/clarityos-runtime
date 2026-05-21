<?php
function galileonline_enqueue() {
    wp_enqueue_style('galileonline-style', get_stylesheet_uri());
}
add_action('wp_enqueue_scripts', 'galileonline_enqueue');