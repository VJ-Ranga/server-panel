<?php
/**
 * Plugin Name: Server Panel Auto Login
 * Version: 1.0.0
 * Description: One-use native WordPress admin login bridge for Server Panel.
 */

if (!defined('ABSPATH')) {
    exit;
}

function server_panel_auto_login_token_key($token) {
    return 'server_panel_auto_login_' . preg_replace('/[^a-f0-9]/', '', $token);
}

function server_panel_auto_login_create_token($user_login) {
    $user = get_user_by('login', $user_login);
    if (!$user || !user_can($user, 'manage_options')) {
        return new WP_Error('invalid_user', 'Administrator account not found');
    }

    try {
        $token = bin2hex(random_bytes(32));
    } catch (Exception $error) {
        return new WP_Error('token_error', 'Could not create login token');
    }

    set_transient(server_panel_auto_login_token_key($token), (int) $user->ID, 60);
    return $token;
}

function server_panel_auto_login_handle_request() {
    if (empty($_GET['server_panel_auto_login'])) {
        return;
    }

    $token = (string) $_GET['server_panel_auto_login'];
    $user_id = get_transient(server_panel_auto_login_token_key($token));
    delete_transient(server_panel_auto_login_token_key($token));

    if (!$user_id || !get_user_by('id', $user_id)) {
        wp_die('Login token expired or already used.', 'Server Panel Auto Login', array('response' => 403));
    }

    wp_set_auth_cookie($user_id, false, is_ssl());
    wp_safe_redirect(admin_url());
    exit;
}
add_action('init', 'server_panel_auto_login_handle_request', 1);

function server_panel_auto_login_uninstall() {
    global $wpdb;
    $wpdb->query("DELETE FROM {$wpdb->options} WHERE option_name LIKE '_transient_server_panel_auto_login_%' OR option_name LIKE '_transient_timeout_server_panel_auto_login_%'");
}
register_uninstall_hook(__FILE__, 'server_panel_auto_login_uninstall');
