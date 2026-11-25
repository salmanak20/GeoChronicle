use rand::RngCore;
use serde::{
    Deserialize, Deserializer, Serialize, Serializer,
    de::{DeserializeOwned, Visitor},
};
use std::{
    fs::{self, OpenOptions},
    net::TcpListener,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::{Duration, Instant},
};
use tauri::{Manager, RunEvent};

const START_TIMEOUT: Duration = Duration::from_secs(20);
const STOP_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_START_ATTEMPTS: usize = 4;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum LifecycleState {
    Starting,
    Ready,
    Stopping,
    Stopped,
    Error,
}

#[derive(Serialize)]
struct BackendStatus {
    state: LifecycleState,
    database_ready: bool,
    error: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct Health {
    status: String,
    application: String,
    api_version: String,
    database: String,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum ProjectStatus {
    Draft,
    InProgress,
    Completed,
    Archived,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Project {
    id: i64,
    name: String,
    description: Option<String>,
    topic: Option<String>,
    status: ProjectStatus,
    target_duration_seconds: Option<i32>,
    aspect_ratio: String,
    language: String,
    visual_style: String,
    created_at: String,
    updated_at: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ProjectInput {
    name: String,
    description: Option<String>,
    topic: Option<String>,
    target_duration_seconds: Option<i32>,
    aspect_ratio: String,
    language: String,
    visual_style: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct ProjectPatch {
    #[serde(default, skip_serializing_if = "PatchValue::is_missing")]
    name: PatchValue<String>,
    #[serde(default, skip_serializing_if = "PatchValue::is_missing")]
    description: PatchValue<String>,
    #[serde(default, skip_serializing_if = "PatchValue::is_missing")]
    topic: PatchValue<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    status: Option<ProjectStatus>,
    #[serde(default, skip_serializing_if = "PatchValue::is_missing")]
    target_duration_seconds: PatchValue<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    aspect_ratio: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    language: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    visual_style: Option<String>,
}

#[derive(Clone, Debug, Default)]
enum PatchValue<T> {
    #[default]
    Missing,
    Null,
    Value(T),
}

impl<T> PatchValue<T> {
    fn is_missing(&self) -> bool {
        matches!(self, Self::Missing)
    }
}

impl<T: Serialize> Serialize for PatchValue<T> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            Self::Missing | Self::Null => serializer.serialize_none(),
            Self::Value(value) => value.serialize(serializer),
        }
    }
}

impl<'de, T: Deserialize<'de>> Deserialize<'de> for PatchValue<T> {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct PatchVisitor<T>(std::marker::PhantomData<T>);
        impl<'de, T: Deserialize<'de>> Visitor<'de> for PatchVisitor<T> {
            type Value = PatchValue<T>;
            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("null or a project field value")
            }
            fn visit_none<E: serde::de::Error>(self) -> Result<Self::Value, E> {
                Ok(PatchValue::Null)
            }
            fn visit_unit<E: serde::de::Error>(self) -> Result<Self::Value, E> {
                Ok(PatchValue::Null)
            }
            fn visit_some<D: Deserializer<'de>>(
                self,
                deserializer: D,
            ) -> Result<Self::Value, D::Error> {
                T::deserialize(deserializer).map(PatchValue::Value)
            }
        }
        deserializer.deserialize_option(PatchVisitor(std::marker::PhantomData))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ProjectPage {
    items: Vec<Project>,
    total: u64,
    page: u32,
    page_size: u32,
    pages: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ProjectStats {
    total: u64,
    draft: u64,
    in_progress: u64,
    completed: u64,
    recently_updated: Vec<Project>,
}

struct OwnedProcess {
    child: Child,
    token: String,
    port: u16,
}

struct Inner {
    state: LifecycleState,
    process: Option<OwnedProcess>,
    error: Option<String>,
    database_ready: bool,
}

#[derive(Clone)]
struct BackendManager {
    inner: std::sync::Arc<Mutex<Inner>>,
    python: PathBuf,
    backend_dir: PathBuf,
}

impl BackendManager {
    fn new() -> Self {
        let backend_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("..")
            .join("services")
            .join("backend");
        let python = backend_dir.join(".venv").join("Scripts").join("python.exe");
        Self {
            inner: std::sync::Arc::new(Mutex::new(Inner {
                state: LifecycleState::Stopped,
                process: None,
                error: None,
                database_ready: false,
            })),
            python,
            backend_dir,
        }
    }

    fn start(&self) -> Result<(), String> {
        let mut inner = self.inner.lock().map_err(|_| "Backend state unavailable")?;
        if !begin_start(&mut inner)? {
            return Ok(());
        }
        if !self.python.exists() {
            return fail(&mut inner, "Python backend environment is missing".into());
        }

        let mut last_error = "Backend failed to start".to_string();
        let log_path = backend_log_path();
        if let Some(parent) = log_path.parent() {
            if fs::create_dir_all(parent).is_err() {
                return fail(&mut inner, "Unable to prepare backend log".into());
            }
        }
        let log_file = match OpenOptions::new().create(true).append(true).open(&log_path) {
            Ok(file) => file,
            Err(_) => return fail(&mut inner, "Unable to open backend log".into()),
        };
        for _ in 0..MAX_START_ATTEMPTS {
            let port = match select_port() {
                Ok(port) => port,
                Err(error) => {
                    last_error = error;
                    continue;
                }
            };
            let token = new_token();
            let stdout = match log_file.try_clone() {
                Ok(file) => Stdio::from(file),
                Err(_) => return fail(&mut inner, "Unable to open backend log".into()),
            };
            let stderr = match log_file.try_clone() {
                Ok(file) => Stdio::from(file),
                Err(_) => return fail(&mut inner, "Unable to open backend log".into()),
            };
            let child = match Command::new(&self.python)
                .arg("run.py")
                .current_dir(&self.backend_dir)
                .env("GEOCHRONICLE_AUTH_TOKEN", &token)
                .env("GEOCHRONICLE_PORT", port.to_string())
                .stdin(Stdio::null())
                .stdout(stdout)
                .stderr(stderr)
                .spawn()
            {
                Ok(child) => child,
                Err(_) => {
                    last_error = "Unable to launch the Python backend".into();
                    break;
                }
            };
            inner.process = Some(OwnedProcess { child, token, port });
            let startup_started = Instant::now();
            let mut collision_or_exit = false;
            while !startup_timed_out(startup_started, START_TIMEOUT) {
                let ready = inner
                    .process
                    .as_ref()
                    .is_some_and(|p| health_request(p, "/api/v1/health/ready").is_ok());
                if ready {
                    inner.state = LifecycleState::Ready;
                    inner.database_ready = true;
                    return Ok(());
                }
                let exited = inner
                    .process
                    .as_mut()
                    .and_then(|p| p.child.try_wait().ok().flatten())
                    .is_some();
                if exited {
                    collision_or_exit = port_collision_detected(true, false);
                    last_error =
                        "Backend exited before readiness; see the local backend log for details"
                            .into();
                    reap_owned(&mut inner.process, false);
                    break;
                }
                std::thread::sleep(Duration::from_millis(200));
            }
            if !collision_or_exit {
                last_error = "Backend startup timed out".into();
                reap_owned(&mut inner.process, true);
                break;
            }
        }
        fail(&mut inner, last_error)
    }

    fn status(&self) -> BackendStatus {
        let mut inner = match self.inner.try_lock() {
            Ok(inner) => inner,
            Err(std::sync::TryLockError::WouldBlock) => {
                return BackendStatus {
                    state: LifecycleState::Starting,
                    database_ready: false,
                    error: None,
                };
            }
            Err(std::sync::TryLockError::Poisoned(_)) => {
                return BackendStatus {
                    state: LifecycleState::Error,
                    database_ready: false,
                    error: Some("Backend state unavailable".into()),
                };
            }
        };
        if inner.state == LifecycleState::Ready {
            let healthy = inner
                .process
                .as_ref()
                .is_some_and(|p| health_request(p, "/api/v1/health/ready").is_ok());
            if !healthy {
                let exited = inner
                    .process
                    .as_mut()
                    .and_then(|p| p.child.try_wait().ok().flatten())
                    .is_some();
                if exited {
                    mark_crashed(&mut inner);
                } else {
                    inner.database_ready = false;
                }
            } else {
                inner.database_ready = true;
            }
        }
        BackendStatus {
            state: inner.state,
            database_ready: inner.database_ready,
            error: inner.error.clone(),
        }
    }

    fn api_request<T: DeserializeOwned>(
        &self,
        method: reqwest::Method,
        path: &str,
        query: &[(String, String)],
        body: Option<serde_json::Value>,
    ) -> Result<T, String> {
        let inner = self
            .inner
            .lock()
            .map_err(|_| "Backend state unavailable".to_string())?;
        let process = inner
            .process
            .as_ref()
            .ok_or_else(|| "Backend is disconnected".to_string())?;
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .map_err(|_| "Backend HTTP client unavailable".to_string())?;
        let mut request = client
            .request(method, format!("http://127.0.0.1:{}{path}", process.port))
            .header("X-Geo-Token", &process.token)
            .query(query);
        if let Some(body) = body {
            request = request.json(&body);
        }
        let response = request
            .send()
            .map_err(|_| "Backend request failed; check its connection".to_string())?;
        let status = response.status();
        if !status.is_success() {
            let details = response.json::<serde_json::Value>().unwrap_or_default();
            return Err(backend_error_message(status.as_u16(), &details));
        }
        if status == reqwest::StatusCode::NO_CONTENT {
            return serde_json::from_value(serde_json::Value::Null)
                .map_err(|_| "Backend returned an unexpected empty response".into());
        }
        response
            .json::<T>()
            .map_err(|_| "Backend returned an invalid response".into())
    }

    fn stop(&self) {
        let Ok(mut inner) = self.inner.lock() else {
            return;
        };
        if shutdown_finished(inner.state) && inner.process.is_none() {
            return;
        }
        inner.state = LifecycleState::Stopping;
        inner.database_ready = false;
        if let Some(mut owned) = inner.process.take() {
            graceful_shutdown_request(owned.port, &owned.token);
            let until = Instant::now() + STOP_TIMEOUT;
            loop {
                match owned.child.try_wait() {
                    Ok(Some(_)) => break,
                    Ok(None) if Instant::now() < until => {
                        std::thread::sleep(Duration::from_millis(100))
                    }
                    _ => {
                        force_and_reap(&mut owned.child);
                        break;
                    }
                }
            }
            let _ = owned.child.wait();
            invalidate_token(&mut owned.token);
        }
        inner.state = LifecycleState::Stopped;
        inner.error = None;
    }
}

fn backend_log_path() -> PathBuf {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("GeoChronicle")
        .join("logs")
        .join("backend.log")
}

fn backend_error_message(status: u16, details: &serde_json::Value) -> String {
    let message = details
        .get("detail")
        .and_then(|detail| detail.get("message"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("Backend rejected the request");
    format!("{message} (HTTP {status})")
}

fn begin_start(inner: &mut Inner) -> Result<bool, String> {
    match inner.state {
        LifecycleState::Ready => Ok(false),
        LifecycleState::Starting | LifecycleState::Stopping => {
            Err("Backend lifecycle operation is already in progress".into())
        }
        state if backend_retry_allowed(state) => {
            inner.state = LifecycleState::Starting;
            inner.error = None;
            inner.database_ready = false;
            Ok(true)
        }
        _ => Err("Backend cannot be started from its current state".into()),
    }
}

fn fail<T>(inner: &mut Inner, message: String) -> Result<T, String> {
    reap_owned(&mut inner.process, true);
    inner.state = LifecycleState::Error;
    inner.error = Some(message.clone());
    inner.database_ready = false;
    Err(message)
}

fn reap_owned(process: &mut Option<OwnedProcess>, force: bool) {
    if let Some(mut owned) = process.take() {
        if force {
            let _ = owned.child.kill();
        }
        let _ = owned.child.wait();
        owned.token.clear();
    }
}

fn select_port() -> Result<u16, String> {
    allocate_port_with(1, || {
        let listener = TcpListener::bind(("127.0.0.1", 0))
            .map_err(|_| "Unable to allocate a localhost port".to_string())?;
        listener
            .local_addr()
            .map(|addr| addr.port())
            .map_err(|_| "Unable to inspect allocated localhost port".to_string())
    })
}

fn allocate_port_with<F>(attempts: usize, mut allocator: F) -> Result<u16, String>
where
    F: FnMut() -> Result<u16, String>,
{
    let mut last_error = "Unable to allocate a localhost port".to_string();
    for _ in 0..attempts {
        match allocator() {
            Ok(port) => return Ok(port),
            Err(error) => last_error = error,
        }
    }
    Err(last_error)
}

fn mark_crashed(inner: &mut Inner) {
    reap_owned(&mut inner.process, false);
    inner.state = LifecycleState::Error;
    inner.database_ready = false;
    inner.error = Some("Backend process stopped unexpectedly".into());
}

fn force_and_reap(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn invalidate_token(token: &mut String) {
    token.clear();
}

fn port_collision_detected(child_exited: bool, authenticated_ready: bool) -> bool {
    child_exited && !authenticated_ready
}

fn shutdown_finished(state: LifecycleState) -> bool {
    state == LifecycleState::Stopped
}

#[cfg(test)]
fn child_is_owned(process: &OwnedProcess, pid: u32) -> bool {
    process.child.id() == pid
}

fn backend_retry_allowed(state: LifecycleState) -> bool {
    matches!(state, LifecycleState::Stopped | LifecycleState::Error)
}

fn startup_timed_out(started: Instant, timeout: Duration) -> bool {
    started.elapsed() >= timeout
}

fn graceful_shutdown_request(port: u16, token: &str) {
    let url = format!("http://127.0.0.1:{port}/api/v1/internal/shutdown");
    let _ = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .and_then(|client| client.post(url).header("X-Geo-Token", token).send());
}

fn new_token() -> String {
    let mut bytes = [0u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn health_request(process: &OwnedProcess, path: &str) -> Result<Health, String> {
    reqwest::blocking::Client::builder()
        .timeout(Duration::from_millis(700))
        .build()
        .map_err(|_| "HTTP client unavailable".to_string())?
        .get(format!("http://127.0.0.1:{}{}", process.port, path))
        .header("X-Geo-Token", &process.token)
        .send()
        .map_err(|_| "Backend unavailable".to_string())?
        .error_for_status()
        .map_err(|_| "Backend returned an error".to_string())?
        .json()
        .map_err(|_| "Invalid backend response".to_string())
}

#[tauri::command]
fn backend_status(manager: tauri::State<BackendManager>) -> BackendStatus {
    manager.status()
}

#[tauri::command]
fn retry_backend(manager: tauri::State<BackendManager>) -> Result<BackendStatus, String> {
    manager.start()?;
    Ok(manager.status())
}

#[tauri::command]
fn create_project(
    manager: tauri::State<BackendManager>,
    payload: ProjectInput,
) -> Result<Project, String> {
    let body = serde_json::to_value(payload).map_err(|_| "Invalid project request".to_string())?;
    manager.api_request(reqwest::Method::POST, "/api/v1/projects", &[], Some(body))
}

#[tauri::command]
fn list_projects(
    manager: tauri::State<BackendManager>,
    page: u32,
    page_size: u32,
    search: Option<String>,
    status: Option<ProjectStatus>,
    sort_by: String,
    sort_order: String,
) -> Result<ProjectPage, String> {
    let mut query = vec![
        ("page".into(), page.to_string()),
        ("page_size".into(), page_size.to_string()),
        ("sort_by".into(), sort_by),
        ("sort_order".into(), sort_order),
    ];
    if let Some(search) = search {
        query.push(("search".into(), search));
    }
    if let Some(status) = status {
        query.push((
            "status".into(),
            serde_json::to_value(status)
                .unwrap()
                .as_str()
                .unwrap()
                .into(),
        ));
    }
    manager.api_request(reqwest::Method::GET, "/api/v1/projects", &query, None)
}

#[tauri::command]
fn get_project(manager: tauri::State<BackendManager>, project_id: i64) -> Result<Project, String> {
    manager.api_request(
        reqwest::Method::GET,
        &format!("/api/v1/projects/{project_id}"),
        &[],
        None,
    )
}

#[tauri::command]
fn update_project(
    manager: tauri::State<BackendManager>,
    project_id: i64,
    payload: ProjectPatch,
) -> Result<Project, String> {
    let body = serde_json::to_value(payload).map_err(|_| "Invalid project update".to_string())?;
    manager.api_request(
        reqwest::Method::PATCH,
        &format!("/api/v1/projects/{project_id}"),
        &[],
        Some(body),
    )
}

#[tauri::command]
fn delete_project(manager: tauri::State<BackendManager>, project_id: i64) -> Result<(), String> {
    manager.api_request(
        reqwest::Method::DELETE,
        &format!("/api/v1/projects/{project_id}"),
        &[],
        None,
    )
}

#[tauri::command]
fn project_stats(manager: tauri::State<BackendManager>) -> Result<ProjectStats, String> {
    manager.api_request(reqwest::Method::GET, "/api/v1/projects/stats", &[], None)
}

pub fn run() {
    tauri::Builder::default()
        .manage(BackendManager::new())
        .invoke_handler(tauri::generate_handler![
            backend_status,
            retry_backend,
            create_project,
            list_projects,
            get_project,
            update_project,
            delete_project,
            project_stats
        ])
        .setup(|app| {
            let manager = app.state::<BackendManager>();
            let manager = manager.inner().clone();
            std::thread::spawn(move || {
                let _ = manager.start();
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("tauri init")
        .run(|app, event| {
            if matches!(event, RunEvent::Exit) {
                if let Some(manager) = app.try_state::<BackendManager>() {
                    manager.stop();
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn initial_state_is_stopped_without_child() {
        let manager = BackendManager::new();
        let status = manager.status();
        assert_eq!(status.state, LifecycleState::Stopped);
        assert!(!status.database_ready);
        assert!(manager.inner.lock().unwrap().process.is_none());
    }
    #[test]
    fn port_selection_returns_loopback_available_port() {
        let port = select_port().unwrap();
        let listener = TcpListener::bind(("127.0.0.1", port)).unwrap();
        assert!(listener.local_addr().unwrap().ip().is_loopback());
    }
    #[test]
    fn duplicate_start_does_not_create_second_process() {
        let mut inner = Inner {
            state: LifecycleState::Starting,
            process: None,
            error: None,
            database_ready: false,
        };
        assert!(begin_start(&mut inner).is_err());
        assert!(inner.process.is_none());
    }
    #[test]
    fn startup_and_failure_states_transition_explicitly() {
        let mut inner = Inner {
            state: LifecycleState::Stopped,
            process: None,
            error: None,
            database_ready: false,
        };
        assert!(begin_start(&mut inner).unwrap());
        assert_eq!(inner.state, LifecycleState::Starting);
        inner.state = LifecycleState::Ready;
        inner.database_ready = true;
        assert!(!begin_start(&mut inner).unwrap());
        assert!(fail::<()>(&mut inner, "startup failure".into()).is_err());
        assert_eq!(inner.state, LifecycleState::Error);
        assert_eq!(inner.error.as_deref(), Some("startup failure"));
    }
    #[test]
    fn retry_can_start_after_error() {
        let mut inner = Inner {
            state: LifecycleState::Error,
            process: None,
            error: Some("old".into()),
            database_ready: false,
        };
        assert!(begin_start(&mut inner).unwrap());
        assert_eq!(inner.state, LifecycleState::Starting);
        assert!(inner.error.is_none());
    }
    #[test]
    fn token_is_unpredictable_and_fixed_length() {
        let a = new_token();
        let b = new_token();
        assert_eq!(a.len(), 64);
        assert_ne!(a, b);
    }
    #[test]
    fn stopping_or_error_state_never_owns_a_stale_child_token() {
        let inner = Inner {
            state: LifecycleState::Stopped,
            process: None,
            error: None,
            database_ready: false,
        };
        assert!(inner.process.is_none());
    }
    #[test]
    fn port_allocation_failure_is_reported_after_bounded_attempts() {
        let mut calls = 0;
        let error = allocate_port_with(3, || {
            calls += 1;
            Err("allocation unavailable".into())
        })
        .unwrap_err();
        assert_eq!(calls, 3);
        assert_eq!(error, "allocation unavailable");
    }
    #[test]
    fn collision_requires_child_exit_and_no_authenticated_readiness() {
        assert!(port_collision_detected(true, false));
        assert!(!port_collision_detected(false, false));
        assert!(!port_collision_detected(true, true));
    }
    #[test]
    fn crash_detection_clears_readiness_and_sets_error() {
        let mut inner = Inner {
            state: LifecycleState::Ready,
            process: None,
            error: None,
            database_ready: true,
        };
        mark_crashed(&mut inner);
        assert_eq!(inner.state, LifecycleState::Error);
        assert!(!inner.database_ready);
        assert!(inner.error.is_some());
    }
    #[test]
    fn startup_timeout_boundary_is_bounded() {
        let started = Instant::now() - Duration::from_secs(2);
        assert!(startup_timed_out(started, Duration::from_secs(1)));
        assert!(!startup_timed_out(Instant::now(), Duration::from_secs(1)));
    }
    #[test]
    fn retry_is_allowed_only_from_stopped_or_error() {
        assert!(backend_retry_allowed(LifecycleState::Error));
        assert!(backend_retry_allowed(LifecycleState::Stopped));
        assert!(!backend_retry_allowed(LifecycleState::Ready));
        assert!(!backend_retry_allowed(LifecycleState::Stopping));
    }
    #[test]
    fn token_invalidation_erases_secret_material() {
        let mut token = "test-token".to_string();
        invalidate_token(&mut token);
        assert!(token.is_empty());
    }
    #[test]
    fn shutdown_is_idempotent_when_already_stopped() {
        let manager = BackendManager::new();
        manager.stop();
        manager.stop();
        assert!(shutdown_finished(manager.status().state));
    }
    #[test]
    fn owned_child_can_be_force_terminated_and_reaped() {
        let mut child = Command::new("cmd.exe")
            .args(["/C", "ping -n 30 127.0.0.1 > nul"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("start test child");
        let pid = child.id();
        let process = OwnedProcess {
            child,
            token: "secret".into(),
            port: 1,
        };
        assert!(child_is_owned(&process, pid));
        assert!(!child_is_owned(&process, pid.wrapping_add(1)));
        child = process.child;
        force_and_reap(&mut child);
        assert!(child.try_wait().unwrap().is_some());
    }
    #[test]
    fn patch_serialization_preserves_omitted_and_null_fields() {
        let patch = ProjectPatch {
            description: PatchValue::Null,
            target_duration_seconds: PatchValue::Value(720),
            ..ProjectPatch::default()
        };
        let value = serde_json::to_value(patch).unwrap();
        assert_eq!(value["description"], serde_json::Value::Null);
        assert_eq!(value["target_duration_seconds"], 720);
        assert!(value.get("name").is_none());
    }
    #[test]
    fn project_status_command_serializes_to_api_contract() {
        assert_eq!(
            serde_json::to_string(&ProjectStatus::InProgress).unwrap(),
            "\"in_progress\""
        );
    }
    #[test]
    fn project_response_deserializes_typed_api_shape() {
        let value = serde_json::json!({
            "id": 4, "name": "Project", "description": null, "topic": "History",
            "status": "draft", "target_duration_seconds": null, "aspect_ratio": "16:9",
            "language": "en", "visual_style": "hybrid", "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"
        });
        let project: Project = serde_json::from_value(value).unwrap();
        assert_eq!(project.id, 4);
        assert_eq!(project.status, ProjectStatus::Draft);
    }
    #[test]
    fn backend_errors_are_mapped_to_safe_messages() {
        let details = serde_json::json!({"detail":{"code":"project_not_found","message":"Project 42 was not found"}});
        assert_eq!(
            backend_error_message(404, &details),
            "Project 42 was not found (HTTP 404)"
        );
        assert_eq!(
            backend_error_message(500, &serde_json::json!({})),
            "Backend rejected the request (HTTP 500)"
        );
    }
    #[test]
    fn typed_project_request_reports_disconnected_backend() {
        let manager = BackendManager::new();
        let result: Result<ProjectPage, String> =
            manager.api_request(reqwest::Method::GET, "/api/v1/projects", &[], None);
        assert_eq!(result.unwrap_err(), "Backend is disconnected");
    }
    #[test]
    fn invalid_project_response_is_rejected_by_type_deserializer() {
        let response = serde_json::from_value::<Project>(serde_json::json!({"id":"bad"}));
        assert!(response.is_err());
    }
}
