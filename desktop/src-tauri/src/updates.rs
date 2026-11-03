//! All update authority stays in Rust. The webview can request named actions,
//! never override the signing key, update feed, installation path or package.
use std::{sync::Arc, thread, time::Duration};
use serde_json::{json, Value};
use tauri_plugin_updater::UpdaterExt;
use crate::Backend;

const FEED: &str = "https://raw.githubusercontent.com/LeymansGuz/Study-Desk/main/desktop/update-manifest.json";

fn official_asset(url: &reqwest::Url, version: &str) -> bool {
    let prefix = format!("/LeymansGuz/Study-Desk/releases/download/v{version}");
    let Some(rest) = url.path().strip_prefix(&prefix) else { return false };
    url.scheme()=="https" && url.host_str()==Some("github.com") && url.username().is_empty()
        && url.password().is_none() && url.query().is_none() && url.fragment().is_none()
        && (rest.starts_with('/') || rest.starts_with('-'))
        && rest.rsplit('/').next().is_some_and(|name|name.contains(version))
}

fn report(client: &reqwest::blocking::Client, backend: &Backend, state: &str, message: &str, version: &str, received: u64, total: u64) {
    let _ = client.post(format!("http://127.0.0.1:{}/desktop/update/result", backend.port))
        .header("X-Study-Desktop", &backend.secret)
        .json(&json!({"state":state,"message":message,"version":version,"received":received,"total":total})).send();
}

pub fn start(app: tauri::AppHandle, backend: Arc<Backend>) {
    thread::spawn(move || {
        let Ok(client) = reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(5)).build() else { return };
        let mut candidate = None;
        let mut package: Option<Vec<u8>> = None;
        loop {
            thread::sleep(Duration::from_secs(1));
            let command = client.get(format!("http://127.0.0.1:{}/desktop/update/command", backend.port))
                .header("X-Study-Desktop", &backend.secret).send().and_then(|r|r.error_for_status()).and_then(|r|r.json::<Value>());
            let Ok(command) = command else { continue };
            match command["action"].as_str().unwrap_or("") {
                "check" => {
                    candidate = None; package = None;
                    let result = tauri::async_runtime::block_on(async {
                        app.updater_builder().endpoints(vec![FEED.parse().unwrap()])?
                            .timeout(Duration::from_secs(30)).build()?.check().await
                    });
                    match result {
                        Ok(Some(mut update)) => {
                            update.timeout = Some(Duration::from_secs(900));
                            // Restrict even manifest-provided URLs to official release assets.
                            let url = &update.download_url;
                            if !official_asset(url, &update.version) {
                                report(&client,&backend,"error","The update feed did not contain an official release download.","",0,0);
                                continue;
                            }
                            report(&client,&backend,"available","A signed update is available. Download when ready.",&update.version,0,0);
                            candidate = Some(update);
                        },
                        Ok(None) => report(&client,&backend,"current","You have the current published version.","",0,0),
                        Err(_) => report(&client,&backend,"error","Could not check for updates. Check your connection and try again. Your current app is unchanged.","",0,0),
                    }
                },
                "download" => {
                    if let Some(update) = candidate.as_ref() {
                        let mut received = 0u64;
                        let mut last = std::time::Instant::now();
                        let result = tauri::async_runtime::block_on(update.download(|chunk,total| {
                            received += chunk as u64;
                            if last.elapsed() > Duration::from_millis(500) {
                                report(&client,&backend,"downloading","Downloading the update…",&update.version,received,total.unwrap_or(0));
                                last = std::time::Instant::now();
                            }
                        }, || {}));
                        match result {
                            Ok(bytes) => {
                                report(&client,&backend,"downloaded","Signature verified. Install and restart when your study work is finished.",&update.version,bytes.len() as u64,bytes.len() as u64);
                                package=Some(bytes);
                            },
                            Err(_) => {
                                report(&client,&backend,"error","Download or signature verification failed. No update was installed. Check your connection and free space, then check again.","",0,0);
                                package=None;candidate=None;
                            }
                        }
                    } else { report(&client,&backend,"error","Check for updates again before downloading.","",0,0); }
                },
                "install" => {
                    if let (Some(update),Some(bytes)) = (candidate.as_ref(),package.take()) {
                        report(&client,&backend,"installing","Backup verified. Restarting to install the signed update…",&update.version,0,0);
                        backend.stop();
                        // install() rechecks the signature. The package never comes from webview input.
                        if update.install(bytes).is_err() {
                            // Restart the existing installed application if replacement failed.
                            app.restart();
                        }
                        #[cfg(not(windows))]
                        app.restart();
                    } else { report(&client,&backend,"error","The downloaded package is no longer available. Check for updates again.","",0,0); }
                },
                _ => {},
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_versioned_official_assets_are_accepted() {
        for url in ["http://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.4/x0.2.4.exe",
                    "https://evil.test/LeymansGuz/Study-Desk/releases/download/v0.2.4/x0.2.4.exe",
                    "https://github.com/other/Study-Desk/releases/download/v0.2.4/x0.2.4.exe",
                    "https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.3/x0.2.3.exe"] {
            assert!(!official_asset(&url.parse().unwrap(),"0.2.4"));
        }
        assert!(official_asset(&"https://github.com/LeymansGuz/Study-Desk/releases/download/v0.2.4-beta.1/Study-Desk_0.2.4_x64-setup.exe".parse().unwrap(),"0.2.4"));
    }
}
