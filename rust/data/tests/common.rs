//! Shared by the update tests: the golden file, and pages served from a map instead of the network.

#![allow(dead_code)]

use std::collections::HashMap;

use data::update::fetch::{Http, HttpError, Response};
use serde_json::Value;

pub fn golden() -> Value {
    let text = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/update/golden.json")).unwrap();
    serde_json::from_str(&text).unwrap()
}

/// A page: a status and a body, or None for a request that does not connect.
pub type Page = Option<(u16, Vec<u8>)>;

/// The tests' _Session: every address asked is noted; one not in the map is a 404.
#[derive(Default)]
pub struct Pages {
    pub pages: HashMap<String, Page>,
    pub asked: Vec<String>,
}

impl Pages {
    pub fn from_golden(pages: &Value) -> Self {
        let pages = pages
            .as_object()
            .unwrap()
            .iter()
            .map(|(url, page)| {
                let page = page.as_object().map(|page| (page["status"].as_u64().unwrap() as u16, page["body"].as_str().unwrap().as_bytes().to_vec()));
                (url.clone(), page)
            })
            .collect();
        Self { pages, asked: Vec::new() }
    }

    pub fn with(mut self, url: &str, page: Page) -> Self {
        self.pages.insert(url.to_string(), page);
        self
    }

    fn answer(&mut self, url: &str) -> Result<Response, HttpError> {
        self.asked.push(url.to_string());
        match self.pages.get(url).cloned().unwrap_or(Some((404, Vec::new()))) {
            Some((status, body)) => Ok(Response { status, body }),
            None => Err(HttpError("cut off".into())),
        }
    }
}

impl Http for Pages {
    fn get(&mut self, url: &str) -> Result<Response, HttpError> {
        self.answer(url)
    }

    fn stream(&mut self, url: &str, chunk: &mut dyn FnMut(&[u8]) -> bool) -> Result<(), HttpError> {
        let response = self.answer(url)?;
        if response.status >= 400 {
            return Err(HttpError(response.status.to_string()));
        }
        for part in response.body.chunks(64 * 1024) {
            if !chunk(part) {
                break;
            }
        }
        Ok(())
    }
}
