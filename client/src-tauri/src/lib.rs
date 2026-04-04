// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// 社内ホスト (localhost 等) への通信がプロキシを経由しないよう NO_PROXY を設定する。
/// reqwest (tauri_plugin_http の内部実装) はクライアント生成時に NO_PROXY を参照する。
/// NO_PROXY / no_proxy の両方から既存エントリを収集してマージする。
fn setup_no_proxy() {
    let internal_hosts = ["localhost", "127.0.0.1"];

    // 既存の NO_PROXY / no_proxy を両方読んで重複排除しながら収集
    let mut hosts: Vec<String> = Vec::new();
    for var in &["NO_PROXY", "no_proxy"] {
        if let Ok(val) = std::env::var(var) {
            for h in val.split(',') {
                let h = h.trim().to_string();
                if !h.is_empty() && !hosts.contains(&h) {
                    hosts.push(h);
                }
            }
        }
    }
    for h in &internal_hosts {
        let s = h.to_string();
        if !hosts.contains(&s) {
            hosts.push(s);
        }
    }

    let merged = hosts.join(",");
    std::env::set_var("NO_PROXY", &merged);
    std::env::set_var("no_proxy", &merged);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    setup_no_proxy();

    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_sql::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
