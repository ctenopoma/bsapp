// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// ホスト(localhost)への通信がプロキシを経由しないよう NO_PROXY を設定する。
/// reqwest (tauri_plugin_http の内部実装) はクライアント生成時に NO_PROXY を参照する。
fn setup_no_proxy() {
    let no_proxy_hosts = "localhost,127.0.0.1";
    let merged = match std::env::var("NO_PROXY") {
        Ok(existing) if !existing.is_empty() => format!("{},{}", existing, no_proxy_hosts),
        _ => no_proxy_hosts.to_string(),
    };
    std::env::set_var("NO_PROXY", &merged);
    std::env::set_var("no_proxy", &merged);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    setup_no_proxy();

    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_sql::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
