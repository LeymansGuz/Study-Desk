//! Native Save dialogs for authenticated, allowlisted local exports only.
use std::{sync::Arc,thread,time::Duration,io::{Read,Write}};
use serde_json::{Value,json};
use tauri_plugin_dialog::DialogExt;
use tauri::Manager;
use crate::Backend;

fn save(app:&tauri::AppHandle,backend:&Backend,client:&reqwest::blocking::Client,route:&str,passphrase:Option<&str>)->Result<Option<String>,String>{
    if !route.starts_with('/') || route.starts_with("//") || route.contains(['\\','\r','\n','#']) {return Err("Invalid export request.".into())}
    let url=format!("http://127.0.0.1:{}{}",backend.port,route);
    let request=if route=="/library/backups/encrypted" {client.post(url).json(&json!({"passphrase":passphrase.ok_or("Missing backup passphrase.")?}))}else{client.get(url)};
    let response=request.header("X-Study-Desktop",&backend.secret).send().map_err(|_|"Could not prepare this export. Please try again.")?;
    if !response.status().is_success(){
        let body:Value=response.json().unwrap_or_default();
        return Err(body["detail"].as_str().or(body["error"].as_str()).unwrap_or("The export failed. Your study work is kept.").chars().take(600).collect());
    }
    let disposition=response.headers().get("content-disposition").and_then(|v|v.to_str().ok()).unwrap_or("");
    let name=disposition.split(';').find_map(|v|v.trim().strip_prefix("filename=")).unwrap_or("study-export.dat").trim_matches('"');
    let name=name.rsplit(['/', '\\']).next().unwrap_or("study-export.dat").replace(['\r','\n'],"");
    let mut dialog=app.dialog().file().set_file_name(name);
    if let Some(window)=app.get_webview_window("main"){dialog=dialog.set_parent(&window);}
    let Some(destination)=dialog.blocking_save_file() else{return Ok(None)};
    let path=destination.into_path().map_err(|_|"Choose a local folder for the export.")?;
    let parent=path.parent().ok_or("Choose an available folder.")?;
    let mut temporary=tempfile::NamedTempFile::new_in(parent).map_err(|_|"Cannot write to that folder. Choose another location.")?;
    let size=std::io::copy(&mut response.take(600_000_001),&mut temporary).map_err(|_|"Saving failed. Check free space and try again; the existing file is kept.")?;
    if size>600_000_000{return Err("This export exceeds the download size limit.".into())}
    temporary.flush().map_err(|_|"Could not finish writing the export.")?;
    temporary.as_file().sync_all().map_err(|_|"Could not finish writing the export.")?;
    temporary.persist(&path).map_err(|_|"Could not save the export. Check permissions and try again.")?;
    Ok(Some(format!("Saved to {}",path.display())))
}

pub fn start(app:tauri::AppHandle,backend:Arc<Backend>){
    thread::spawn(move||{
        let Ok(client)=reqwest::blocking::Client::builder().no_proxy().redirect(reqwest::redirect::Policy::none()).timeout(Duration::from_secs(1800)).build() else{return};
        loop{
            thread::sleep(Duration::from_millis(500));
            let command=client.get(format!("http://127.0.0.1:{}/desktop/files/command",backend.port)).header("X-Study-Desktop",&backend.secret).send().and_then(|r|r.error_for_status()).and_then(|r|r.json::<Value>());
            let Ok(command)=command else{continue};let Some(id)=command["id"].as_str() else{continue};let Some(route)=command["route"].as_str() else{continue};
            let (state,message)=match save(&app,&backend,&client,route,command["passphrase"].as_str()){Ok(Some(path))=>("saved",path),Ok(None)=>("cancelled","Export cancelled. No file was saved.".into()),Err(e)=>("error",e)};
            let _=client.post(format!("http://127.0.0.1:{}/desktop/files/result",backend.port)).header("X-Study-Desktop",&backend.secret).json(&json!({"id":id,"state":state,"message":message})).send();
        }
    });
}
