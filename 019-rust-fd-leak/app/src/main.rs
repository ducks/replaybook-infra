use std::fs::File;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Mutex, OnceLock};

static OPEN_DOCUMENTS: OnceLock<Mutex<Vec<File>>> = OnceLock::new();

fn open_documents() -> &'static Mutex<Vec<File>> {
    OPEN_DOCUMENTS.get_or_init(|| Mutex::new(Vec::new()))
}

fn respond(stream: &mut TcpStream, status: &str, body: &str) {
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Length: {}\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
}

fn open_fd_count() -> usize {
    std::fs::read_dir("/proc/self/fd")
        .map(|entries| entries.count())
        .unwrap_or(usize::MAX)
}

fn handle(mut stream: TcpStream) {
    let mut request = [0_u8; 4096];
    let size = stream.read(&mut request).unwrap_or(0);
    let first_line = String::from_utf8_lossy(&request[..size])
        .lines()
        .next()
        .unwrap_or("")
        .to_string();
    let path = first_line.split_whitespace().nth(1).unwrap_or("/");

    if path == "/health" {
        respond(&mut stream, "200 OK", "ok");
    } else if path == "/bounded" {
        if open_fd_count() <= 20 {
            respond(&mut stream, "200 OK", "bounded");
        } else {
            respond(&mut stream, "503 Service Unavailable", "resource pressure");
        }
    } else if path.starts_with("/work/") {
        match File::open("/var/lib/fd-service/payload.txt") {
            Ok(file) => {
                open_documents().lock().unwrap().push(file);
                respond(&mut stream, "200 OK", "processed");
            }
            Err(_) => respond(&mut stream, "503 Service Unavailable", "resource pressure"),
        }
    } else {
        respond(&mut stream, "404 Not Found", "missing");
    }
}

fn main() -> std::io::Result<()> {
    let listener = TcpListener::bind("127.0.0.1:3000")?;
    for stream in listener.incoming() {
        if let Ok(stream) = stream {
            handle(stream);
        }
    }
    Ok(())
}
