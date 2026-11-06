//! All update authority stays in Rust. The webview can request named actions,
//! never override the signing key, update feed, installation path or package.
use std::{sync::Arc, thread, time::Duration};
use serde_json::{json, Value};
use tauri_plugin_updater::UpdaterExt;
use tauri::Manager;
use std::io::{Write, BufRead, BufReader};
use crate::Backend;

const FEED: &str = "https://raw.githubusercontent.com/LeymansGuz/Study-Desk/main/desktop/update-manifest.json";

fn diagnostic(app: &tauri::AppHandle, stage: &str, error: &dyn std::fmt::Display) {
    let directory=std::env::var_os("STUDY_DESKTOP_DATA_DIR").map(std::path::PathBuf::from).or_else(||app.path().app_data_dir().ok());
    if let Some(directory)=directory {
        let path=directory.join("updater.log");
        if std::fs::metadata(&path).map(|m|m.len()>1_000_000).unwrap_or(false) {
            let previous=directory.join("updater.previous.log");
            let _=std::fs::remove_file(&previous);let _=std::fs::rename(&path,previous);
        }
        if let Ok(mut file)=std::fs::OpenOptions::new().create(true).append(true).open(path) {
            let _=writeln!(file,"{:?} {stage}: {error}",std::time::SystemTime::now());
        }
    }
}

fn official_asset(url: &reqwest::Url, version: &str) -> bool {
    let prefix = format!("/LeymansGuz/Study-Desk/releases/download/v{version}");
    let Some(rest) = url.path().strip_prefix(&prefix) else { return false };
    url.scheme()=="https" && url.host_str()==Some("github.com") && url.username().is_empty()
        && url.password().is_none() && url.query().is_none() && url.fragment().is_none()
        && (rest.starts_with('/') || rest.starts_with('-'))
        && rest.rsplit('/').next().is_some_and(|name|name.contains(version))
}

fn report(client: &reqwest::blocking::Client, backend: &Backend, state: &str, message: &str, version: &str, received: u64, total: u64) {
    // download() invokes its progress callback inside Tokio. reqwest's blocking
    // client must run on a separate OS thread there, including response drop.
    // Joining keeps progress/final states ordered; at most one report is active.
    thread::scope(|scope| {
        let _=scope.spawn(|| {
            let _ = client.post(format!("http://127.0.0.1:{}/desktop/update/result", backend.port))
                .header("X-Study-Desktop", &backend.secret)
                .json(&json!({"state":state,"message":message,"version":version,"received":received,"total":total})).send();
        }).join();
    });
}

fn prepare_download(app: &tauri::AppHandle, backend: &Backend, client: &reqwest::blocking::Client, url: &str, signature: &str, version: &str) -> Result<(Vec<u8>,u64,u64),String> {
    let data=std::env::var_os("STUDY_DESKTOP_DATA_DIR").map(std::path::PathBuf::from).unwrap_or(app.path().app_data_dir().map_err(|e|e.to_string())?);
    let cache=data.join("update-cache");std::fs::create_dir_all(&cache).map_err(|e|e.to_string())?;
    let config:Value=serde_json::from_str(include_str!("../tauri.conf.json")).map_err(|e|e.to_string())?;
    let request=cache.join("request.json");
    std::fs::write(&request,serde_json::to_vec(&json!({"url":url,"signature":signature,"version":version,"public_key":config["plugins"]["updater"]["pubkey"],"cache":cache,"parent_pid":std::process::id()})).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    let helper=app.path().resource_dir().map_err(|e|e.to_string())?.join("backend").join(if cfg!(windows){"StudyDeskBackend.exe"}else{"StudyDeskBackend"});
    let mut command=std::process::Command::new(helper);
    command.arg("--update-download").arg(&request).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null());
    #[cfg(windows)] { use std::os::windows::process::CommandExt;command.creation_flags(0x08000000); }
    let mut child=command.spawn().map_err(|e|e.to_string())?;
    let mut completed=false;let mut reused_bytes=0;let mut downloaded_bytes=0;
    for line in BufReader::new(child.stdout.take().ok_or("Update helper unavailable")?).lines() {
        let line=line.map_err(|e|e.to_string())?;
        if line.len()>8192 {let _=child.kill();return Err("Invalid updater response".into())}
        let Ok(message)=serde_json::from_str::<Value>(&line) else {continue};
        if let Some(state)=message.get("progress") {
            let received=state["received"].as_u64().unwrap_or(0);let reused=state["reused"].as_u64().unwrap_or(0);
            let note=if state["fallback"].as_bool()==Some(true){"Using a full signed download; differential reuse was unavailable.".into()}else{format!("Downloading update · {:.1} MB downloaded · {:.1} MB reused",received as f64/1048576.0,reused as f64/1048576.0)};
            report(client,backend,"downloading",&note,version,received+reused,state["total"].as_u64().unwrap_or(0));
        }
        if let Some(done)=message.get("complete"){completed=true;reused_bytes=done["reused"].as_u64().unwrap_or(0);downloaded_bytes=done["received"].as_u64().unwrap_or(0);}
    }
    let status=child.wait().map_err(|e|e.to_string())?;let _=std::fs::remove_file(request);
    if !status.success() || !completed {return Err("Update reconstruction or signature verification failed".into())}
    let path=cache.join("previous.package");
    if std::fs::metadata(&path).map_err(|e|e.to_string())?.len()>1_500_000_000{return Err("Update package too large".into())}
    std::fs::read(path).map(|bytes|(bytes,reused_bytes,downloaded_bytes)).map_err(|e|e.to_string())
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
                        Err(error) => { diagnostic(&app,"check",&error); report(&client,&backend,"error","Could not check for updates. Check your connection and try again. Your current app is unchanged.","",0,0); },
                    }
                },
                "download" => {
                    if let Some(update) = candidate.as_ref() {
                        let result = prepare_download(&app,&backend,&client,update.download_url.as_str(),&update.signature,&update.version);
                        match result {
                            Ok((bytes,reused,downloaded)) => {
                                let note=format!("Signature verified · {:.1} MB downloaded · {:.1} MB reused. Install and restart when ready.",downloaded as f64/1048576.0,reused as f64/1048576.0);
                                report(&client,&backend,"downloaded",&note,&update.version,bytes.len() as u64,bytes.len() as u64);
                                package=Some(bytes);
                            },
                            Err(error) => {
                                diagnostic(&app,"download or signature",&error);
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
                        if let Err(error)=update.install(bytes) {
                            diagnostic(&app,"install",&error);
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
    fn progress_reporting_is_safe_inside_the_download_runtime() {
        use std::{io::{Read,Write},net::TcpListener,sync::Mutex};
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();
        let port=listener.local_addr().unwrap().port();
        let server=thread::spawn(move || {
            let (mut stream,_)=listener.accept().unwrap();
            stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut request=Vec::new();let mut buffer=[0;1024];
            while !request.windows(4).any(|s|s==b"\r\n\r\n") {
                let n=stream.read(&mut buffer).unwrap();if n==0 {break}request.extend_from_slice(&buffer[..n]);
            }
            assert!(String::from_utf8_lossy(&request).contains("POST /desktop/update/result"));
            stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}").unwrap();
        });
        let backend=Backend{child:Mutex::new(None),port,secret:"isolated-test-secret".into()};
        let client=reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(3)).build().unwrap();
        tauri::async_runtime::block_on(async {report(&client,&backend,"downloading","Downloading","0.2.5",1,2)});
        server.join().unwrap();
    }
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
