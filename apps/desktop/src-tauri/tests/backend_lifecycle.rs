use std::{
    net::TcpListener,
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant},
};

fn wait_for_exit(child: &mut Child, timeout: Duration) -> bool {
    let until = Instant::now() + timeout;
    while Instant::now() < until {
        if child.try_wait().ok().flatten().is_some() {
            return child.wait().is_ok();
        }
        thread::sleep(Duration::from_millis(50));
    }
    false
}

#[test]
fn actual_python_backend_authenticates_shuts_down_and_is_reaped() {
    let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let backend = manifest
        .join("..")
        .join("..")
        .join("..")
        .join("services")
        .join("backend");
    let python = backend.join(".venv").join("Scripts").join("python.exe");
    if !python.exists() {
        panic!(
            "repository Python virtual environment missing: run backend setup before cargo test"
        );
    }
    let reservation = TcpListener::bind(("127.0.0.1", 0)).expect("allocate integration port");
    let port = reservation.local_addr().unwrap().port();
    drop(reservation);
    let token = format!("rust-integration-{}", std::process::id());
    let db = std::env::temp_dir().join(format!("geochronicle-rust-{}.db", std::process::id()));
    let mut child = Command::new(&python)
        .arg("run.py")
        .current_dir(&backend)
        .env("GEOCHRONICLE_AUTH_TOKEN", &token)
        .env("GEOCHRONICLE_PORT", port.to_string())
        .env(
            "GEOCHRONICLE_DATABASE_URL",
            format!("sqlite:///{}", db.to_string_lossy().replace('\\', "/")),
        )
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("start real backend process");
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(1))
        .build()
        .unwrap();
    let base = format!("http://127.0.0.1:{port}");
    let until = Instant::now() + Duration::from_secs(20);
    let mut ready = false;
    while Instant::now() < until {
        if client
            .get(format!("{base}/api/v1/health/ready"))
            .header("X-Geo-Token", &token)
            .send()
            .is_ok_and(|r| r.status().is_success())
        {
            ready = true;
            break;
        }
        if child.try_wait().ok().flatten().is_some() {
            break;
        }
        thread::sleep(Duration::from_millis(100));
    }
    assert!(ready, "real backend did not become ready");
    let marker = Command::new(&python)
        .args([
            "-c",
            "import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); db.execute('CREATE TABLE IF NOT EXISTS gc_process_marker (value TEXT NOT NULL)'); db.execute('INSERT INTO gc_process_marker VALUES (?)', ('retained',)); db.commit()",
        ])
        .arg(&db)
        .status()
        .expect("write integration marker");
    assert!(
        marker.success(),
        "integration marker must persist in SQLite"
    );
    assert_eq!(
        client
            .get(format!("{base}/api/v1/health"))
            .send()
            .unwrap()
            .status(),
        401
    );
    assert_eq!(
        client
            .get(format!("{base}/api/v1/health"))
            .header("X-Geo-Token", "wrong")
            .send()
            .unwrap()
            .status(),
        401
    );
    assert_eq!(
        client
            .post(format!("{base}/api/v1/internal/shutdown"))
            .header("X-Geo-Token", &token)
            .send()
            .unwrap()
            .status(),
        202
    );
    assert!(
        wait_for_exit(&mut child, Duration::from_secs(8)),
        "backend process did not exit and reap gracefully"
    );
    assert!(
        client.get(format!("{base}/api/v1/health")).send().is_err(),
        "backend listener remained after shutdown"
    );
    let second_reservation = TcpListener::bind(("127.0.0.1", 0)).expect("allocate restart port");
    let second_port = second_reservation.local_addr().unwrap().port();
    drop(second_reservation);
    let second_token = format!("rust-restart-{}", std::process::id());
    let mut restarted = Command::new(&python)
        .arg("run.py")
        .current_dir(&backend)
        .env("GEOCHRONICLE_AUTH_TOKEN", &second_token)
        .env("GEOCHRONICLE_PORT", second_port.to_string())
        .env(
            "GEOCHRONICLE_DATABASE_URL",
            format!("sqlite:///{}", db.to_string_lossy().replace('\\', "/")),
        )
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("restart real backend against persisted database");
    let second_base = format!("http://127.0.0.1:{second_port}");
    let until = Instant::now() + Duration::from_secs(20);
    let mut restarted_ready = false;
    while Instant::now() < until {
        if client
            .get(format!("{second_base}/api/v1/health/ready"))
            .header("X-Geo-Token", &second_token)
            .send()
            .is_ok_and(|r| r.status().is_success())
        {
            restarted_ready = true;
            break;
        }
        if restarted.try_wait().ok().flatten().is_some() {
            break;
        }
        thread::sleep(Duration::from_millis(100));
    }
    assert!(
        restarted_ready,
        "backend did not restart against its persisted database"
    );
    assert_eq!(
        client
            .post(format!("{second_base}/api/v1/internal/shutdown"))
            .header("X-Geo-Token", &second_token)
            .send()
            .unwrap()
            .status(),
        202
    );
    assert!(
        wait_for_exit(&mut restarted, Duration::from_secs(8)),
        "restarted backend did not reap"
    );
    let persisted = Command::new(&python)
        .args(["-c", "import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); print(db.execute('SELECT value FROM gc_process_marker').fetchone()[0])"])
        .arg(&db)
        .output()
        .expect("read persistence marker after backend restart");
    assert!(persisted.status.success());
    assert_eq!(
        String::from_utf8_lossy(&persisted.stdout).trim(),
        "retained"
    );
    let _ = std::fs::remove_file(db);
}

#[test]
fn occupied_local_port_is_not_mistaken_for_the_backend() {
    let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let backend = manifest
        .join("..")
        .join("..")
        .join("..")
        .join("services")
        .join("backend");
    let python = backend.join(".venv").join("Scripts").join("python.exe");
    if !python.exists() {
        panic!(
            "repository Python virtual environment missing: run backend setup before cargo test"
        );
    }
    let reservation = TcpListener::bind(("127.0.0.1", 0)).expect("allocate collision port");
    let port = reservation.local_addr().unwrap().port();
    let token = format!("collision-test-{}", std::process::id());
    let mut child = Command::new(&python)
        .arg("run.py")
        .current_dir(&backend)
        .env("GEOCHRONICLE_AUTH_TOKEN", &token)
        .env("GEOCHRONICLE_PORT", port.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("start backend against occupied port");
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
        .unwrap();
    let until = Instant::now() + Duration::from_secs(8);
    let mut exited = false;
    while Instant::now() < until {
        if child.try_wait().ok().flatten().is_some() {
            exited = child.wait().is_ok();
            break;
        }
        thread::sleep(Duration::from_millis(50));
    }
    assert!(
        exited,
        "backend must fail startup rather than claim an occupied listener"
    );
    let response = client
        .get(format!("http://127.0.0.1:{port}/api/v1/health/ready"))
        .header("X-Geo-Token", &token)
        .send();
    assert!(response.is_err() || !response.unwrap().status().is_success());
    drop(reservation);
}
