//! The real `Http` (updater.py's requests session): ureq over rustls, the app's User-Agent and timeouts.

use std::io::Read as _;
use std::time::Duration;

use super::fetch::{Http, HttpError, Response};

/// updater.TIMEOUT: 5 s to connect, 15 s between bytes.
pub const CONNECT: Duration = Duration::from_secs(5);
pub const BETWEEN_BYTES: Duration = Duration::from_secs(15);
/// The body is read this much at a time.
pub const CHUNK: usize = 64 * 1024;

pub struct Net {
    agent: ureq::Agent,
}

impl Net {
    /// A session saying it is `BlackListDetect/<version>`.
    pub fn new(version: &str) -> Net {
        let agent = ureq::AgentBuilder::new()
            .timeout_connect(CONNECT)
            .timeout_read(BETWEEN_BYTES)
            .user_agent(&format!("BlackListDetect/{version}"))
            .build();
        Net { agent }
    }

    /// The answer, a status of 400 or more included; Err only when no answer came.
    fn answer(&self, url: &str) -> Result<ureq::Response, HttpError> {
        match self.agent.get(url).call() {
            Ok(response) | Err(ureq::Error::Status(_, response)) => Ok(response),
            Err(error) => Err(HttpError(error.to_string())),
        }
    }
}

impl Http for Net {
    fn get(&mut self, url: &str) -> Result<Response, HttpError> {
        let response = self.answer(url)?;
        let status = response.status();
        let mut body = Vec::new();
        response.into_reader().read_to_end(&mut body).map_err(|error| HttpError(error.to_string()))?;
        Ok(Response { status, body })
    }

    fn stream(&mut self, url: &str, chunk: &mut dyn FnMut(&[u8]) -> bool) -> Result<(), HttpError> {
        let response = self.answer(url)?;
        if response.status() >= 400 {
            return Err(HttpError(response.status().to_string()));
        }
        let mut reader = response.into_reader();
        let mut buffer = vec![0u8; CHUNK];
        loop {
            let got = reader.read(&mut buffer).map_err(|error| HttpError(error.to_string()))?;
            if got == 0 || !chunk(&buffer[..got]) {
                return Ok(());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_server_is_an_error_not_an_answer() {
        // Port 9 on this machine: refused at once, offline.
        let mut net = Net::new("1.0.0");
        assert!(net.get("http://127.0.0.1:9/version.json").is_err());
        assert!(net.stream("http://127.0.0.1:9/a.zip", &mut |_| true).is_err());
    }
}
