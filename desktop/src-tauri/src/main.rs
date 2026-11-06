#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{fs, io::{Read, Write}, net::{TcpListener, TcpStream}, process::{Child, Command, Stdio}, sync::{Arc, Mutex}, thread, time::{Duration, Instant}};
use tauri::Manager;
use tauri_plugin_opener::OpenerExt;
mod updates;

struct Backend { child: Mutex<Option<Child>>, port: u16, secret: String }
fn official_page(url: &reqwest::Url) -> bool {
    url.scheme()=="https" && url.username().is_empty() && url.password().is_none() &&
      (matches!(url.host_str(),Some("cdn.deepseek.com"|"platform.deepseek.com"|"api-docs.deepseek.com"|"openrouter.ai"|"platform.openai.com"|"platform.claude.com")) ||
      (url.host_str()==Some("github.com") && (url.path()=="/LeymansGuz/Study-Desk" || url.path().starts_with("/LeymansGuz/Study-Desk/"))))
}
impl Backend {
    fn request(&self, path: &str, method: &str) -> bool {
        let Ok(mut stream) = TcpStream::connect_timeout(&([127,0,0,1],self.port).into(), Duration::from_millis(500)) else { return false };
        let _=stream.set_read_timeout(Some(Duration::from_secs(1)));
        let request=format!("{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nX-Study-Desktop: {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",self.port,self.secret);
        if stream.write_all(request.as_bytes()).is_err() { return false }
        let mut buf=[0u8;128];
        stream.read(&mut buf).map(|n| String::from_utf8_lossy(&buf[..n]).starts_with("HTTP/1.1 200")).unwrap_or(false)
    }
    fn stop(&self) {
        let _=self.request("/desktop/stop","POST");
        let deadline=Instant::now()+Duration::from_secs(25);
        if let Ok(mut child)=self.child.lock() {
            if let Some(process)=child.as_mut() {
                while Instant::now()<deadline {
                    if process.try_wait().ok().flatten().is_some() {return}
                    thread::sleep(Duration::from_millis(100));
                }
                let _=process.kill();let _=process.wait();
            }
        }
    }
}

fn main() {
    let engine=Arc::new(Mutex::new(None::<Arc<Backend>>));
    let setup_engine=engine.clone();
    let app=tauri::Builder::default()
      .plugin(tauri_plugin_updater::Builder::new().build())
      .plugin(tauri_plugin_opener::init())
      .plugin(tauri_plugin_single_instance::init(|app,_,_| {
          if let Some(window)=app.get_webview_window("main") { let _=window.show();let _=window.set_focus(); }
      }))
      .setup(move |app| {
        let data=std::env::var_os("STUDY_DESKTOP_DATA_DIR").map(std::path::PathBuf::from).unwrap_or(app.path().app_data_dir()?);
        fs::create_dir_all(&data)?;
        let resource=app.path().resource_dir()?;
        let backend=resource.join("backend").join(if cfg!(windows){"StudyDeskBackend.exe"}else{"StudyDeskBackend"});
        let listener=TcpListener::bind("127.0.0.1:0")?;let port=listener.local_addr()?.port();drop(listener);
        let secret=format!("{}{}",uuid::Uuid::new_v4().simple(),uuid::Uuid::new_v4().simple());
        let mut command=Command::new(backend);
        command.args(["--port",&port.to_string(),"--data-dir",&data.to_string_lossy(),"--parent-pid",&std::process::id().to_string()]);
        command.env("STUDY_DESKTOP_SECRET",&secret).stdin(Stdio::null()).stdout(Stdio::null());
        command.env("STUDY_DESKTOP_VERSION",app.package_info().version.to_string());
        let log=fs::OpenOptions::new().create(true).append(true).open(data.join("startup.log"))?;
        command.stderr(Stdio::from(log));
        #[cfg(windows)] { use std::os::windows::process::CommandExt;command.creation_flags(0x08000000); }
        let child=command.spawn()?;
        let state=Arc::new(Backend {child:Mutex::new(Some(child)),port,secret});
        *setup_engine.lock().unwrap()=Some(state.clone());
        updates::start(app.handle().clone(), state.clone());
        let external=app.handle().clone();
        let window=tauri::WebviewWindowBuilder::new(app,"main",tauri::WebviewUrl::App("index.html".into()))
          .disable_drag_drop_handler()
          .title("Study Desk").inner_size(1280.0,860.0).min_inner_size(800.0,620.0)
          .on_navigation(move |url| {
              if official_page(url) {
                  let _=external.opener().open_url(url.as_str(),None::<&str>);
                  return false;
              }
              matches!(url.scheme(),"tauri"|"about") || (url.scheme()=="http" && url.host_str()==Some("127.0.0.1") && url.port()==Some(port)) || (url.scheme()=="http" && url.host_str()==Some("tauri.localhost"))
          }).build()?;
        thread::spawn(move || {
            let deadline=Instant::now()+Duration::from_secs(120);
            while Instant::now()<deadline {
                if state.request("/desktop/ready","GET") {
                    let url=format!("http://127.0.0.1:{}/desktop/launch?token={}",state.port,state.secret);
                    if let Ok(parsed)=url.parse(){let _=window.navigate(parsed);}
                    return
                }
                if state.child.lock().unwrap().as_mut().and_then(|c|c.try_wait().ok().flatten()).is_some(){break}
                thread::sleep(Duration::from_millis(300));
            }
            let _=window.eval("document.querySelector('#message').textContent='Study Desk could not start. Close this window and reopen the app. If it happens again, see startup.log in your application data folder.';");
        });
        Ok(())
      }).build(tauri::generate_context!()).expect("Study Desk could not initialize");
    app.run(move |_,event| {
        if let tauri::RunEvent::Exit=event {
            if let Some(state)=engine.lock().unwrap().as_ref(){state.stop();}
        }
    });
}

#[cfg(test)]
mod link_tests {
    use super::*;
    #[test]
    fn provider_key_links_open_only_on_official_hosts() {
        for url in ["https://platform.deepseek.com/api_keys","https://platform.openai.com/api-keys","https://platform.claude.com/settings/keys","https://openrouter.ai/keys"] {assert!(official_page(&url.parse().unwrap()));}
        for url in ["https://platform.deepseek.com.evil.test/api_keys","https://secret@platform.deepseek.com/api_keys","http://platform.deepseek.com/api_keys","https://github.com/another/project"] {assert!(!official_page(&url.parse().unwrap()));}
    }
}
